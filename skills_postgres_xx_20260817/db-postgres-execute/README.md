# db-postgres-execute

PostgreSQL DDL/DML 执行技能（可控变更）。执行表结构变更、索引管理、约束管理、视图与 SCHEMA 管理，以及安全数据订正（INSERT/UPSERT/UPDATE/DELETE）。

## 功能概述

本技能负责实际执行 PostgreSQL DDL 与 DML 操作，覆盖建表/改表/删表、索引创建与删除、约束管理、视图与 SCHEMA 管理、TRUNCATE，以及安全数据订正（INSERT/UPSERT/UPDATE/DELETE）。所有变更操作默认 dry_run=true（仅预估不执行），严守出厂红线：DELETE 前必备份、TRUNCATE/DROP 前先备份、大表 DDL 需评估风险。自包含、单一职责。

## DDL 操作覆盖

| 操作 | 说明 | 风险等级 |
|------|------|---------|
| CREATE TABLE | 建表（含列定义、注释） | 低 |
| ALTER TABLE（加列） | 添加列 | 低-中 |
| ALTER TABLE（删列） | 删除列 | 中 |
| ALTER TABLE（改列类型） | 修改列类型 | 高 |
| ALTER TABLE（重命名） | 重命名列/表 | 低 |
| DROP TABLE | 删除表 | 极高 |
| CREATE INDEX | 创建索引（含 CONCURRENTLY） | 低-中 |
| DROP INDEX | 删除索引（含 CONCURRENTLY） | 低 |
| 约束管理 | 主键/外键/唯一/CHECK/NOT NULL | 低-中 |
| CREATE VIEW | 创建视图 | 低 |
| SCHEMA 管理 | 创建/删除 SCHEMA | 中-极高 |
| TRUNCATE | 清空表数据 | 极高 |

## DML 操作覆盖

| 操作 | 说明 | 风险等级 |
|------|------|---------|
| INSERT | 插入数据（单行/批量） | 低 |
| UPSERT | INSERT ... ON CONFLICT | 低 |
| UPDATE | 更新数据（必带 WHERE） | 中 |
| DELETE | 删除数据（必带 WHERE，先备份） | 高 |
| SELECT | 数据查询与影响预估 | 查询级 |

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instance_host | string | 是 | - | PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | 空 | 目标数据库名 |
| schema_name | string | 否 | 空 | 目标 SCHEMA 名（默认 public） |
| table_name | string | 否 | 空 | 目标表名 |
| sql_text | string | 否 | 空 | 待执行的 DDL/DML 语句 |
| operation | string | 否 | 空 | 操作类型：ddl_create_table / ddl_alter_table / ddl_drop_table / ddl_create_index / ddl_drop_index / ddl_create_schema / ddl_truncate / dml_insert / dml_upsert / dml_update / dml_delete / dml_select |
| batch_size | integer | 否 | 1000 | 批量 DML 操作每批处理行数 |
| dry_run | boolean | 否 | true | 是否仅预估影响范围不实际执行变更 |

## 触发话术

- "创建一张 users 表"
- "给 orders 表添加一个 status 列"
- "在 orders 表的 user_id 列上创建索引"
- "删除 products 表的多余索引"
- "给 users 表添加唯一约束"
- "插入一条新记录到 users 表"
- "批量更新 orders 表中 status = 'pending' 的数据"
- "安全删除 90 天前的日志数据"
- "查看 orders 表的数据分布"
- "预估 UPDATE 操作的影响行数"

## 输出示例

```text
=== PostgreSQL DDL/DML 执行报告 ===
实例: 192.168.1.100:5432 | 数据库: mydb | SCHEMA: public
操作类型: ddl_create_index | 模式: 实际执行
执行时间: 2026-08-18 14:30:00

## 前置检查
[✓] 实例连通性检查通过
[✓] 备份确认通过（24h 内有备份）
[✓] 活跃事务: 3（< 10）
[✓] 锁等待: 0（= 0）
[✓] 长事务: 0（= 0）

## 影响预估
目标表: public.orders
表大小: 256MB
预计影响行数: 0（DDL 不变更数据）
预计耗时: < 30s

## 执行结果
SQL: CREATE INDEX CONCURRENTLY idx_orders_user_id ON public.orders (user_id);
状态: 成功
影响行数: 0
耗时: 12.5s

## 后置验证
[✓] 索引创建成功: idx_orders_user_id
[✓] 表结构验证通过

## 回滚方案
回滚 SQL: DROP INDEX CONCURRENTLY idx_orders_user_id;
```

## 安全边界

- 本技能安全等级为 modify（tags: db-modify），执行 DDL/DML 变更。
- 严守出厂红线：不执行 DROP DATABASE/TABLESPACE/EXTENSION 等破坏性操作。
- 所有变更操作默认 dry_run=true，需显式设置 dry_run=false 才实际执行。
- DELETE 操作前必须先备份（CREATE TABLE _bak AS SELECT），且必带 WHERE 条件。
- TRUNCATE/DROP TABLE 前必须先备份，双重确认后执行。
- 大表 DDL（> 1GB）会提示评估风险，建议使用 CONCURRENTLY 或低峰期执行。
- 不修改会话/全局配置参数、不执行 KILL/GRANT/REVOKE。
- 所有操作前有检查清单、后有验证、可追溯。

## 功能限制

- 不执行 DROP DATABASE / DROP TABLESPACE / DROP EXTENSION
- 不修改会话或全局配置参数（SET / ALTER SYSTEM）
- 不执行 KILL / GRANT / REVOKE / CREATE ROLE / DROP ROLE
- 不执行 VACUUM / ANALYZE / REINDEX（由专项技能负责）
- 不调用其他 Skill，低耦合、自包含

## 关联技能

- `db-postgres-inspect` - 基础巡检（变更前健康检查）
- `db-postgres-diagnose-deadlock` - 死锁诊断（变更前锁等待分析）
- `db-postgres-diagnose-perf` - 综合性能诊断（变更后性能验证）
- `db-postgres-backup` - 备份执行（变更前备份保障）
- `db-postgres-plan-tuning` - 性能调优方案（索引创建后验证效果）

## 版本记录

- v1.0.0（2026-08-18）：初始版本，按出厂标准化规范创建。覆盖 DDL（建表/改表/删表/索引/约束/视图/SCHEMA/TRUNCATE）与 DML（INSERT/UPSERT/UPDATE/DELETE），含安全检查清单、影响预估、变更后验证、回滚方案。

## 变更类型说明

| 操作 | 变更级别 | 说明 |
|------|---------|------|
| ddl_create_table | modify | 创建新表，无风险 |
| ddl_alter_table | modify | 修改表结构，大表需评估风险 |
| ddl_drop_table | modify | 删除表，红线操作，须先备份 |
| ddl_create_index | modify | 创建索引，使用 CONCURRENTLY 不锁表 |
| ddl_drop_index | modify | 删除索引 |
| ddl_create_schema | modify | 创建 SCHEMA |
| ddl_truncate | modify | 清空表数据，不可回滚，须先备份 |
| dml_insert | modify | 插入数据 |
| dml_upsert | modify | 插入或更新 |
| dml_update | modify | 更新数据，必带 WHERE |
| dml_delete | modify | 删除数据，须先备份且必带 WHERE |
| dml_select | query | 仅查询，不修改数据 |