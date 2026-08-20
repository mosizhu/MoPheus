---
name: "db-postgres-audit-sql"
description: "PostgreSQL SQL 审计技能（只读）。核心能力：对 PostgreSQL 实例进行 SQL 与 DDL 审计——慢查询捕获、异常 SQL 模式检测、DDL 变更历史、连接审计、对象变更审计。输出审计报告与风险建议。适用场景：安全合规审计、SQL 异常排查、变更追溯、违规操作检测、数据泄露溯源。功能限制：只读操作，不修改任何数据或配置；依赖 pg_stat_statements 扩展；不调用其他 Skill，低耦合、自包含。"
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
    desc: "目标数据库名（可选，不填则审计所有数据库）"
  - name: "audit_scope"
    type: "string"
    required: false
    default: "all"
    desc: "审计范围"
  - name: "time_range_hours"
    type: "integer"
    required: false
    default: 24
    desc: "审计时间范围（小时）"
support_db: postgresql
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-18"
---

# PostgreSQL SQL 审计

> 对 PostgreSQL 实例进行 SQL 与 DDL 审计，捕获慢查询、异常 SQL 模式、DDL 变更历史、连接审计。本技能为 query 级只读操作。自包含。

## 核心能力
- 单一职责：PostgreSQL SQL 审计（只读扫描 + 报告）。
- 慢查询审计：基于 pg_stat_statements 的历史慢查询统计。
- DDL 变更审计：基于事件触发器的 DDL 变更历史。
- 连接审计：连接来源、频率、时长。

## 适用场景
- 安全合规审计、SQL 异常排查、变更追溯

## 功能限制
- 只读操作，不修改任何数据或配置
- 依赖 pg_stat_statements 扩展

## 执行逻辑
1. 检查扩展 2. 慢查询审计 3. DDL 变更审计 4. 连接审计 5. 输出报告

## 慢查询审计

```sql
SELECT queryid, LEFT(query, 200) AS query_preview, calls,
       ROUND(total_exec_time::numeric, 2) AS total_time_ms
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 10;
```

## 输出格式

```text
=== PostgreSQL SQL 审计报告 ===
实例: <instance_host> | 审计范围: <audit_scope>

## 慢查询审计
- Top 10 最耗时查询: ...

## 建议
1. 优化慢查询
```
