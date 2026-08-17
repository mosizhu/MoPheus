# Oracle 账号权限审计 说明文档

## 能力简介
本技能对 Oracle 数据库账号权限执行纯只读扫描审计，覆盖五大维度：账号状态（锁定/过期/默认密码/SYSDBA 特权/代理用户）、系统权限（高危权限/ANY 类权限/管理权限）、角色权限（角色分配/递归继承/高危角色）、对象权限（表级/列级/系统包 EXECUTE/DIRECTORY 目录/PUBLIC 权限）、口令策略（Profile 密码策略/资源限制/密码复杂度校验），对照最小权限角色基线输出越权风险清单与整改建议。本技能为纯只读扫描，不执行任何账号创建/删除/密码重置/锁定解锁/权限变更操作。

## 适用场景
- 定期账号权限审计（月度/季度/年度安全巡检）
- 安全基线对标检查（等保2.0 / ISO 27001 / SOC2）
- 权限越权筛查与最小权限整改准备
- 合规预检与审计证据准备
- 离职/转岗人员权限回收确认
- 高危权限清理前盘点
- 新系统上线前权限安全评审

## 触发话术
- "审计一下 Oracle 数据库的账号权限"
- "扫描所有 Oracle 账号的安全风险和权限越权情况"
- "检查是否有账号使用默认密码"
- "审计一下哪些账号有 DBA 角色"
- "看看有没有账号拥有 ALTER SYSTEM 或者 ANY 类高危权限"
- "检查一下口令策略是否符合安全基线"
- "做一次 Oracle 账号权限安全基线检查"
- "帮我审计 Oracle 数据库的权限分布，生成合规报告"
- "检查一下有没有不需要的 SYSDBA 特权账号"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| username | string | 否 | | 指定审计用户名（可选，为空则审计全部非系统账号） |
| audit_scope | string | 否 | all | 审计范围：all（全部）/ account（仅账号状态）/ privilege（仅权限）/ policy（仅口令策略） |
| include_sys | boolean | 否 | false | 是否包含 Oracle 内置系统账号（SYS/SYSTEM/DBSNMP 等），默认仅审计业务账号 |

## 输出示例

```
=== Oracle 账号权限审计报告 ===
实例: 192.168.1.100:1521/orcl
审计范围: all
审计时间: 2026-08-17 12:00:00
Oracle 版本: 19c

--- 综合安全评分: 58 / 100（越高越安全）---

=== 一、账号状态审计 ===
[高] 发现 2 个账号使用默认密码（SCOTT, HR）→ 建议立即修改密码或锁定
[中] 账号 APP_USER 状态为 EXPIRED(GRACE) → 密码将在 5 天后过期
[中] 生产环境存在测试账号 TEST_DEV → 建议锁定或删除
[低] 账号 OLD_ADMIN 状态为 LOCKED → 建议确认是否可删除

=== 二、系统权限审计 ===
[高] 账号 APP_ADMIN 拥有 ALTER SYSTEM 权限 → 建议回收
[高] 账号 REPORT_USER 拥有 SELECT ANY TABLE 权限 → 建议改为按需授权
[高] 账号 ETL_USER 拥有 UNLIMITED TABLESPACE 权限 → 建议设置表空间配额

=== 三、角色权限审计 ===
[高] 账号 APP_ADMIN 持有 DBA 角色（DEFAULT_ROLE=YES）→ 权限过大
[高] 账号 SVC_ACCOUNT 持有 SELECT_CATALOG_ROLE 角色 → 可查看数据字典

=== 四、对象权限审计 ===
[高] 账号 APP_USER 拥有 UTL_FILE 包 EXECUTE 权限 → 可读写服务器文件
[中] 账号 REPORT_USER 对 HR.EMPLOYEES.SALARY 有 UPDATE 权限 → 薪资列敏感
[中] PUBLIC 拥有 UTL_HTTP 包 EXECUTE 权限 → 所有用户可发起 HTTP 请求

=== 五、口令策略审计 ===
[高] DEFAULT Profile 未启用 PASSWORD_VERIFY_FUNCTION → 12 个账号无密码复杂度要求
[中] Profile APP_PROFILE 的 FAILED_LOGIN_ATTEMPTS 设为 UNLIMITED → 暴力破解风险
```

## 审计维度详情

### 账号状态审计（10+ 检查项）
- 账号列表与基本信息（用户名、默认表空间、Profile、认证方式）
- 账号状态检测（OPEN / LOCKED / EXPIRED / EXPIRED(GRACE)）
- 默认密码检测（DBA_USERS_WITH_DEFPWD）
- SYSDBA / SYSOPER 特权账户盘点（V$PWFILE_USERS）
- 代理用户（Proxy User）审计
- 测试/演示/临时账号识别
- 僵尸账号（长期未登录）检测

### 系统权限审计（15+ 检查项）
- 高危系统权限筛查（ALTER SYSTEM/ALTER DATABASE/GRANT ANY PRIVILEGE/UNLIMITED TABLESPACE 等）
- ANY 类权限盘点（SELECT ANY TABLE/EXECUTE ANY PROCEDURE 等）
- 管理权限审计（DBA/IMP_FULL_DATABASE/EXP_FULL_DATABASE/SCHEDULER_ADMIN）
- 直授权限 vs 角色授权区分

### 角色权限审计（10+ 检查项）
- 角色分配关系（含 ADMIN_OPTION/DEFAULT_ROLE 标记）
- 递归角色继承分析（展开角色层级，发现隐藏权限）
- 高危角色持有者清单（DBA/SELECT_CATALOG_ROLE/IMP_FULL_DATABASE 等）
- 角色默认启用状态检查

### 对象权限审计（10+ 检查项）
- 表级权限分布（SELECT/INSERT/UPDATE/DELETE/ALTER）
- 列级敏感权限审计（敏感列上的读写权限）
- 系统包 EXECUTE 权限（UTL_FILE/UTL_HTTP/UTL_SMTP/DBMS_LOB 等）
- DIRECTORY 目录对象权限
- PUBLIC 权限审计

### 口令策略审计（10+ 检查项）
- Profile 密码策略参数（FAILED_LOGIN_ATTEMPTS/PASSWORD_LIFE_TIME/PASSWORD_VERIFY_FUNCTION 等）
- 默认 Profile 密码复杂度校验检查
- 资源限制合规检查（IDLE_TIME/SESSIONS_PER_USER 等）
- 用户→Profile 映射关系

## 风险等级

| 等级 | 标识 | 说明 |
|------|------|------|
| 高 | 🔴 | 可能导致数据泄露、权限扩散、安全漏洞、数据库不可用 |
| 中 | 🟡 | 可能导致权限过大、合规风险、潜在安全隐患 |
| 低 | 🟢 | 规范性/管理性问题，不影响安全但影响可维护性 |

## 安全边界
- 安全等级为 query（纯只读扫描），仅做分析与建议
- 不创建/删除/修改任何账号
- 不重置密码、不锁定/解锁账号
- 不执行 GRANT/REVOKE 权限变更
- 不修改 Profile 口令策略
- 不更改认证方式（密码/证书/Kerberos）
- 不执行任何 DDL/DCL 操作

## 功能限制
- 账号管理（创建/删除/密码重置）请用对应账号管理类技能
- 权限变更（GRANT/REVOKE）请用对应权限设计类技能
- 审计日志配置查看请用对应审计日志类技能
- 不调用其它 Skill、不自动修复、仅按需手动触发

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle 账号权限审计技能，纯只读扫描（query / db-security），覆盖账号状态（默认密码/SYSDBA/代理用户/僵尸账号）、系统权限（高危权限/ANY 类权限/管理权限）、角色权限（角色分配/递归继承/高危角色）、对象权限（表级/列级/系统包/DIRECTORY/PUBLIC）、口令策略（Profile 密码策略/资源限制/密码复杂度）五大维度，产出结构化审计报告与整改建议。