---
name: "db-oracle-audit-permission"
description: "Oracle 账号权限审计技能（纯只读扫描）。核心能力：(1) 账号状态审计：账号列表、锁定/过期/未锁定状态、默认密码检测、SYSDBA/SYSOPER 特权账户盘点、代理用户审计；(2) 系统权限审计：高危系统权限（ALTER SYSTEM/ALTER DATABASE/GRANT ANY PRIVILEGE/UNLIMITED TABLESPACE 等）筛查、ANY 类权限盘点、管理权限（DBA/IMP_FULL_DATABASE）审计；(3) 角色权限审计：角色分配关系、递归角色继承分析、高危角色持有者清单；(4) 对象权限审计：表级权限（SELECT/INSERT/UPDATE/DELETE）分布、列级敏感权限（敏感列上的读写权限）、EXECUTE 系统包权限风险；(5) 口令策略审计：Profile 密码策略（FAILED_LOGIN_ATTEMPTS/PASSWORD_LIFE_TIME/PASSWORD_VERIFY_FUNCTION）、资源限制合规检查。适用场景：定期账号权限审计、安全基线检查、权限越权筛查、合规预检（等保/ISO27001）、高危权限清理准备。功能限制：不创建/删除/修改账号、不重置密码、不锁定/解锁账号、不执行 GRANT/REVOKE、不修改 Profile 策略、不更改认证方式、不执行任何 DDL/DCL（safe_level=query，纯扫描）。"
version: "v1.0.0"
tags: db-security
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "username"
    type: "string"
    required: false
    default: ""
    desc: "指定审计用户名（可选，为空则审计全部非系统账号）"
  - name: "audit_scope"
    type: "string"
    required: false
    default: "all"
    desc: "审计范围：all（全部）/ account（仅账号状态）/ privilege（仅权限）/ policy（仅口令策略）"
  - name: "include_sys"
    type: "boolean"
    required: false
    default: false
    desc: "是否包含 Oracle 内置系统账号（SYS/SYSTEM/DBSNMP 等），默认仅审计业务账号"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 账号权限审计

本技能对 Oracle 数据库账号权限执行纯只读扫描，产出结构化审计报告，包含账号状态、权限分布、口令策略、风险清单与整改建议（仅建议，不执行任何变更）。

---

## 核心能力

### 账号状态审计
- 账号列表与基本信息（用户名、默认表空间、临时表空间、Profile、认证方式）
- 账号状态检测（OPEN / LOCKED / EXPIRED / EXPIRED(GRACE)）
- 默认密码检测（DBA_USERS_WITH_DEFPWD 视图，11g+）
- SYSDBA / SYSOPER 特权账户盘点（V$PWFILE_USERS）
- 代理用户（Proxy User）审计
- 测试/演示/临时账号识别

### 系统权限审计
- 高危系统权限筛查（ALTER SYSTEM / ALTER DATABASE / GRANT ANY PRIVILEGE / UNLIMITED TABLESPACE / EXEMPT REDACTION POLICY 等）
- ANY 类权限盘点（SELECT ANY TABLE / UPDATE ANY TABLE / DELETE ANY TABLE / EXECUTE ANY PROCEDURE 等）
- 管理权限审计（DBA / IMP_FULL_DATABASE / EXP_FULL_DATABASE / SCHEDULER_ADMIN）
- 直接授权 vs 角色授权区分（DBA_SYS_PRIVS 直授标记）

### 角色权限审计
- 角色分配关系（DBA_ROLE_PRIVS 含 ADMIN_OPTION / DEFAULT_ROLE 标记）
- 递归角色继承分析（展开角色层级，发现隐藏权限）
- 高危角色持有者清单（DBA / SELECT_CATALOG_ROLE / IMP_FULL_DATABASE / EXP_FULL_DATABASE / SCHEDULER_ADMIN 等）
- 角色是否默认启用（DEFAULT_ROLE = YES/NO）

### 对象权限审计
- 表级权限分布（DBA_TAB_PRIVS：SELECT / INSERT / UPDATE / DELETE / ALTER / INDEX / REFERENCES）
- 列级权限审计（DBA_COL_PRIVS：敏感列上的读写权限）
- 系统包执行权限（DBA_TAB_PRIVS WHERE TYPE = 'PACKAGE'：UTL_FILE / UTL_HTTP / UTL_SMTP / DBMS_LOB 等）
- 目录对象权限（DBA_TAB_PRIVS WHERE TYPE = 'DIRECTORY'）

### 口令策略审计
- Profile 密码策略：FAILED_LOGIN_ATTEMPTS / PASSWORD_LIFE_TIME / PASSWORD_GRACE_TIME / PASSWORD_REUSE_TIME / PASSWORD_REUSE_MAX / PASSWORD_LOCK_TIME / PASSWORD_VERIFY_FUNCTION
- 资源限制合规检查（IDLE_TIME / CONNECT_TIME / CPU_PER_SESSION 等）
- 默认 Profile（DEFAULT）是否启用密码复杂度校验函数
- 用户自定义 Profile 分配情况

## 适用场景
- 定期账号权限审计（月度/季度/年度）
- 安全基线对标检查（等保2.0 / ISO 27001 / SOC2）
- 权限越权筛查与最小权限整改准备
- 合规预检与审计证据准备
- 离职/转岗人员权限回收确认
- 高危权限清理前盘点
- 新系统上线前的权限安全评审

## 功能限制 / 安全边界
- 不创建/删除/修改任何账号
- 不重置密码、不锁定/解锁账号
- 不执行 GRANT / REVOKE 权限变更
- 不修改 Profile 口令策略
- 不更改认证方式（密码/证书/Kerberos）
- 不执行任何 DDL / DCL 操作
- 不调用其它 Skill、不自动修复、仅按需手动触发
- 仅产出审计结论与整改建议，单次执行耗时 ≤10s，无第三方依赖、无常驻逻辑

---

## 一、推理框架：Oracle 账号权限审计链

```
输入审计参数（instance_host / username / audit_scope）
    |
    v
[1] 连接验证与环境探测
    | 验证实例可达性
    | 确认查询权限（需 SELECT_CATALOG_ROLE 或 DBA 权限）
    | 探测 Oracle 版本（决定可用视图与检查项）
    v
[2] 账号状态审计
    | DBA_USERS 查询 → 账号列表、状态、Profile、认证方式
    | DBA_USERS_WITH_DEFPWD（11g+）→ 默认密码
    | V$PWFILE_USERS → SYSDBA/SYSOPER 特权账户
    | PROXY_USERS → 代理用户关系
    v
[3] 系统权限审计
    | DBA_SYS_PRIVS → 直授系统权限
    | 高危权限标记（ALTER SYSTEM/DATABASE、GRANT ANY PRIVILEGE 等）
    | ANY 类权限筛查
    | 管理角色权限展开
    v
[4] 角色权限审计
    | DBA_ROLE_PRIVS → 角色分配关系
    | 递归展开角色层级（ROLE_TAB_PRIVS / ROLE_SYS_PRIVS / ROLE_ROLE_PRIVS）
    | 高危角色持有者识别
    | ADMIN_OPTION 标记
    v
[5] 对象权限审计
    | DBA_TAB_PRIVS → 表级/视图级权限
    | DBA_COL_PRIVS → 列级敏感权限
    | 系统包 EXECUTE 权限（UTL_FILE / UTL_HTTP 等）
    | 目录对象权限（DIRECTORY）
    v
[6] 口令策略审计
    | DBA_PROFILES → 密码策略参数
    | 默认 Profile 密码复杂度检查
    | 用户→Profile 映射关系
    v
[7] 综合审计报告
    | 五大维度问题汇总（按风险等级排序）
    | 逐项风险说明 + 整改建议
    | 综合安全评分（0~100，越高越安全）
```

---

## 二、账号状态审计（只读扫描）

### 2.1 账号列表与状态

```sql
-- 查询全部非系统账号
SELECT username,
       account_status,
       default_tablespace,
       temporary_tablespace,
       profile,
       authentication_type,
       created,
       lock_date,
       expiry_date
FROM dba_users
WHERE username NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'XDB', 'OUTLN', 'APPQOSSYS',
                        'ORACLE_OCM', 'GSMADMIN_INTERNAL', 'GSMCATUSER', 'GSMUSER',
                        'DIP', 'REMOTE_SCHEDULER_AGENT', 'SYSBACKUP', 'SYSDG',
                        'SYSKM', 'SYSRAC', 'XS$NULL', 'AUDSYS')
ORDER BY account_status, username;
```

### 2.2 账号状态检查清单

| 检查项 | 风险等级 | 说明 |
|--------|---------|------|
| 账号状态为 EXPIRED | 🟡 中 | 密码已过期，应用可能突然中断 |
| 账号状态为 EXPIRED(GRACE) | 🟡 中 | 密码在宽限期内，需尽快修改 |
| 账号状态为 LOCKED | 🟢 低 | 账号已锁定（可能是离职/停用），确认是否仍需保留 |
| 账号状态为 EXPIRED & LOCKED | 🟢 低 | 账号已过期且锁定，建议清理 |
| 存在大量 OPEN 但长期未用的账号 | 🟡 中 | 僵尸账号，存在安全隐患 |

### 2.3 默认密码检测

```sql
-- Oracle 11g+ 支持 DBA_USERS_WITH_DEFPWD 视图
SELECT * FROM dba_users_with_defpwd;

-- 🔴 高危：任何出现在此视图中的账号仍使用默认密码
-- 常见默认密码账号：SCOTT(TIGER)、HR(HR)、OE(OE)、PM(PM)、SH(SH)、BI(BI)、IX(IX)
```

### 2.4 SYSDBA / SYSOPER 特权账户

```sql
-- 查询具有 SYSDBA / SYSOPER 特权的账户
SELECT * FROM v$pwfile_users;

-- 🔴 高危：非 SYS 的 SYSDBA 账户（可通过操作系统认证或密码文件）
-- 🟡 中危：存在多个 SYSDBA 账户，应审计其必要性
-- 规则：除 SYS 外，如有其他 SYSDBA 账户，应逐项说明必要性
```

### 2.5 代理用户审计

```sql
-- 查询代理用户关系
SELECT proxy_user_id, client_user_id, proxy, client, authentication
FROM proxy_users;

-- 🟡 中危：代理用户关系可能绕过权限控制
-- 检查代理用户（proxy）是否拥有过多权限
```

### 2.6 测试/演示/临时账号识别

```sql
-- 识别测试/演示/临时账号
SELECT username, account_status, created
FROM dba_users
WHERE username LIKE 'TEST%'
   OR username LIKE 'DEMO%'
   OR username LIKE 'TMP%'
   OR username LIKE 'TEMP%'
   OR username LIKE 'DEV%'
ORDER BY username;

-- 🟡 中危：生产环境存在测试/演示账号
-- 建议：生产环境禁止保留测试账号，如需保留则锁定并限制权限
```

---

## 三、系统权限审计（只读扫描）

### 3.1 高危系统权限清单

| 权限名称 | 风险等级 | 风险说明 |
|----------|---------|---------|
| ALTER SYSTEM | 🔴 高 | 可修改数据库系统参数，可能导致实例不可用 |
| ALTER DATABASE | 🔴 高 | 可修改数据库结构，如数据文件/日志文件操作 |
| GRANT ANY PRIVILEGE | 🔴 高 | 可授予任何系统权限，权限扩散风险 |
| GRANT ANY ROLE | 🔴 高 | 可授予任何角色，包括 DBA 角色 |
| UNLIMITED TABLESPACE | 🔴 高 | 无限制使用表空间，可能导致磁盘耗尽 |
| EXEMPT REDACTION POLICY | 🔴 高 | 绕过数据编辑策略，可查看脱敏数据原始值 |
| EXEMPT ACCESS POLICY | 🔴 高 | 绕过 VPD/FGAC 访问控制策略 |
| ADMINISTER DATABASE TRIGGER | 🟡 中 | 可创建数据库级触发器，可能植入后门 |
| BECOME USER | 🟡 中 | 可冒充其他用户执行操作 |
| ALTER USER | 🟡 中 | 可修改其他用户密码/Profile/表空间 |
| DROP USER | 🟡 中 | 可删除用户账号 |
| CREATE USER | 🟡 中 | 可创建新账号 |

### 3.2 高危权限审计查询

```sql
-- 查询拥有高危系统权限的非系统账号
SELECT grantee, privilege, admin_option
FROM dba_sys_privs
WHERE privilege IN ('ALTER SYSTEM', 'ALTER DATABASE',
                     'GRANT ANY PRIVILEGE', 'GRANT ANY ROLE',
                     'UNLIMITED TABLESPACE', 'EXEMPT REDACTION POLICY',
                     'EXEMPT ACCESS POLICY', 'ADMINISTER DATABASE TRIGGER',
                     'BECOME USER', 'ALTER USER', 'DROP USER', 'CREATE USER')
  AND grantee NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
ORDER BY privilege, grantee;
```

### 3.3 ANY 类权限筛查

```sql
-- 查询 ANY 类权限（SELECT ANY TABLE / UPDATE ANY TABLE / EXECUTE ANY PROCEDURE 等）
SELECT grantee, privilege, admin_option
FROM dba_sys_privs
WHERE privilege LIKE '%ANY%'
  AND grantee NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'EXP_FULL_DATABASE', 'IMP_FULL_DATABASE')
ORDER BY grantee, privilege;

-- 🔴 高危：SELECT ANY TABLE 可读取任意表数据（包括敏感数据）
-- 🔴 高危：EXECUTE ANY PROCEDURE 可执行任意存储过程（包括高危系统包）
-- 🔴 高危：UPDATE ANY TABLE / DELETE ANY TABLE 可修改任意表数据
-- 🟡 中危：SELECT ANY DICTIONARY 可查看数据字典（含用户密码哈希）
```

### 3.4 管理权限审计

```sql
-- 查询拥有 DBA / IMP_FULL_DATABASE / EXP_FULL_DATABASE 等管理角色的账号
SELECT grantee, granted_role, admin_option
FROM dba_role_privs
WHERE granted_role IN ('DBA', 'IMP_FULL_DATABASE', 'EXP_FULL_DATABASE',
                        'SCHEDULER_ADMIN', 'DATAPUMP_IMP_FULL_DATABASE',
                        'DATAPUMP_EXP_FULL_DATABASE', 'EM_EXPRESS_ALL',
                        'AQ_ADMINISTRATOR_ROLE')
  AND grantee NOT IN ('SYS', 'SYSTEM')
ORDER BY granted_role, grantee;

-- 🔴 高危：DBA 角色持有者（除 SYS/SYSTEM 外）
-- 🟡 中危：IMP_FULL_DATABASE / EXP_FULL_DATABASE 持有者（可导出含敏感数据）
```

### 3.5 直授权限 vs 角色授权

```sql
-- 直授系统权限（非通过角色获得）
-- 建议：业务用户应通过角色获得权限，而非直接授权
-- 规则：除 SYS 和 SYSTEM 外，业务账号直授系统权限应标记为需关注
```

---

## 四、角色权限审计（只读扫描）

### 4.1 角色分配关系

```sql
-- 查询非系统账号的角色分配
SELECT grantee, granted_role, admin_option, default_role
FROM dba_role_privs
WHERE grantee NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'XDB', 'OUTLN', 'APPQOSSYS',
                       'ORACLE_OCM', 'GSMADMIN_INTERNAL', 'GSMCATUSER', 'GSMUSER',
                       'DIP', 'REMOTE_SCHEDULER_AGENT', 'SYSBACKUP', 'SYSDG',
                       'SYSKM', 'SYSRAC', 'XS$NULL', 'AUDSYS')
ORDER BY grantee, granted_role;
```

### 4.2 高危角色持有者清单

| 角色名称 | 风险等级 | 风险说明 |
|----------|---------|---------|
| DBA | 🔴 高 | 数据库管理员权限，可执行任何操作 |
| SELECT_CATALOG_ROLE | 🟡 中 | 可查看数据字典，含用户密码哈希 |
| IMP_FULL_DATABASE | 🟡 中 | 可导入数据，可能覆盖现有数据 |
| EXP_FULL_DATABASE | 🟡 中 | 可导出数据，可能泄露敏感数据 |
| SCHEDULER_ADMIN | 🟡 中 | 可创建定时任务，可能植入恶意作业 |
| DATAPUMP_IMP_FULL_DATABASE | 🟡 中 | Data Pump 完全导入权限 |
| DATAPUMP_EXP_FULL_DATABASE | 🟡 中 | Data Pump 完全导出权限 |
| EM_EXPRESS_ALL | 🟡 中 | OEM Express 全部权限 |
| AQ_ADMINISTRATOR_ROLE | 🟡 中 | 高级队列管理权限 |

### 4.3 递归角色继承分析

```sql
-- 角色→角色继承关系
SELECT role, granted_role
FROM role_role_privs
WHERE role NOT IN ('DBA', 'IMP_FULL_DATABASE', 'EXP_FULL_DATABASE',
                    'SCHEDULER_ADMIN', 'DATAPUMP_IMP_FULL_DATABASE',
                    'DATAPUMP_EXP_FULL_DATABASE')
ORDER BY role, granted_role;

-- 审计规则：
-- ① 展开角色层级，发现"隐藏权限"（用户持有角色 A，角色 A 包含角色 B 含高危权限）
-- ② 检查是否存在普通角色→DBA 角色的间接继承
-- ③ 标记 ADMIN_OPTION = YES 的角色（持有者可向他人授予该角色）
```

### 4.4 角色默认启用检查

- DEFAULT_ROLE = YES：登录时自动启用，权限始终生效
- DEFAULT_ROLE = NO：需手动 SET ROLE 启用，风险较低
- 建议：高危角色（DBA 等）不应设置为 DEFAULT_ROLE = YES

---

## 五、对象权限审计（只读扫描）

### 5.1 表级权限分布

```sql
-- 查询非系统 Schema 上的对象权限
SELECT grantee, owner, table_name, privilege, grantable, hierarchy
FROM dba_tab_privs
WHERE owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'XDB', 'OUTLN', 'APPQOSSYS',
                     'ORACLE_OCM', 'GSMADMIN_INTERNAL', 'AUDSYS', 'CTXSYS',
                     'MDSYS', 'OLAPSYS', 'ORDDATA', 'ORDPLUGINS', 'ORDSYS',
                     'SI_INFORMTN_SCHEMA', 'WMSYS')
  AND grantee NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'PUBLIC')
ORDER BY owner, table_name, grantee;
```

### 5.2 敏感列权限审计

```sql
-- 查询列级权限（DBA_COL_PRIVS）
SELECT grantee, owner, table_name, column_name, privilege
FROM dba_col_privs
WHERE owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND grantee NOT IN ('SYS', 'SYSTEM', 'PUBLIC')
ORDER BY owner, table_name, column_name, grantee;

-- 🟡 中危：敏感列上的 UPDATE 权限（密码列、金额列、身份证号列等）
-- 敏感列关键词：PASSWORD, PASSWD, PWD, SECRET, CREDENTIAL
--               ID_CARD, IDCARD, SSN, IDENTITY
--               PHONE, MOBILE, TEL, TELEPHONE
--               BANK_CARD, CARD_NO, CREDIT_CARD
--               EMAIL, MAIL
--               SALARY, BONUS, WAGE
```

### 5.3 系统包执行权限风险

```sql
-- 查询高危系统包 EXECUTE 权限
SELECT grantee, owner, table_name, privilege
FROM dba_tab_privs
WHERE table_name IN ('UTL_FILE', 'UTL_HTTP', 'UTL_SMTP', 'UTL_TCP', 'UTL_MAIL',
                      'DBMS_LOB', 'DBMS_SCHEDULER', 'DBMS_SQL', 'DBMS_SYS_SQL',
                      'DBMS_BACKUP_RESTORE', 'DBMS_OBFUSCATION_TOOLKIT',
                      'DBMS_CRYPTO', 'DBMS_RANDOM', 'HTTPURITYPE',
                      'DBMS_XSLPROCESSOR', 'DBMS_JAVA', 'DBMS_JAVA_TEST')
  AND type = 'PACKAGE'
  AND owner = 'SYS'
  AND grantee NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'PUBLIC')
ORDER BY table_name, grantee;

-- 🔴 高危：非系统账户持有 UTL_FILE / UTL_HTTP / UTL_TCP / UTL_SMTP / DBMS_SCHEDULER EXECUTE 权限
-- 🟡 中危：非系统账户持有 DBMS_LOB / DBMS_CRYPTO / UTL_MAIL EXECUTE 权限
```

### 5.4 DIRECTORY 目录对象权限

```sql
-- 查询目录对象权限
SELECT grantee, table_name, privilege
FROM dba_tab_privs
WHERE type = 'DIRECTORY'
  AND grantee NOT IN ('SYS', 'SYSTEM', 'PUBLIC')
ORDER BY table_name, grantee;

-- 🟡 中危：READ/WRITE 目录对象权限 → 可读写操作系统文件
-- 检查是否存在 DATA_PUMP_DIR 以外的自定义目录授权
```

### 5.5 PUBLIC 权限审计

```sql
-- 查询授予 PUBLIC 的对象权限
SELECT owner, table_name, privilege, grantable
FROM dba_tab_privs
WHERE grantee = 'PUBLIC'
ORDER BY owner, table_name, privilege;

-- 🟡 中危：授予 PUBLIC 的权限对所有用户生效
-- 重点关注：PUBLIC 对系统包（UTL_FILE/UTL_HTTP 等）的 EXECUTE 权限
-- 重点关注：PUBLIC 对敏感表的 SELECT 权限
```

---

## 六、口令策略审计（只读扫描）

### 6.1 密码策略参数

```sql
-- 查询所有 Profile 的口令策略
SELECT profile, resource_name, limit
FROM dba_profiles
WHERE resource_type = 'PASSWORD'
  AND resource_name IN ('FAILED_LOGIN_ATTEMPTS', 'PASSWORD_LIFE_TIME',
                         'PASSWORD_REUSE_TIME', 'PASSWORD_REUSE_MAX',
                         'PASSWORD_LOCK_TIME', 'PASSWORD_GRACE_TIME',
                         'PASSWORD_VERIFY_FUNCTION')
ORDER BY profile, resource_name;
```

### 6.2 口令策略检查清单

| 检查项 | 安全基线 | 风险等级 | 说明 |
|--------|---------|---------|------|
| FAILED_LOGIN_ATTEMPTS | ≥ 5 且 ≤ 10 | 🟡 中 | DEFAULT 为 10 次，UNLIMITED 为不限制（高危） |
| PASSWORD_LIFE_TIME | ≥ 90 天 | 🟡 中 | 密码过期时间，UNLIMITED 为永不过期 |
| PASSWORD_GRACE_TIME | ≤ 7 天 | 🟢 低 | 密码过期宽限期 |
| PASSWORD_REUSE_MAX | ≥ 5 次 | 🟢 低 | 密码重用前需使用不同密码次数 |
| PASSWORD_REUSE_TIME | ≥ 365 天 | 🟢 低 | 密码重用前需等待天数 |
| PASSWORD_LOCK_TIME | ≥ 1 天 | 🟡 中 | 登录失败锁定时间，UNLIMITED 需管理员手动解锁 |
| PASSWORD_VERIFY_FUNCTION | 非 NULL | 🔴 高 | 密码复杂度校验函数，NULL 表示无密码复杂度要求 |

### 6.3 默认 Profile 密码复杂度检查

```sql
-- 检查 DEFAULT Profile 是否启用密码复杂度校验
SELECT profile, resource_name, limit
FROM dba_profiles
WHERE profile = 'DEFAULT'
  AND resource_name = 'PASSWORD_VERIFY_FUNCTION';

-- 🔴 高危：DEFAULT Profile 的 PASSWORD_VERIFY_FUNCTION = NULL
-- 说明：所有使用 DEFAULT Profile 的账号无密码复杂度要求
-- 建议：启用 ORA12C_VERIFY_FUNCTION 或自定义复杂度校验函数
```

### 6.4 用户→Profile 映射

```sql
-- 查询用户与 Profile 的对应关系
SELECT username, profile, account_status
FROM dba_users
WHERE username NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'XDB', 'OUTLN', 'APPQOSSYS',
                       'ORACLE_OCM', 'GSMADMIN_INTERNAL', 'GSMCATUSER', 'GSMUSER',
                       'DIP', 'REMOTE_SCHEDULER_AGENT', 'SYSBACKUP', 'SYSDG',
                       'SYSKM', 'SYSRAC', 'XS$NULL', 'AUDSYS')
ORDER BY profile, username;
```

### 6.5 资源限制检查

```sql
-- 查询资源限制参数
SELECT profile, resource_name, limit
FROM dba_profiles
WHERE resource_type = 'KERNEL'
  AND resource_name IN ('IDLE_TIME', 'CONNECT_TIME', 'CPU_PER_SESSION',
                         'CPU_PER_CALL', 'LOGICAL_READS_PER_SESSION',
                         'LOGICAL_READS_PER_CALL', 'SESSIONS_PER_USER',
                         'COMPOSITE_LIMIT')
ORDER BY profile, resource_name;

-- 🟢 低：IDLE_TIME（空闲超时）建议 ≤ 60 分钟
-- 🟢 低：SESSIONS_PER_USER 建议设置合理上限
```

---

## 七、审计报告输出格式

```markdown
=== Oracle 账号权限审计报告 ===
实例: 192.168.1.100:1521/orcl
审计范围: all
审计时间: 2026-08-17 12:00:00
Oracle 版本: 19c

--- 综合安全评分: 58 / 100（越高越安全）---

=== 一、账号状态审计 ===
总账号数: 45（含系统账号）/ 15（业务账号）
[高] 共 1 项
  [高-1] 发现 2 个账号使用默认密码（SCOTT, HR）→ 建议立即修改密码或锁定账号
[中] 共 3 项
  [中-1] 账号 APP_USER 状态为 EXPIRED(GRACE) → 密码将在 5 天后过期，建议尽快修改
  [中-2] 生产环境存在测试账号 TEST_DEV → 建议锁定或删除
  [中-3] 存在 3 个 OPEN 状态但最后登录在 180 天前的僵尸账号 → 建议锁定或清理
[低] 共 1 项
  [低-1] 账号 OLD_ADMIN 状态为 LOCKED → 建议确认是否可删除

=== 二、系统权限审计 ===
[高] 共 3 项
  [高-1] 账号 APP_ADMIN 拥有 ALTER SYSTEM 权限（ADMIN_OPTION=NO）→ 建议回收
  [高-2] 账号 REPORT_USER 拥有 SELECT ANY TABLE 权限 → 建议改为按需授权具体表
  [高-3] 账号 ETL_USER 拥有 UNLIMITED TABLESPACE 权限 → 建议设置表空间配额
[中] 共 2 项
  [中-1] 账号 DEV_USER 拥有 CREATE USER 权限 → 建议回收，创建用户应由 DBA 统一操作
  [中-2] 账号 APP_SVC 拥有 EXECUTE ANY PROCEDURE 权限 → 高风险，建议改为按需授权具体存储过程

=== 三、角色权限审计 ===
[高] 共 2 项
  [高-1] 账号 APP_ADMIN 持有 DBA 角色（DEFAULT_ROLE=YES）→ 权限过大，建议降级为业务专用角色
  [高-2] 账号 SVC_ACCOUNT 持有 SELECT_CATALOG_ROLE 角色 → 可查看数据字典，建议审计其必要性
[中] 共 1 项
  [中-1] 账号 DEV_USER 持有 IMP_FULL_DATABASE 角色 → 可导入数据，建议限制

=== 四、对象权限审计 ===
[高] 共 1 项
  [高-1] 账号 APP_USER 拥有 UTL_FILE 包 EXECUTE 权限 → 可读写服务器文件，建议回收
[中] 共 3 项
  [中-1] 账号 REPORT_USER 对 HR.EMPLOYEES.SALARY 列有 UPDATE 权限 → 薪资列应严格控制
  [中-2] 账号 APP_USER 对 DATA_PUMP_DIR 目录有 WRITE 权限 → 建议审计
  [中-3] PUBLIC 拥有 UTL_HTTP 包 EXECUTE 权限 → 所有用户可发起 HTTP 请求，建议回收

=== 五、口令策略审计 ===
[高] 共 1 项
  [高-1] DEFAULT Profile 未启用 PASSWORD_VERIFY_FUNCTION → 12 个使用 DEFAULT Profile 的账号无密码复杂度要求
[中] 共 2 项
  [中-1] Profile APP_PROFILE 的 FAILED_LOGIN_ATTEMPTS 设为 UNLIMITED → 无登录失败次数限制，存在暴力破解风险
  [中-2] 账号 APP_USER 的 PASSWORD_LIFE_TIME 为 UNLIMITED → 密码永不过期

=== 六、整改建议汇总 ===
账号状态：
  1. 修改 SCOTT、HR 账号默认密码或锁定
  2. 尽快修改 APP_USER 密码（宽限期 5 天）
  3. 锁定或删除 TEST_DEV 测试账号
  4. 清理 3 个僵尸账号

系统权限：
  5. 回收 APP_ADMIN 的 ALTER SYSTEM 权限
  6. 回收 REPORT_USER 的 SELECT ANY TABLE，改为按需授权
  7. 为 ETL_USER 设置表空间配额，回收 UNLIMITED TABLESPACE

角色权限：
  8. 为 APP_ADMIN 创建业务专用角色，回收 DBA 角色
  9. 审计 SVC_ACCOUNT 的 SELECT_CATALOG_ROLE 必要性

对象权限：
  10. 回收 APP_USER 的 UTL_FILE EXECUTE 权限
  11. 回收 REPORT_USER 对 HR.EMPLOYEES.SALARY 的 UPDATE 权限
  12. 回收 PUBLIC 的 UTL_HTTP EXECUTE 权限

口令策略：
  13. 为 DEFAULT Profile 启用 PASSWORD_VERIFY_FUNCTION
  14. 修改 APP_PROFILE 的 FAILED_LOGIN_ATTEMPTS 为有限值（如 10）

=== 七、综合说明 ===
- 审计范围：all，覆盖 5 个维度
- 共发现 6 个高风险项、11 个中风险项、1 个低风险项
- 建议优先处理高风险项（账号默认密码、高危系统权限、DBA 角色扩散、口令策略缺失）
- 本报告仅提供审计结论与整改建议，不执行任何变更操作
```

---

## 八、风险等级判定标准

| 风险等级 | 标识 | 判定标准 | 示例 |
|----------|------|---------|------|
| 高 | 🔴 | 可能导致数据泄露、权限扩散、安全漏洞、数据库不可用 | 默认密码、DBA 角色扩散、UTL_FILE 执行权限、无密码复杂度 |
| 中 | 🟡 | 可能导致权限过大、合规风险、潜在安全隐患 | ANY 类权限、IMP_FULL_DATABASE、僵尸账号、弱口令策略 |
| 低 | 🟢 | 规范性/管理性问题，不影响安全但影响可维护性 | 账号已锁定待清理、长期未登录、命名不规范 |

---

## 九、审计范围策略

| audit_scope | 覆盖维度 | 适用场景 |
|-------------|---------|---------|
| all | 全部 5 个维度 | 全面审计、合规检查 |
| account | 仅账号状态（第 2 节） | 离职审计、账号盘点 |
| privilege | 系统权限 + 角色权限 + 对象权限（第 3-5 节） | 权限越权排查、最小权限整改 |
| policy | 仅口令策略（第 6 节） | 密码策略合规检查 |

---

## 十、最小权限角色基线对照表（仅供审计对照，不执行）

| 角色类型 | 推荐权限 | 禁止权限 |
|----------|---------|---------|
| 应用账户 | 业务 Schema 的 SELECT, INSERT, UPDATE, DELETE | ALTER SYSTEM, ALTER DATABASE, DBA, ANY 类权限, UTL_FILE/UTL_HTTP/UTL_SMTP |
| 只读账户 | 业务 Schema 的 SELECT（指定表） | INSERT, UPDATE, DELETE, DDL, ANY 类权限 |
| ETL 账户 | 目标 Schema 的 SELECT, INSERT, UPDATE, DELETE, CREATE TABLE | DROP ANY TABLE, ALTER SYSTEM, UTL_FILE |
| 报表账户 | 业务 Schema 的 SELECT（汇总表/视图） | 明细表 SELECT, ANY 类权限, 敏感列权限 |
| 备份账户 | SYSBACKUP 角色 | DBA, SYSDBA, SELECT ANY TABLE |
| 监控账户 | SELECT_CATALOG_ROLE | DBA, ALTER SYSTEM, ALTER DATABASE |

---

## 异常处理
- 实例连接失败时返回明确的结构化错误提示，不暴露底层异常栈。
- 审计用户缺少 SELECT_CATALOG_ROLE 权限时，提示需要的最小查询权限，不向上抛出原始堆栈。
- 单次审计耗时 ≤10s，大型环境（> 100 账号）建议按 scope 分批审计。
- 不支持 Oracle 版本（< 10g）时提示版本限制，并给出可用的回退检查项。
- 本技能仅做只读分析与建议，不执行任何 DDL/DML/DCL，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：综合安全评分 + 五维度问题清单（按风险等级排序）+ 逐项整改建议 + 最小权限对照表。