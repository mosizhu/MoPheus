---
name: "db-oracle-execute"
description: "Oracle 普通 DDL/DML 执行技能（带自动回滚）。核心能力：执行普通 DDL（CREATE/ALTER/DROP TABLE、CREATE/DROP INDEX、TRUNCATE 等）与 DML（INSERT/UPDATE/DELETE/MERGE），所有变更操作自动记录回滚所需信息，支持失败自动回滚与手动回滚。适用场景：表结构变更、索引维护、数据订正、批量数据操作、开发/测试环境快速变更。功能限制：不执行 DCL（GRANT/REVOKE）、不修改系统参数、不执行 DROP TABLESPACE/DATABASE 等破坏性操作；TRUNCATE 不可回滚需二次确认；DDL 自动提交不可逆，仅支持反向 DDL 回滚。"
version: "v1.0.0"
tags: db-modify
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "sql_text"
    type: "string"
    required: true
    default: ""
    desc: "待执行的 SQL 语句（支持单条 DDL 或 DML，若为多条请用分号分隔的 PL/SQL 匿名块）"
  - name: "execute_type"
    type: "string"
    required: false
    default: "auto"
    desc: "执行类型：auto（自动识别 DDL/DML）/ ddl（强制 DDL 模式）/ dml（强制 DML 模式）"
  - name: "auto_rollback"
    type: "boolean"
    required: false
    default: true
    desc: "DML 执行后是否自动回滚（默认 true，即执行后回滚验证，确认无误后需再次执行并设 false 提交）；DDL 不可回滚，此参数仅对 DML 生效"
  - name: "dry_run"
    type: "boolean"
    required: false
    default: false
    desc: "是否为试运行模式（默认 false），true 时仅解析 SQL 并输出回滚方案，不实际执行"
  - name: "commit_batch_size"
    type: "integer"
    required: false
    default: 0
    desc: "DML 分批提交行数（默认 0 表示不自动分批，单次提交），建议大批量 DML 设为 5000~10000"
  - name: "timeout_seconds"
    type: "integer"
    required: false
    default: 300
    desc: "DML 执行超时时间（秒），默认 300 秒，超时自动回滚并终止"
support_db: oracle
safe_level: "modify"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 普通 DDL/DML 执行（带自动回滚）

> 本技能执行普通 DDL/DML 操作，核心特征：**所有变更操作自动记录回滚所需信息，DML 失败自动回滚到 SAVEPOINT，DDL 产出反向 DDL 以便回退**。轻量化、自包含、不依赖其他 Skill。

## 核心能力
- 单一职责：Oracle DDL/DML 执行 + 自动回滚（DML 通过 SAVEPOINT 回滚，DDL 通过反向 DDL 回退）。
- 支持 DDL：CREATE TABLE、ALTER TABLE、DROP TABLE（含 FLASHBACK）、CREATE INDEX、DROP INDEX、TRUNCATE TABLE（需二次确认）。
- 支持 DML：INSERT、UPDATE、DELETE、MERGE，支持分批提交（commit_batch_size）。
- 变更前自动记录回滚信息（表结构备份、受影响行数预估），变更后自动验证。

## 适用场景
- 表结构变更：添加/删除/修改列、重命名表/列、修改约束
- 索引维护：创建/删除普通索引
- 数据订正：少量 UPDATE/DELETE 数据修正
- 批量数据操作：大批量 INSERT/UPDATE/DELETE（分批提交）
- 开发/测试环境快速变更与回退
- 变更前的安全试运行（dry_run 模式）

## 功能限制 / 安全边界
- 不执行 DCL（GRANT/REVOKE/ALTER USER），不修改系统/会话参数
- 不执行 DROP TABLESPACE / DROP DATABASE / ALTER SYSTEM 等破坏性操作
- TRUNCATE TABLE 不可回滚（Oracle 不支持 FLASHBACK 恢复 TRUNCATE），需二次确认后执行
- DDL 自动提交（Oracle 特性），无法通过 SAVEPOINT 回滚，仅支持反向 DDL 回退
- 不调用其他 Skill；仅按需手动触发
- 所有变更前有检查清单，后有验证，可追溯可回滚

---

## 一、推理框架：DDL/DML 执行链

```
用户提出 DDL/DML 执行需求
    |
    v
[1] SQL 解析与分类
    | 识别 SQL 类型（DDL: CREATE/ALTER/DROP/TRUNCATE | DML: INSERT/UPDATE/DELETE/MERGE）
    | 提取操作对象（表名、列名、索引名）
    | 检查 SQL 是否在安全边界内（禁止 DCL/系统级操作）
    v
[2] 前置检查（只读）
    | 数据库版本与状态
    | 操作对象是否存在/权限是否足够
    | 表大小与受影响行数预估（DML）
    | 回收站状态（FLASHBACK 可用性，针对 DROP TABLE）
    | 当前活跃事务数
    v
[3] 回滚信息记录
    | DDL: 通过 DBMS_METADATA.GET_DDL 备份当前对象定义
    | DML: 记录受影响行数预估（SELECT COUNT(*)）
    | 生成回滚 SQL（反向 DDL 或数据备份方案）
    v
[4] 执行变更
    | DML: 设置 SAVEPOINT → 执行 DML → 验证 → 提交或回滚
    | DDL: 执行前最终确认 → 执行 DDL → 验证结果
    v
[5] 变更后验证
    | 验证变更结果（DESC / SELECT COUNT / 索引状态）
    | 输出回滚命令（DDL 反向操作 / DML 回滚 SAVEPOINT）
    v
[6] 结果输出
    | 结构化输出：操作类型 + 执行结果 + 验证 + 回滚命令
```

---

## 二、前置检查（只读 SQL）

### 2.1 数据库状态与版本

```sql
-- 数据库版本与状态
SELECT name AS db_name,
       open_mode,
       log_mode,
       database_role,
       flashback_on,
       TO_CHAR(current_scn) AS current_scn
FROM v$database;

-- 实例信息
SELECT instance_name,
       host_name,
       version_full,
       status,
       TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time
FROM v$instance;
```

### 2.2 回收站状态（影响 DROP TABLE 回滚能力）

```sql
-- 回收站开关状态
SELECT name AS db_name,
       value AS recyclebin_status
FROM v$parameter
WHERE name = 'recyclebin';

-- 当前回收站对象数量
SELECT COUNT(*) AS recyclebin_objects
FROM user_recyclebin;
```

### 2.3 目标对象检查

```sql
-- 检查表是否存在
SELECT owner, table_name, tablespace_name,
       num_rows, last_analyzed,
       ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb
FROM dba_tables
WHERE owner = UPPER('<schema>') AND table_name = UPPER('<table_name>');

-- 检查索引是否存在
SELECT owner, index_name, table_name, uniqueness, status
FROM dba_indexes
WHERE owner = UPPER('<schema>') AND table_name = UPPER('<table_name>');

-- 当前用户权限
SELECT * FROM session_privs;
```

### 2.4 DML 影响范围预估

```sql
-- 预估 UPDATE/DELETE 影响行数
SELECT COUNT(*) AS estimated_rows
FROM <schema>.<table_name>
WHERE <condition>;

-- 分批预估
SELECT CEIL(COUNT(*) / <batch_size>) AS estimated_batches,
       COUNT(*) AS total_rows
FROM <schema>.<table_name>
WHERE <condition>;

-- 当前活跃事务
SELECT COUNT(*) AS active_txns
FROM v$transaction;
```

---

## 三、DML 执行（带 SAVEPOINT 自动回滚）

### 3.1 DML 执行范式

```sql
-- DML 执行模板（Oracle PL/SQL 匿名块）
DECLARE
    v_total_rows   NUMBER := 0;
    v_batch_size   NUMBER := <batch_size>;  -- 分批大小，0 表示不分批
    v_timeout      NUMBER := <timeout_seconds>;
    v_start_time   TIMESTAMP;
BEGIN
    -- 设置超时与回滚点
    v_start_time := SYSTIMESTAMP;
    SAVEPOINT dml_sp;

    -- 执行 DML（示例：UPDATE）
    UPDATE <schema>.<table_name>
    SET <column> = <value>
    WHERE <condition>;

    v_total_rows := SQL%ROWCOUNT;
    DBMS_OUTPUT.PUT_LINE('受影响行数: ' || v_total_rows);

    -- 超时检查
    IF (SYSTIMESTAMP - v_start_time) > NUMTODSINTERVAL(v_timeout, 'SECOND') THEN
        ROLLBACK TO dml_sp;
        RAISE_APPLICATION_ERROR(-20001, 'DML 执行超时，已回滚到 SAVEPOINT');
    END IF;

    -- 自动回滚验证模式（auto_rollback=true）
    -- ROLLBACK TO dml_sp;  -- 取消注释以启用自动回滚
    -- COMMIT;              -- 取消注释以提交

    DBMS_OUTPUT.PUT_LINE('执行完成，受影响行数: ' || v_total_rows);
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK TO dml_sp;
        DBMS_OUTPUT.PUT_LINE('执行失败，已回滚: ' || SQLERRM);
        RAISE;
END;
/
```

### 3.2 INSERT 安全执行

```sql
-- 安全 INSERT（单条/批量）
BEGIN
    SAVEPOINT dml_sp;

    INSERT INTO <schema>.<table_name> (col1, col2, col3)
    VALUES (val1, val2, val3);

    DBMS_OUTPUT.PUT_LINE('INSERT 成功，行数: ' || SQL%ROWCOUNT);

    -- 验证
    -- SELECT * FROM <schema>.<table_name> WHERE ROWID = <插入行的ROWID>;

    -- 回滚: ROLLBACK TO dml_sp;
    -- 提交: COMMIT;
EXCEPTION
    WHEN DUP_VAL_ON_INDEX THEN
        ROLLBACK TO dml_sp;
        DBMS_OUTPUT.PUT_LINE('主键/唯一索引冲突，已回滚');
        RAISE;
    WHEN OTHERS THEN
        ROLLBACK TO dml_sp;
        DBMS_OUTPUT.PUT_LINE('INSERT 失败: ' || SQLERRM);
        RAISE;
END;
/
```

### 3.3 UPDATE 安全执行（分批提交）

```sql
-- 安全 UPDATE（分批提交，避免大事务）
DECLARE
    v_batch_size   NUMBER := 5000;
    v_total_rows   NUMBER := 0;
    v_batch_rows   NUMBER;
    v_batch_num    NUMBER := 0;
    v_timeout      NUMBER := <timeout_seconds>;
    v_start_time   TIMESTAMP;
BEGIN
    v_start_time := SYSTIMESTAMP;

    LOOP
        SAVEPOINT batch_sp;

        UPDATE <schema>.<table_name>
        SET <column> = <value>
        WHERE <condition>
          AND ROWNUM <= v_batch_size;

        v_batch_rows := SQL%ROWCOUNT;
        v_total_rows := v_total_rows + v_batch_rows;
        v_batch_num := v_batch_num + 1;

        COMMIT;

        DBMS_OUTPUT.PUT_LINE('批次 ' || v_batch_num || ' 完成，本批行数: ' || v_batch_rows);

        -- 超时检查
        IF (SYSTIMESTAMP - v_start_time) > NUMTODSINTERVAL(v_timeout, 'SECOND') THEN
            DBMS_OUTPUT.PUT_LINE('执行超时，已处理 ' || v_total_rows || ' 行');
            EXIT;
        END IF;

        EXIT WHEN v_batch_rows = 0;
    END LOOP;

    DBMS_OUTPUT.PUT_LINE('UPDATE 完成，总行数: ' || v_total_rows || '，批次: ' || v_batch_num);
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK TO batch_sp;
        DBMS_OUTPUT.PUT_LINE('批次 ' || v_batch_num || ' 失败，已回滚本批: ' || SQLERRM);
        RAISE;
END;
/
```

### 3.4 DELETE 安全执行（带数据备份）

```sql
-- 安全 DELETE（先备份受影响数据，再分批删除）
DECLARE
    v_batch_size   NUMBER := 5000;
    v_total_rows   NUMBER := 0;
    v_batch_rows   NUMBER;
BEGIN
    -- 备份受影响数据（用于误删恢复）
    SAVEPOINT backup_sp;

    -- 创建备份表（如不存在）
    BEGIN
        EXECUTE IMMEDIATE 'CREATE TABLE <schema>.<table_name>_bak_' ||
                          TO_CHAR(SYSDATE, 'YYYYMMDD_HH24MISS') ||
                          ' AS SELECT * FROM <schema>.<table_name> WHERE <condition>';
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLCODE != -955 THEN  -- ORA-00955: name already used
                RAISE;
            END IF;
    END;

    -- 分批删除
    LOOP
        SAVEPOINT batch_sp;

        DELETE FROM <schema>.<table_name>
        WHERE <condition>
          AND ROWNUM <= v_batch_size;

        v_batch_rows := SQL%ROWCOUNT;
        v_total_rows := v_total_rows + v_batch_rows;

        COMMIT;

        DBMS_OUTPUT.PUT_LINE('DELETE 批次完成，本批行数: ' || v_batch_rows);

        EXIT WHEN v_batch_rows = 0;
    END LOOP;

    DBMS_OUTPUT.PUT_LINE('DELETE 完成，总行数: ' || v_total_rows);
    DBMS_OUTPUT.PUT_LINE('备份表: <schema>.<table_name>_bak_<timestamp>');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK TO batch_sp;
        DBMS_OUTPUT.PUT_LINE('DELETE 失败: ' || SQLERRM);
        RAISE;
END;
/

-- 回滚方案：从备份表 INSERT 回原表
-- INSERT INTO <schema>.<table_name> SELECT * FROM <schema>.<table_name>_bak_<timestamp>;
-- COMMIT;
```

### 3.5 MERGE 安全执行

```sql
-- 安全 MERGE（UPSERT）
BEGIN
    SAVEPOINT dml_sp;

    MERGE INTO <schema>.<target_table> t
    USING (SELECT <key_col>, <col1>, <col2> FROM <source_table> WHERE <condition>) s
    ON (t.<key_col> = s.<key_col>)
    WHEN MATCHED THEN UPDATE
        SET t.<col1> = s.<col1>, t.<col2> = s.<col2>
    WHEN NOT MATCHED THEN INSERT (<key_col>, <col1>, <col2>)
        VALUES (s.<key_col>, s.<col1>, s.<col2>);

    DBMS_OUTPUT.PUT_LINE('MERGE 完成，受影响行数: ' || SQL%ROWCOUNT);

    -- 回滚: ROLLBACK TO dml_sp;
    -- 提交: COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK TO dml_sp;
        DBMS_OUTPUT.PUT_LINE('MERGE 失败: ' || SQLERRM);
        RAISE;
END;
/
```

---

## 四、DDL 执行（带反向 DDL 回滚）

### 4.1 DDL 回滚策略说明

Oracle 中 DDL 语句自动提交当前事务，无法通过 SAVEPOINT 回滚。本技能通过以下策略支持回退：

| DDL 类型 | 回滚策略 | 恢复方式 |
|----------|---------|---------|
| CREATE TABLE | 执行前检查是否存在，回滚用 DROP TABLE | DROP TABLE <table> PURGE; |
| ALTER TABLE（加列） | 执行前备份 DDL，回滚用 DROP COLUMN | ALTER TABLE <table> DROP COLUMN <col>; |
| ALTER TABLE（删列） | 执行前备份列数据，回滚用 ADD COLUMN + 数据恢复 | 从备份恢复 |
| ALTER TABLE（修改列） | 执行前备份 DDL，回滚用反向 ALTER | 反向 ALTER TABLE ... MODIFY |
| DROP TABLE | 使用 FLASHBACK TABLE（需回收站开启） | FLASHBACK TABLE <table> TO BEFORE DROP; |
| CREATE INDEX | 回滚用 DROP INDEX | DROP INDEX <index_name>; |
| DROP INDEX | 回滚用 CREATE INDEX（需保存 DDL） | 重新创建索引 |
| TRUNCATE TABLE | **不可回滚**（Oracle 不支持 FLASHBACK 恢复 TRUNCATE 数据） | 只能从备份恢复 |

### 4.2 变更前 DDL 备份

```sql
-- 获取当前表 DDL（用于回滚）
SET LONG 100000
SET PAGESIZE 0
SELECT DBMS_METADATA.GET_DDL('TABLE', '<table_name>', '<schema>') FROM DUAL;

-- 获取当前索引 DDL
SELECT DBMS_METADATA.GET_DDL('INDEX', '<index_name>', '<schema>') FROM DUAL;

-- 保存表行数（变更前快照）
SELECT COUNT(*) FROM <schema>.<table_name>;
```

### 4.3 CREATE TABLE（可回滚：DROP TABLE）

```sql
-- 执行前检查：表是否已存在
SELECT owner, table_name FROM dba_tables
WHERE owner = UPPER('<schema>') AND table_name = UPPER('<table_name>');

-- 执行 CREATE TABLE
CREATE TABLE <schema>.<table_name> (
    id          NUMBER(18) PRIMARY KEY,
    name        VARCHAR2(200) NOT NULL,
    status      VARCHAR2(20) DEFAULT 'ACTIVE',
    create_time DATE DEFAULT SYSDATE
) TABLESPACE <tablespace_name>;

-- 验证
SELECT table_name, num_rows FROM dba_tables
WHERE owner = UPPER('<schema>') AND table_name = UPPER('<table_name>');

-- 回滚 DDL
DROP TABLE <schema>.<table_name> PURGE;
```

### 4.4 ALTER TABLE 加列（可回滚：DROP COLUMN）

```sql
-- 执行前备份 DDL
-- SELECT DBMS_METADATA.GET_DDL('TABLE', '<table_name>', '<schema>') FROM DUAL;

-- 执行 ALTER TABLE 加列
ALTER TABLE <schema>.<table_name>
ADD (<new_col> VARCHAR2(100) DEFAULT NULL);

-- 验证
DESC <schema>.<table_name>;

-- 回滚 DDL
ALTER TABLE <schema>.<table_name> DROP COLUMN <new_col>;
```

### 4.5 ALTER TABLE 删列（可回滚：从备份恢复）

```sql
-- 执行前备份：保存被删列数据
CREATE TABLE <schema>.<table_name>_col_bak_<timestamp> AS
SELECT <pk_col>, <col_to_drop> FROM <schema>.<table_name>;

-- 执行 ALTER TABLE 删列
ALTER TABLE <schema>.<table_name> DROP COLUMN <col_to_drop>;

-- 验证
DESC <schema>.<table_name>;

-- 回滚方案：
-- ALTER TABLE <schema>.<table_name> ADD (<col_to_drop> <original_type>);
-- MERGE INTO <schema>.<table_name> t
-- USING <schema>.<table_name>_col_bak_<timestamp> s
-- ON (t.<pk_col> = s.<pk_col>)
-- WHEN MATCHED THEN UPDATE SET t.<col_to_drop> = s.<col_to_drop>;
-- COMMIT;
```

### 4.6 ALTER TABLE 修改列属性（可回滚：反向 MODIFY）

```sql
-- 执行前备份 DDL
-- SELECT DBMS_METADATA.GET_DDL('TABLE', '<table_name>', '<schema>') FROM DUAL;

-- 执行 ALTER TABLE 修改列
ALTER TABLE <schema>.<table_name>
MODIFY (<column> VARCHAR2(200));

-- 验证
DESC <schema>.<table_name>;

-- 回滚 DDL（反向 MODIFY）
-- ALTER TABLE <schema>.<table_name> MODIFY (<column> VARCHAR2(100));
```

### 4.7 DROP TABLE（可回滚：FLASHBACK TABLE）

```sql
-- 执行前确认回收站已开启
SHOW PARAMETER recyclebin;

-- 执行 DROP TABLE（不加 PURGE，保留在回收站）
DROP TABLE <schema>.<table_name>;

-- 验证：表是否在回收站中
SELECT original_name, object_name, type, droptime
FROM user_recyclebin
WHERE original_name = UPPER('<table_name>');

-- 回滚：FLASHBACK TABLE（恢复表及其数据）
FLASHBACK TABLE <schema>.<table_name> TO BEFORE DROP;

-- 回滚：FLASHBACK TABLE 并重命名（原表名已存在时）
FLASHBACK TABLE <schema>.<table_name> TO BEFORE DROP RENAME TO <table_name>_recovered;
```

### 4.8 CREATE INDEX（可回滚：DROP INDEX）

```sql
-- 执行前检查：索引是否已存在
SELECT owner, index_name, table_name, uniqueness
FROM dba_indexes
WHERE owner = UPPER('<schema>') AND index_name = UPPER('<index_name>');

-- 执行 CREATE INDEX
CREATE INDEX <index_name> ON <schema>.<table_name> (<column_list>)
TABLESPACE <tablespace_name>;

-- 验证
SELECT index_name, status FROM dba_indexes
WHERE owner = UPPER('<schema>') AND index_name = UPPER('<index_name>');

-- 回滚 DDL
DROP INDEX <schema>.<index_name>;
```

### 4.9 TRUNCATE TABLE（不可回滚，需二次确认）

```sql
-- ❗ 高风险：TRUNCATE 不可回滚（Oracle 的 FLASHBACK 不支持 TRUNCATE 恢复）
-- 执行前必须：
-- 1. 确认已有有效备份
-- 2. 二次确认（用户明确同意）
-- 3. 如有条件，先导出数据

-- 执行前备份（可选但强烈建议）
-- expdp <schema>/<password> TABLES=<schema>.<table_name> DIRECTORY=DATA_PUMP_DIR DUMPFILE=<table_name>_<timestamp>.dmp

-- 执行 TRUNCATE
TRUNCATE TABLE <schema>.<table_name>;

-- 验证
SELECT COUNT(*) FROM <schema>.<table_name>;  -- 应为 0

-- 回滚方案：仅能从备份恢复
-- impdp <schema>/<password> TABLES=<schema>.<table_name> DIRECTORY=DATA_PUMP_DIR DUMPFILE=<table_name>_<timestamp>.dmp TABLE_EXISTS_ACTION=TRUNCATE
```

---

## 五、变更前安全检查清单

| 检查项 | 检查方式 | 通过标准 |
|--------|----------|----------|
| 数据库状态 | `SELECT open_mode FROM v$database;` | READ WRITE |
| 归档模式 | `SELECT log_mode FROM v$database;` | ARCHIVELOG（生产库） |
| 备份 | 确认最近备份 | 24h 内有有效备份 |
| 回收站 | `SELECT value FROM v$parameter WHERE name='recyclebin';` | ON（DROP TABLE 回滚需要） |
| 目标对象存在性 | `SELECT table_name FROM dba_tables WHERE ...` | 确认操作对象存在/不存在 |
| 权限 | `SELECT * FROM session_privs;` | 具备所需权限（CREATE TABLE/ANY TABLE 等） |
| DML 影响行数 | `SELECT COUNT(*) FROM <table> WHERE <condition>;` | 明确影响范围 |
| 活跃事务 | `SELECT COUNT(*) FROM v$transaction;` | < 10 |
| 表空间余量 | `SELECT tablespace_name, ROUND(SUM(bytes)/1024/1024/1024,2) AS free_gb FROM dba_free_space GROUP BY tablespace_name;` | 足够空间 |

---

## 六、变更后验证

```sql
-- DDL 变更后验证
-- 表结构验证
DESC <schema>.<table_name>;

-- 索引状态验证
SELECT index_name, status FROM dba_indexes
WHERE owner = UPPER('<schema>') AND table_name = UPPER('<table_name>');

-- 对象状态验证
SELECT object_name, object_type, status FROM dba_objects
WHERE owner = UPPER('<schema>')
  AND object_name IN (UPPER('<table_name>'), UPPER('<index_name>'));

-- DML 变更后验证
-- 行数验证
SELECT COUNT(*) FROM <schema>.<table_name> WHERE <condition>;

-- 数据一致性抽样
SELECT * FROM <schema>.<table_name> WHERE <condition> AND ROWNUM <= 10;
```

---

## 七、Dry Run 模式（试运行）

当 `dry_run=true` 时，本技能仅解析 SQL 并输出回滚方案，不实际执行：

```
=== Dry Run 报告 ===
SQL 类型: DDL (ALTER TABLE)
操作对象: SCHEMA.ORDERS
操作内容: ADD COLUMN (remark VARCHAR2(500))

--- 前置检查 ---
表存在: YES
表大小: 2.5 GB (行数: 8,500,000)
表空间余量: USERS 表空间剩余 120 GB
回收站: ON

--- 影响评估 ---
预估耗时: < 1 秒（仅修改数据字典，实际数据无变化）
锁级别: 表级排他锁（DDL 锁），执行期间该表 DML 阻塞
风险等级: 低

--- 回滚方案 ---
ALTER TABLE SCHEMA.ORDERS DROP COLUMN remark;

--- 建议 ---
1. 建议在业务低峰期执行
2. 执行前确认无长事务持有该表锁
3. 加列无默认值时 INSTANT 完成，有默认值且 NOT NULL 列可能耗时较长
```

---

## 八、异常处理

| 异常场景 | 处理方式 |
|----------|---------|
| ORA-00955: 名称已存在 | DDL 中断，提示对象已存在，检查是否需要先删除或改名 |
| ORA-00942: 表或视图不存在 | DDL/DML 中断，提示对象不存在，检查 schema 与表名是否正确 |
| ORA-00001: 唯一约束冲突 | DML 自动回滚到 SAVEPOINT，提示冲突值 |
| ORA-00054: 资源正忙 | DDL 等待超时，提示存在锁持有者，建议低峰期重试 |
| ORA-01555: 快照太旧 | DML 中断，提示 undo 表空间不足，建议减小 commit_batch_size |
| ORA-30036: undo 表空间不足 | DML 中断，提示增大 undo 表空间或减小分批大小 |
| DML 执行超时 | 自动回滚到 SAVEPOINT，提示已处理行数，建议调整 timeout_seconds 或 commit_batch_size |
| TRUNCATE 不可回滚 | 执行前强制二次确认，提示从备份恢复的方案 |
| 权限不足 | 中断操作，提示缺失的具体权限 |
| 表空间不足 | DDL 中断，提示释放空间或扩展表空间 |

---

## 九、输出格式

结构化输出：
1. **SQL 解析结果**：SQL 类型（DDL/DML）、操作对象、操作内容
2. **前置检查结果**：数据库状态、对象存在性、权限、影响行数预估
3. **回滚信息**：备份的 DDL / 受影响行数 / 备份表名
4. **执行结果**：成功/失败、耗时、受影响行数（DML）、批次信息
5. **变更后验证**：表结构/索引状态/数据一致性
6. **回滚命令**：可执行的回滚 SQL（DDL 反向操作 / DML 数据恢复方案）