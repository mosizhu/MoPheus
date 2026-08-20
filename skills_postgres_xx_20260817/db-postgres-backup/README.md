# db-postgres-backup

PostgreSQL 备份执行技能（高危变更）。

## 功能概述

实际执行 PostgreSQL 备份操作：逻辑备份（pg_dump/pg_dumpall）、物理备份（pg_basebackup）、WAL 归档与备份校验。区别于 `db-postgres-plan-backup`（备份策略设计），本技能实际执行备份命令并校验结果。自包含、单一职责。

## 备份类型

| 类型 | 工具 | 适用场景 | 特点 |
|------|------|---------|------|
| 逻辑全库备份 | pg_dump -Fc | 单库备份，可选择性恢复 | 支持并行恢复，压缩好 |
| 逻辑全实例备份 | pg_dumpall | 全局对象 + 所有库 | 包含角色、表空间 |
| 物理全量备份 | pg_basebackup | 实例级备份，恢复最快 | 块级复制，速度快 |
| WAL 归档 | archive_command | 增量备份，PITR | 支持时间点恢复 |

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instance_host | string | 是 | - | 目标 PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | 空 | 目标数据库名（不填则备份所有数据库或实例级备份） |
| backup_type | string | 是 | - | 备份类型：pg_dump / pg_dumpall / pg_basebackup / wal_archive |
| backup_dir | string | 是 | - | 备份文件存储目录（绝对路径） |
| format | string | 否 | custom | 逻辑备份格式：custom / plain / directory / tar |
| parallel_jobs | integer | 否 | 2 | 并行度 |
| compression_level | integer | 否 | 5 | 压缩级别（0-9） |
| dry_run | boolean | 否 | true | 是否仅预览备份计划 |

## 安全级别

`dangerous` - 实际执行备份操作，但默认 dry_run=true 仅预览。

## 关联技能

- `db-postgres-restore` - 恢复执行
- `db-postgres-plan-backup` - 备份策略设计
