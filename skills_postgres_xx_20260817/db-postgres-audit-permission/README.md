# db-postgres-audit-permission

PostgreSQL 权限审计技能（只读）。

## 功能概述

对 PostgreSQL 实例进行全面的权限审计，覆盖角色权限、对象权限、默认权限、行级安全策略（RLS）、schema 权限、数据库权限、表空间权限、函数权限。输出审计报告与合规建议。自包含，只读操作。

## 审计维度

| 维度 | 审计内容 | 风险等级 |
|------|---------|---------|
| 角色与成员 | 角色列表、超级用户、角色成员关系、角色属性 | 高 |
| 数据库权限 | CONNECT / CREATE / TEMP 权限 | 中 |
| Schema 权限 | schema 的 CREATE / USAGE 权限 | 中 |
| 表权限 | SELECT / INSERT / UPDATE / DELETE / TRUNCATE / REFERENCES / TRIGGER | 高 |
| 列权限 | 列级 SELECT / INSERT / UPDATE / REFERENCES | 高 |
| 序列权限 | USAGE / SELECT / UPDATE 权限 | 中 |
| 函数权限 | EXECUTE 权限 | 中 |
| 默认权限 | 未来对象默认权限 | 中 |
| 行级安全 | RLS 启用状态与策略定义 | 高 |

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instance_host | string | 是 | - | 目标 PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | 空 | 目标数据库名（不填则审计所有数据库） |
| audit_scope | string | 否 | all | 审计范围：all / roles / objects / rls / defaults |

## 安全级别

`query` - 只读操作，不修改任何权限或配置。

## 关联技能

- `db-postgres-inspect` - 基础巡检（互补，巡检侧重性能与配置，本技能侧重权限合规）
