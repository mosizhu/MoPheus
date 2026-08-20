---
name: "db-postgres-backup"
description: "PostgreSQL 备份执行技能（高危变更）。核心能力：逻辑备份（pg_dump/pg_dumpall）、物理备份（pg_basebackup）、WAL 归档配置与备份校验。适用场景：日常备份执行、上线前/变更前全量备份、灾备演练、WAL 归档配置。功能限制：默认 dry_run=true 仅预览；备份前必须校验磁盘空间；不执行备份恢复。"
version: "v1.0.0"
tags: db-ops
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 PostgreSQL 实例地址（host:port）"
  - name: "db_name"
    type: "string"
    required: false
    default: ""
    desc: "目标数据库名"
  - name: "backup_type"
    type: "string"
    required: true
    default: ""
    desc: "备份类型：pg_dump / pg_dumpall / pg_basebackup / wal_archive"
  - name: "backup_dir"
    type: "string"
    required: true
    default: ""
    desc: "备份文件存储目录"
  - name: "format"
    type: "string"
    required: false
    default: "custom"
    desc: "逻辑备份格式"
  - name: "parallel_jobs"
    type: "integer"
    required: false
    default: 2
    desc: "并行度"
  - name: "compression_level"
    type: "integer"
    required: false
    default: 5
    desc: "压缩级别（0-9）"
  - name: "dry_run"
    type: "boolean"
    required: false
    default: true
    desc: "是否仅预览备份计划"
support_db: postgresql
safe_level: "dangerous"
author: "团队出厂预置"
update_time: "2026-08-18"
---

# PostgreSQL 备份执行

> 实际执行 PostgreSQL 备份操作：逻辑备份（pg_dump/pg_dumpall）、物理备份（pg_basebackup）、WAL 归档。默认 dry_run=true 仅预览。自包含。

## 核心能力
- 单一职责：PostgreSQL 备份执行。
- 逻辑备份执行：pg_dump 自定义格式/plain/目录/tar。
- 物理备份执行：pg_basebackup 全量物理备份。
- WAL 归档配置：archive_command 配置。
- 备份校验：pg_verifybackup 验证物理备份完整性。

## 适用场景
- 日常备份、上线前备份、灾备演练、WAL 归档配置

## 功能限制
- 默认 dry_run=true，仅预览备份命令
- 备份前必须校验磁盘空间充足
- 不执行备份恢复、不设计备份策略

## 执行逻辑
1. 前置检查（磁盘空间、权限、连通性）
2. 备份预览（dry_run）
3. 执行备份（dry_run=false）
4. 后置校验

## 逻辑备份（pg_dump）

```bash
pg_dump -h <host> -p <port> -U <user> \
  -d <db_name> --format=custom --compress=<compression_level> \
  --verbose --no-owner --no-privileges \
  -f <backup_dir>/<db_name>_$(date +%Y%m%d_%H%M%S).dump
```

## 物理备份（pg_basebackup）

```bash
pg_basebackup -h <host> -p <port> -U <user> \
  -D <backup_dir>/pg_basebackup_$(date +%Y%m%d_%H%M%S) \
  --format=plain --progress --verbose --checkpoint=fast
```

## 输出格式

```text
=== PostgreSQL 备份执行报告 ===
实例: <instance_host> | 数据库: <db_name>
备份类型: <backup_type> | 格式: <format>
状态: <成功/失败>
备份文件: <backup_file_path>
```
