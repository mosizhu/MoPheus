# db-postgres-audit-sql

PostgreSQL SQL 审计技能（只读）。

## 功能概述

对 PostgreSQL 实例进行 SQL 与 DDL 审计，捕获慢查询、异常 SQL 模式、DDL 变更历史、连接审计、对象变更审计。输出审计报告与风险建议。自包含，只读操作。

## 审计维度

| 维度 | 审计内容 | 风险等级 |
|------|---------|---------|
| 慢查询审计 | 历史慢查询记录与统计 | 中 |
| DDL 变更审计 | 表/索引/视图/函数修改历史 | 高 |
| 连接审计 | 连接来源、频率、时长 | 中 |
| 对象变更审计 | 表结构、索引、约束变更 | 高 |
| 异常 SQL 模式 | 全表扫描、笛卡尔积、频繁重复查询 | 中 |

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instance_host | string | 是 | - | 目标 PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | 空 | 目标数据库名（不填则审计所有数据库） |
| audit_scope | string | 否 | all | 审计范围：all / slow_query / ddl / connection / object_change |
| time_range_hours | integer | 否 | 24 | 审计时间范围（小时） |

## 安全级别

`query` - 只读操作，不修改任何数据或配置。

## 关联技能

- `db-postgres-diagnose-slow-query` - 慢查询诊断
- `db-postgres-inspect` - 基础巡检
