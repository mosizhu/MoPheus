---
name: "db-postgres-audit-permission"
description: "PostgreSQL 权限审计技能（只读）。核心能力：对 PostgreSQL 实例进行全面的权限审计——角色权限、对象权限、默认权限、行级安全策略（RLS）、schema 权限、数据库权限、表空间权限、函数权限。输出审计报告与合规建议。适用场景：安全合规审计、权限排查、角色权限梳理、最小权限原则验证、数据泄露风险评估。功能限制：只读操作，不修改任何权限、角色或配置；不执行 GRANT/REVOKE/ALTER ROLE 等变更；不调用其他 Skill，低耦合、自包含。"
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
    desc: "审计范围：all（全部）/ roles（仅角色）/ objects（仅对象权限）/ rls（仅行级安全）/ defaults（仅默认权限）"
support_db: postgresql
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-18"
---

# PostgreSQL 权限审计

> 对 PostgreSQL 实例进行全面的权限审计，覆盖角色、对象、默认权限、RLS 策略等所有维度，输出审计报告与合规建议。本技能为 query 级只读操作。自包含。

## 核心能力
- 单一职责：PostgreSQL 权限审计（只读扫描 + 报告 + 合规建议）。
- 角色与成员审计：角色列表、超级用户、角色属性、成员关系。
- 对象权限审计：表/列/序列/函数的授予权限。
- 默认权限审计：未来对象默认权限。
- 行级安全审计：RLS 启用状态与策略定义。

## 适用场景
- 安全合规审计、权限排查、最小权限原则验证

## 功能限制
- 只读操作，不执行任何权限变更
- 不调用其他 Skill，低耦合、自包含

## 执行逻辑
1. 角色审计 2. 对象权限审计 3. 默认权限审计 4. RLS 策略审计 5. 输出报告

## 角色审计

```sql
SELECT rolname, rolsuper, rolcreatedb, rolcanlogin
FROM pg_roles ORDER BY rolsuper DESC, rolname;
```

## 对象权限审计

```sql
SELECT grantee, table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name, grantee;
```

## 输出格式

```text
=== PostgreSQL 权限审计报告 ===
实例: <instance_host> | 审计范围: <audit_scope>

## 角色审计
- 角色总数: <count>
- 超级用户: <list>

## 风险评估
[高] 超级用户过多
```
