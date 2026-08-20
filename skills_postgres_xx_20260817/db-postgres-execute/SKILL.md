---
name: "db-postgres-execute"
description: "PostgreSQL DDL/DML 执行技能（可控变更）。核心能力：DDL 执行（建表/改表/删表/索引/约束/视图/SCHEMA）、DML 执行（INSERT/UPSERT/UPDATE/DELETE）、数据查询与影响范围预估、变更前安全校验与变更后验证。适用场景：需要执行表结构变更、索引创建与删除、安全数据订正、批量数据操作等。功能限制：不执行 DROP DATABASE/TABLESPACE 等破坏性操作、不修改会话/全局配置参数、不执行 KILL/GRANT/REVOKE；DELETE 前须备份且必带 WHERE。"
version: "v1.0.0"
tags: db-modify
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "PostgreSQL 实例地址（host:port）"
  - name: "db_name"
    type: "string"
    required: false
    default: ""
    desc: "目标数据库名（可选）"
  - name: "schema_name"
    type: "string"
    required: false
    default: ""
    desc: "目标 SCHEMA 名（可选，默认 public）"
  - name: "table_name"
    type: "string"
    required: false
    default: ""
    desc: "目标表名（可选）"
  - name: "sql_text"
    type: "string"
    required: false
    default: ""
    desc: "待执行的 DDL/DML 语句（可选，执行指定 SQL 时使用）"
  - name: "operation"
    type: "string"
    required: false
    default: ""
    desc: "操作类型：ddl_create_table / ddl_alter_table / ddl_drop_table / ddl_create_index / ddl_drop_index / ddl_create_schema / ddl_truncate / dml_insert / dml_upsert / dml_update / dml_delete / dml_select"
  - name: "batch_size"
    type: "integer"
    required: false
    default: 1000
    desc: "批量 DML 操作每批处理行数"
  - name: "dry_run"
    type: "boolean"
    required: false
    default: true
    desc: "是否仅预估影响范围不实际执行变更（默认 true，避免误操作）"
support_db: postgresql
safe_level: "modify"
author: "团队出厂预置"
update_time: "2026-08-18"
---

# PostgreSQL DDL/DML 执行

> 本技能执行可控的 PostgreSQL DDL（表结构变更、索引、约束、视图、SCHEMA）与 DML（INSERT/UPSERT/UPDATE/DELETE）操作。严守出厂红线，所有变更前有安全检查、后有验证、可追溯。自包含。

## 核心能力
- 单一职责：DDL/DML 执行（可控变更）。
- DDL：建表/改表/删表、索引创建与删除、约束管理、视图创建、SCHEMA 管理、TRUNCATE。
- DML：INSERT/UPSERT（INSERT ... ON CONFLICT）、安全 UPDATE（带 WHERE）、安全 DELETE（带 WHERE）、数据查询与统计。

## 适用场景
- 创建新表、修改表结构（加列/删列/改列类型/改默认值）、删除表。
- 创建索引/删除索引（含 CONCURRENTLY）。
- 添加/删除约束（主键/外键/唯一/CHECK/NOT NULL）。
- 创建视图、管理 SCHEMA。
- 安全数据订正（INSERT/UPSERT/UPDATE/DELETE）。
- 数据查询与影响范围预估（SELECT COUNT）。

## 功能限制 / 安全边界
- 不执行 DROP DATABASE / DROP TABLESPACE / DROP EXTENSION 等破坏性操作。
- 不修改会话或全局配置参数（不执行 SET / ALTER SYSTEM）。
- 不执行 KILL / GRANT / REVOKE / CREATE ROLE / DROP ROLE 等权限管理操作。
- 不执行 VACUUM / ANALYZE / REINDEX（由专项技能负责）。
- DELETE 操作前必须先备份、且必带 WHERE 条件。
- 大表 DDL 操作（> 1GB）会提示评估风险，建议低峰期执行。
- 所有变更操作默认 dry_run=true（仅预估不执行），需显式设置 dry_run=false 才实际执行。
- 不调用其它 Skill、自包含、单一职责。

## 执行逻辑
1. **前置检查**：校验实例连通性、表大小、活跃事务、锁等待、备份状态。
2. **影响预估**（dry_run）：通过 SELECT 预估 DDL/DML 影响范围，不实际变更。
3. **执行变更**（dry_run=false）：在确认安全检查通过后，实际执行 DDL/DML。
4. **后置验证**：校验变更结果、数据一致性、行数变化。

---

## 一、变更前安全检查清单

| 检查项 | 检查方式 | 通过标准 |
|--------|----------|----------|
| 实例连通性 | `SELECT 1` | 正常返回 |
| 备份确认 | 确认备份 | 24h 内有备份 |
| 表大小 | `SELECT pg_size_pretty(pg_total_relation_size('<schema>.<table>'))` | 大表（> 1GB）DDL 需评估风险 |
| 活跃事务 | `SELECT COUNT(*) FROM pg_stat_activity WHERE state != 'idle' AND pid != pg_backend_pid()` | < 10 |
| 锁等待 | `SELECT COUNT(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND pid != pg_backend_pid()` | = 0 |
| 长事务 | `SELECT COUNT(*) FROM pg_stat_activity WHERE xact_start < NOW() - interval '60 seconds' AND pid != pg_backend_pid()` | = 0 |
| 复制延迟 | `SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) FROM pg_stat_replication` | < 100MB |

```sql
-- 安全检查一键执行
SELECT 1 AS connectivity_check;

SELECT pg_size_pretty(pg_total_relation_size('<schema>.<table>')) AS table_size;

SELECT COUNT(*) AS active_trx_count
FROM pg_stat_activity
WHERE state != 'idle' AND pid != pg_backend_pid();

SELECT COUNT(*) AS lock_wait_count
FROM pg_stat_activity
WHERE wait_event_type = 'Lock' AND pid != pg_backend_pid();

SELECT COUNT(*) AS long_trx_count
FROM pg_stat_activity
WHERE xact_start < NOW() - interval '60 seconds' AND pid != pg_backend_pid();
```

---

## 二、DDL 操作

### 2.1 建表（CREATE TABLE）

```sql
-- 影响预估（dry_run）
SELECT 'CREATE TABLE <schema>.<table_name>' AS planned_ddl;

-- 实际执行（dry_run=false）
CREATE TABLE <schema>.<table_name> (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 添加注释
COMMENT ON TABLE <schema>.<table_name> IS '表说明';
COMMENT ON COLUMN <schema>.<table_name>.id IS '主键ID';
```

**回滚**: `DROP TABLE <schema>.<table_name>;`

### 2.2 改表（ALTER TABLE）

```sql
-- 添加列
ALTER TABLE <schema>.<table_name>
ADD COLUMN <new_col> <data_type> DEFAULT <default_value>;

-- 删除列（高风险，需确认列无引用）
ALTER TABLE <schema>.<table_name>
DROP COLUMN <old_col>;

-- 修改列类型（可能重建全表，大表须评估）
ALTER TABLE <schema>.<table_name>
ALTER COLUMN <col_name> TYPE <new_type>;

-- 修改列默认值
ALTER TABLE <schema>.<table_name>
ALTER COLUMN <col_name> SET DEFAULT <new_default>;

-- 删除列默认值
ALTER TABLE <schema>.<table_name>
ALTER COLUMN <col_name> DROP DEFAULT;

-- 设置/删除 NOT NULL
ALTER TABLE <schema>.<table_name>
ALTER COLUMN <col_name> SET NOT NULL;
ALTER TABLE <schema>.<table_name>
ALTER COLUMN <col_name> DROP NOT NULL;

-- 重命名列
ALTER TABLE <schema>.<table_name>
RENAME COLUMN <old_name> TO <new_name>;

-- 重命名表
ALTER TABLE <schema>.<old_table_name>
RENAME TO <new_table_name>;
```

**回滚**: 反向操作（如 ADD COLUMN → DROP COLUMN；注意数据可能丢失，删列回滚须从备份恢复）。

### 2.3 删表（DROP TABLE）

> ⚠️ 红线操作：删除前必须确认备份、无外键引用、无业务依赖。

```sql
-- 先备份
CREATE TABLE <schema>.<table_name>_bak AS SELECT * FROM <schema>.<table_name>;

-- 检查外键引用
SELECT tc.table_schema, tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND kcu.table_schema = '<schema>'
  AND kcu.table_name = '<table_name>';

-- 实际删除（dry_run=false）
DROP TABLE <schema>.<table_name>;
```

**回滚**: 从备份恢复 `CREATE TABLE ..._bak` 中的数据和结构。

### 2.4 创建索引（CREATE INDEX）

```sql
-- 普通索引
CREATE INDEX <idx_name> ON <schema>.<table_name> (<col1>, <col2>);

-- 唯一索引
CREATE UNIQUE INDEX <idx_name> ON <schema>.<table_name> (<col1>);

-- 并发创建索引（不锁表，推荐生产环境使用）
CREATE INDEX CONCURRENTLY <idx_name> ON <schema>.<table_name> (<col1>);

-- 部分索引
CREATE INDEX <idx_name> ON <schema>.<table_name> (<col1>)
WHERE <col2> IS NOT NULL;

-- 表达式索引
CREATE INDEX <idx_name> ON <schema>.<table_name> (LOWER(<col1>));

-- 查看索引创建进度（CONCURRENTLY 时）
SELECT pid, phase, 
       lockers_total, lockers_done,
       blocks_total, blocks_done,
       tuples_total, tuples_done
FROM pg_stat_progress_create_index;
```

**回滚**: `DROP INDEX <idx_name>;`

### 2.5 删除索引（DROP INDEX）

```sql
-- 并发删除索引（不锁表）
DROP INDEX CONCURRENTLY <idx_name>;

-- 普通删除
DROP INDEX <idx_name>;
```

**回滚**: 重新创建索引 `CREATE INDEX ...`（记录原索引定义）。

### 2.6 约束管理

```sql
-- 添加主键
ALTER TABLE <schema>.<table_name>
ADD CONSTRAINT <pk_name> PRIMARY KEY (<col1>, <col2>);

-- 添加外键
ALTER TABLE <schema>.<table_name>
ADD CONSTRAINT <fk_name> FOREIGN KEY (<col>)
REFERENCES <ref_schema>.<ref_table> (<ref_col>)
ON DELETE CASCADE ON UPDATE CASCADE;

-- 添加唯一约束
ALTER TABLE <schema>.<table_name>
ADD CONSTRAINT <uq_name> UNIQUE (<col1>, <col2>);

-- 添加 CHECK 约束
ALTER TABLE <schema>.<table_name>
ADD CONSTRAINT <ck_name> CHECK (<col> > 0);

-- 删除约束
ALTER TABLE <schema>.<table_name>
DROP CONSTRAINT <constraint_name>;
```

**回滚**: 反向操作（DROP CONSTRAINT 后重新 ADD CONSTRAINT）。

### 2.7 创建视图

```sql
CREATE OR REPLACE VIEW <schema>.<view_name> AS
SELECT <col1>, <col2>
FROM <schema>.<table_name>
WHERE <condition>;
```

**回滚**: `DROP VIEW <schema>.<view_name>;`

### 2.8 SCHEMA 管理

```sql
-- 创建 SCHEMA
CREATE SCHEMA <schema_name>;

-- 查看所有 SCHEMA
SELECT schema_name FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
ORDER BY schema_name;

-- 删除 SCHEMA（仅空 SCHEMA）
DROP SCHEMA <schema_name>;

-- 删除 SCHEMA（级联删除其中所有对象，高风险）
DROP SCHEMA <schema_name> CASCADE;
```

**回滚**: DROP SCHEMA 前须先备份所有对象。

### 2.9 TRUNCATE

> ⚠️ TRUNCATE 不可回滚（非事务性），执行前必须备份。

```sql
-- 先备份
CREATE TABLE <schema>.<table_name>_bak AS SELECT * FROM <schema>.<table_name>;

-- 影响预估
SELECT COUNT(*) AS rows_to_truncate FROM <schema>.<table_name>;

-- 实际执行
TRUNCATE TABLE <schema>.<table_name>;

-- 级联截断（同时截断外键关联表）
TRUNCATE TABLE <schema>.<table_name> CASCADE;
```

**回滚**: 从备份 `_bak` 表恢复数据 `INSERT INTO <table> SELECT * FROM <table>_bak;`

---

## 三、DML 操作

### 3.1 INSERT（插入数据）

```sql
-- 单行插入
INSERT INTO <schema>.<table_name> (<col1>, <col2>, <col3>)
VALUES (<val1>, <val2>, <val3>);

-- 批量插入
INSERT INTO <schema>.<table_name> (<col1>, <col2>, <col3>)
VALUES
    (<val1>, <val2>, <val3>),
    (<val4>, <val5>, <val6>);

-- 验证
SELECT * FROM <schema>.<table_name> WHERE <col1> = <val1>;
```

### 3.2 UPSERT（INSERT ... ON CONFLICT）

```sql
-- 冲突时更新
INSERT INTO <schema>.<table_name> (<col1>, <col2>, <col3>)
VALUES (<val1>, <val2>, <val3>)
ON CONFLICT (<col1>)
DO UPDATE SET
    <col2> = EXCLUDED.<col2>,
    <col3> = EXCLUDED.<col3>,
    updated_at = NOW();

-- 冲突时忽略
INSERT INTO <schema>.<table_name> (<col1>, <col2>)
VALUES (<val1>, <val2>)
ON CONFLICT (<col1>) DO NOTHING;

-- 验证
SELECT * FROM <schema>.<table_name> WHERE <col1> = <val1>;
```

### 3.3 UPDATE（安全更新）

```sql
-- 影响预估（dry_run，不实际修改）
SELECT COUNT(*) AS estimated_rows
FROM <schema>.<table_name>
WHERE <condition>;

-- 查看受影响的样本数据
SELECT * FROM <schema>.<table_name>
WHERE <condition>
LIMIT 10;

-- 实际执行（dry_run=false）
UPDATE <schema>.<table_name>
SET <col1> = <new_val1>,
    <col2> = <new_val2>,
    updated_at = NOW()
WHERE <condition>;

-- 验证
SELECT COUNT(*) AS updated_rows
FROM <schema>.<table_name>
WHERE <condition> AND <col1> = <new_val1>;
```

**回滚思路**: UPDATE 前先 `CREATE TABLE <table>_bak AS SELECT * FROM <table> WHERE <condition>;` 留存。

### 3.4 DELETE（安全删除）

> ⚠️ DELETE 操作必须带 WHERE 条件，且执行前先备份。

```sql
-- 影响预估（dry_run，不实际删除）
SELECT COUNT(*) AS estimated_rows
FROM <schema>.<table_name>
WHERE <condition>;

-- 查看受影响的样本数据
SELECT * FROM <schema>.<table_name>
WHERE <condition>
LIMIT 10;

-- 备份受影响数据
CREATE TABLE <schema>.<table_name>_del_bak_<timestamp> AS
SELECT * FROM <schema>.<table_name>
WHERE <condition>;

-- 实际执行（dry_run=false）
DELETE FROM <schema>.<table_name>
WHERE <condition>;

-- 验证
SELECT COUNT(*) AS remaining_rows
FROM <schema>.<table_name>
WHERE <condition>;
```

**回滚**: 从备份恢复 `INSERT INTO <table> SELECT * FROM <table>_del_bak_<timestamp>;`

---

## 四、数据查询与影响预估（只读）

```sql
-- 基础查询
SELECT * FROM <schema>.<table_name>
WHERE <condition>
ORDER BY <col>
LIMIT 100;

-- 聚合统计
SELECT <col>, COUNT(*) AS cnt, AVG(<num>) AS avg_val
FROM <schema>.<table_name>
WHERE <condition>
GROUP BY <col>
ORDER BY cnt DESC;

-- 变更影响范围预估（仅统计，不改数据）
SELECT COUNT(*) AS affected_rows FROM <schema>.<table_name> WHERE <condition>;

-- 数据分布探查
SELECT <col>, COUNT(*) AS cnt
FROM <schema>.<table_name>
GROUP BY <col>
ORDER BY cnt DESC
LIMIT 20;

-- 执行计划分析
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM <schema>.<table_name> WHERE <condition>;
```

---

## 五、DDL 风险评估参考矩阵

| 操作 | 表大小 | 风险等级 | 评估建议 |
|------|--------|---------|---------|
| 加列（DEFAULT NULL） | < 1GB | 低 | 直接执行，无锁 |
| 加列（DEFAULT 非 NULL） | 任意 | 中 | 需全表重写，PG11+ 可缓解 |
| 删除列 | 任意 | 中 | 仅标记删除，需确认无引用 |
| 修改列类型 | 任意 | 高 | 可能重建全表，大表须评估 |
| 添加约束（NOT NULL） | 任意 | 中 | 需扫描全表验证 |
| 添加外键 | 任意 | 中 | 需验证引用完整性 |
| CREATE INDEX | < 1GB | 低 | 直接执行 |
| CREATE INDEX | > 1GB | 中 | 使用 CONCURRENTLY，低峰期执行 |
| CREATE INDEX CONCURRENTLY | 任意 | 低 | 不锁表，但耗时更长 |
| DROP TABLE | 任意 | 极高 | 红线，须先备份、双重确认 |
| TRUNCATE | 任意 | 极高 | 不可回滚，须先备份 |
| DROP SCHEMA CASCADE | 任意 | 极高 | 红线，须先备份所有对象 |

---

## 六、变更后验证

```sql
-- 表结构验证
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = '<schema>' AND table_name = '<table_name>'
ORDER BY ordinal_position;

-- 索引验证
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = '<schema>' AND tablename = '<table_name>';

-- 约束验证
SELECT conname, contype, pg_get_constraintdef(oid) AS constraint_def
FROM pg_constraint
WHERE conrelid = '<schema>.<table_name>'::regclass;

-- 数据行数验证
SELECT COUNT(*) AS row_count FROM <schema>.<table_name>;

-- 数据一致性验证
SELECT COUNT(*) AS bak_row_count FROM <schema>.<table_name>_bak;
```

---

## 七、异常处理
- 单条 SQL 执行失败返回结构化错误提示，不暴露原始报错栈。
- 前置检查不通过时输出具体未通过项与建议，不执行变更。
- DDL 执行因锁等待超时时，提示当前锁等待情况，建议低峰期重试。
- 影响行数与预期不符时暂停并提示人工核对。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- 所有变更操作默认 dry_run=true，防止误操作，需显式确认后才执行。

---

## 八、输出格式

```text
=== PostgreSQL DDL/DML 执行报告 ===
实例: <instance_host> | 数据库: <db_name> | SCHEMA: <schema_name>
操作类型: <operation> | 模式: <dry_run ? '预估（dry_run）' : '实际执行'>
执行时间: <timestamp>

## 前置检查
[✓] 实例连通性检查通过
[✓] 备份确认通过（24h 内有备份）
[✓] 活跃事务: <count>（< 10）
[✓] 锁等待: <count>（= 0）
[✓] 长事务: <count>（= 0）

## 影响预估
目标表: <schema>.<table>
表大小: <size>
预计影响行数: <count>
预计耗时: <estimated_duration>

## 执行结果
SQL: <executed_sql>
状态: <成功/失败>
影响行数: <affected_rows>
耗时: <duration>

## 后置验证
[✓] 表结构验证通过
[✓] 数据行数验证通过（<before> → <after>）
[✓] 数据一致性验证通过

## 回滚方案
回滚 SQL: <rollback_sql>
备份位置: <backup_table/directory>
```