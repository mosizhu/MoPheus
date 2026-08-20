# db-postgres-diagnose-deadlock

PostgreSQL 死锁诊断分析技能（只读）。

## 功能概述

基于 `pg_locks`、`pg_stat_activity`、PostgreSQL 死锁日志、锁模式冲突矩阵，定位死锁根因与锁等待阻塞链，给出预防建议。只读操作，不执行任何变更。

## 诊断维度

| 维度 | 诊断内容 | 风险等级 |
|------|---------|---------|
| 实时锁等待 | 当前锁等待关系与阻塞源 | 高 |
| 阻塞链检测 | 从被阻塞会话向上追溯所有阻塞源 | 高 |
| 死锁日志解析 | 从 PostgreSQL 日志中提取死锁详情 | 高 |
| 长事务排查 | 长时间未提交的事务持有锁 | 中 |
| 空闲事务 | idle in transaction 持有锁 | 中 |
| DDL 互锁 | ALTER TABLE 等 DDL 阻塞诊断 | 高 |
| 咨询锁冲突 | pg_advisory_lock 冲突排查 | 中 |

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instance_host | string | 是 | - | PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | 空 | 目标数据库名 |
| log_file_path | string | 否 | 空 | PostgreSQL 日志文件路径 |
| min_duration_sec | integer | 否 | 5 | 锁等待最小持续时间阈值（秒） |
| deadlock_log_lines | integer | 否 | 200 | 从日志文件尾部读取的行数 |

## 安全级别

`query` - 只读操作，不终止任何连接或事务。

## 关联技能

- `db-postgres-diagnose-perf` - 综合性能诊断
- `db-postgres-inspect` - 基础巡检
