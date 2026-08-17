---
name: "db-oracle-switchover"
description: "Oracle DataGuard 主备切换技能（高危，需双签）。核心能力：执行 DataGuard 主备角色切换（SWITCHOVER）、计划内切换前全面校验（DG 配置状态/同步延迟/归档中断/日志传输/Standby Redo Log/闪回区空间/数据文件状态）、切换执行（主库切备库 STANDY→备库切主库 PRIMARY）、切换后验证（角色确认/同步状态/归档传输/应用延迟/数据文件一致性）。适用场景：计划内主备角色互换（硬件维护/系统升级/灾备演练/负载均衡）、控制文件损坏修复后的主备重新对齐、DG 配置调整后的角色同步。功能限制：切换操作不可逆且影响数据库服务连续性，必须通过双人审批（双签）后方可执行；不执行 Failover（强制故障切换，不可逆）、不修改 DG/Broker 配置参数、不执行数据库备份恢复、不执行 DDL/DML；切换前必须完成前置校验（DG 同步状态/延迟/归档连续性/Standby Redo Log 配置）。"
version: "v1.0.0"
tags: db-ops
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "当前主库 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "switchover_type"
    type: "string"
    required: false
    default: "switchover"
    desc: "切换类型：switchover（标准计划内主备切换）/ validate（仅前置校验不执行切换，默认走此模式进行安全校验）/ dg_broker（通过 DataGuard Broker 执行切换，需已配置 Broker）"
  - name: "standby_host"
    type: "string"
    required: false
    default: ""
    desc: "备库实例连接串（host:port/service_name 或 TNS 别名），switchover 模式下必填"
  - name: "standby_unique_name"
    type: "string"
    required: false
    default: ""
    desc: "备库 DB_UNIQUE_NAME，不填则自动从主库 DG 配置中识别"
  - name: "primary_unique_name"
    type: "string"
    required: false
    default: ""
    desc: "主库 DB_UNIQUE_NAME，不填则自动从当前实例识别"
  - name: "max_lag_seconds"
    type: "integer"
    required: false
    default: 30
    desc: "允许的最大备库延迟（秒），超过此阈值终止切换，默认 30 秒"
  - name: "max_lag_mb"
    type: "integer"
    required: false
    default: 100
    desc: "允许的最大备库延迟（MB），超过此阈值终止切换，默认 100 MB"
  - name: "validate_only"
    type: "boolean"
    required: false
    default: true
    desc: "是否仅做前置校验（默认 true），设为 false 且双签通过后才实际执行切换"
  - name: "wait_timeout_seconds"
    type: "integer"
    required: false
    default: 600
    desc: "等待备库追上主库的超时时间（秒），默认 600 秒"
  - name: "approver_one"
    type: "string"
    required: false
    default: ""
    desc: "第一审批人标识（双签第一签，必填，高危操作须双人审批）"
  - name: "approver_two"
    type: "string"
    required: false
    default: ""
    desc: "第二审批人标识（双签第二签，必填，高危操作须双人审批）"
  - name: "skip_checks"
    type: "boolean"
    required: false
    default: false
    desc: "是否跳过前置校验（默认 false，仅极端紧急场景经双签确认后可设为 true，不推荐）"
support_db: oracle
safe_level: "danger"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle DataGuard 主备切换（SWITCHOVER）

> 本技能执行 DataGuard 计划内主备角色切换，核心特征：**双人审批（双签）门禁 + 完整前置校验链 + 切换执行 + 切换后验证**。切换操作不可逆，影响数据库服务连续性，执行前必须完成双签确认与前置校验。

## 核心能力
- 单一职责：Oracle DataGuard SWITCHOVER 主备角色互换（计划内切换）。
- 完整前置校验：DG 配置状态、同步延迟、归档中断、日志传输、Standby Redo Log、闪回区空间、数据文件状态。
- 支持标准 SQL*Plus 切换与 DataGuard Broker 切换两种模式。
- 切换后自动验证：角色确认、同步状态、归档传输、应用延迟、数据文件一致性。
- 切换前自动等待备库追上主库（可配置超时时间）。

## 适用场景
- 计划内硬件维护（主库服务器需停机维护，提前切换至备库）
- 系统升级/补丁应用（先切换后对原主库进行升级）
- 灾备演练（定期验证主备切换能力与 RTO/RPO）
- 负载均衡（主备角色互换以分散负载）
- 数据中心迁移（配合 DG 实现最小停机迁移）
- 控制文件损坏修复后的主备重新对齐
- DG 配置调整后的角色同步验证

## 功能限制 / 安全边界
- **不执行 Failover（强制故障切换）**：Failover 不可逆且会导致原主库数据丢失，本技能仅支持计划内 SWITCHOVER。
- 不修改 DG 配置参数（LOG_ARCHIVE_DEST_n / FAL_SERVER / FAL_CLIENT 等）
- 不修改 DataGuard Broker 配置（如 DGMGRL 的 CONFIGURATION 修改）
- 不执行数据库备份/恢复
- 不执行 DDL/DML
- 不调用其他 Skill；仅按需手动触发
- SWITCHOVER 操作不可逆，执行后原主库变为备库，原备库变为主库
- 切换过程中主备库均不可提供读写服务（短暂中断），业务需提前感知
- 切换前必须确认双签（approver_one + approver_two）均非空，且在校验报告中明确展示

---

## 一、推理框架：SWITCHOVER 执行链

```
用户提出 DataGuard 主备切换需求
    |
    v
[1] 双签门禁
    | 检查 approver_one 与 approver_two 是否均非空
    | 双签信息记录到切换报告中
    | 任一审批人缺失 → 终止操作，提示需双人审批
    v
[2] 前置校验（只读，主库 + 备库）
    | DG 配置状态（v$dataguard_config / dba_logstdby_parameters）
    | 同步延迟（主备 SCN 差距 / 备库 REDO 应用延迟）
    | 归档日志连续性（主库未传输归档 / 备库 GAP 检查）
    | Standby Redo Log 配置（大小/组数/状态）
    | 闪回恢复区空间（FRA 使用率）
    | 数据文件状态（主备数据文件一致性）
    | 监听与服务状态（主备库监听可达性）
    v
[3] 校验结果评估
    | 通过 → 输出校验报告，等待用户确认
    | 不通过 → 输出阻塞项详情与修复建议，终止操作
    v
[4] 切换执行（validate_only=false 且双签通过）
    | 主库执行：ALTER DATABASE COMMIT TO SWITCHOVER TO PHYSICAL STANDBY;
    | 备库执行：ALTER DATABASE COMMIT TO SWITCHOVER TO PRIMARY;
    | 新主库 OPEN（如需要）
    | 新备库启动 MRP（Managed Recovery Process）
    v
[5] 切换后验证
    | 角色确认（主备角色互换）
    | 新主库读写验证
    | 新备库同步状态（MRP 运行 / 延迟）
    | 归档传输恢复正常
    v
[6] 结果输出
    | 结构化输出：校验结果 + 切换前后状态对比 + 审批记录 + 回退方案
```

---

## 二、双签审批门禁（必须最先执行）

```sql
-- 双签审批记录（不执行 SQL，仅记录）
-- 第一审批人: <approver_one>
-- 第二审批人: <approver_two>
-- 审批时间: <SYSDATE>
-- 审批结果: 通过 / 不通过
```

**双签规则：**
- `approver_one` 和 `approver_two` 必须均非空
- 两个审批人不能为同一人
- 校验报告中必须展示双签信息
- 如 `validate_only=true`（默认），双签仅用于校验授权；只有当 `validate_only=false` 时双签才用于实际切换授权

---

## 三、前置校验（只读 SQL）

### 3.1 主库 DG 配置状态

```sql
-- 主库数据库角色与 DG 状态
SELECT name AS db_name,
       db_unique_name,
       open_mode,
       database_role,
       switchover_status,
       protection_mode,
       protection_level,
       TO_CHAR(current_scn) AS current_scn
FROM v$database;

-- 主库 DG 目标配置（归档传输目标）
SELECT dest_id,
       dest_name,
       status,
       type,
       database_mode,
       destination,
       error,
       recovery_mode,
       synchronizing_status,
       gap_status
FROM v$archive_dest_status
WHERE database_mode = 'STANDBY';

-- 主库 DG 传输延迟
SELECT dest_id,
       applied_scn,
       TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') AS current_time,
       recovery_mode,
       gap_status,
       synchronizing_status
FROM v$archive_dest_status
WHERE type = 'PHYSICAL';
```

### 3.2 备库状态检查

```sql
-- 备库数据库角色与状态
SELECT name AS db_name,
       db_unique_name,
       open_mode,
       database_role,
       switchover_status,
       TO_CHAR(current_scn) AS current_scn
FROM v$database;

-- 备库实例信息
SELECT instance_name,
       host_name,
       version,
       status,
       TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time
FROM v$instance;

-- 备库 MRP 状态
SELECT process,
       status,
       sequence#,
       thread#,
       block#,
       blocks
FROM v$managed_standby
WHERE process LIKE 'MRP%'
   OR process LIKE 'RFS%';
```

### 3.3 主备 SCN 差距与延迟计算

```sql
-- 主库当前 SCN
SELECT current_scn FROM v$database;

-- 备库当前应用 SCN
SELECT current_scn FROM v$database;

-- 备库 REDO 应用延迟（从主库查询）
SELECT dest_id,
       recovery_mode,
       gap_status,
       applied_scn,
       (SELECT current_scn FROM v$database) - applied_scn AS scn_gap
FROM v$archive_dest_status
WHERE type = 'PHYSICAL';

-- 备库 REDO 应用延迟（从备库查询）
SELECT name,
       value,
       time_computed,
       datum_time
FROM v$dataguard_stats
WHERE name IN ('transport lag', 'apply lag', 'apply finish time');
```

### 3.4 归档日志连续性检查

```sql
-- 主库未传输归档日志
SELECT thread#,
       sequence#,
       first_time,
       next_time,
       archived,
       applied,
       deleted,
       status
FROM v$archived_log
WHERE status = 'A'
  AND standby_dest = 'NO'
  AND deleted = 'NO'
ORDER BY thread#, sequence#;

-- 备库归档日志 GAP 检查
SELECT * FROM v$archive_gap;

-- 备库最近接收的归档日志
SELECT thread#,
       sequence#,
       first_time,
       next_time,
       applied,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI:SS') AS completion_time
FROM v$archived_log
WHERE completion_time > SYSDATE - 1
ORDER BY thread#, sequence# DESC;
```

### 3.5 Standby Redo Log 配置检查

```sql
-- 主库 SRL 配置
SELECT group#,
       thread#,
       sequence#,
       bytes / 1024 / 1024 AS size_mb,
       status,
       archived
FROM v$standby_log
ORDER BY group#, thread#;

-- 备库 SRL 配置
SELECT group#,
       thread#,
       sequence#,
       bytes / 1024 / 1024 AS size_mb,
       status,
       archived
FROM v$standby_log
ORDER BY group#, thread#;

-- 在线 REDO 日志大小（SRL 应与在线 REDO 大小一致）
SELECT group#,
       thread#,
       bytes / 1024 / 1024 AS size_mb,
       members,
       status
FROM v$log
ORDER BY group#, thread#;
```

**SRL 校验规则：**
- 备库 SRL 组数 >= 主库在线 REDO 组数 + 1（推荐）
- SRL 大小与主库在线 REDO 日志大小一致
- 所有 SRL 组状态应为 ACTIVE 或 UNASSIGNED

### 3.6 闪回恢复区空间检查

```sql
-- 主库 FRA 使用率
SELECT name,
       ROUND(space_limit / 1024 / 1024 / 1024, 2) AS limit_gb,
       ROUND(space_used / 1024 / 1024 / 1024, 2) AS used_gb,
       ROUND(space_reclaimable / 1024 / 1024 / 1024, 2) AS reclaimable_gb,
       ROUND((space_used - space_reclaimable) / space_limit * 100, 2) AS used_pct
FROM v$recovery_file_dest;

-- 备库 FRA 使用率
-- 同上在备库执行
```

### 3.7 数据文件状态一致性检查

```sql
-- 主库数据文件状态
SELECT file#,
       name,
       status,
       enabled,
       ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb,
       checkpoint_change#,
       TO_CHAR(checkpoint_time, 'YYYY-MM-DD HH24:MI:SS') AS checkpoint_time
FROM v$datafile
ORDER BY file#;

-- 备库数据文件状态
SELECT file#,
       name,
       status,
       enabled,
       ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb,
       checkpoint_change#,
       TO_CHAR(checkpoint_time, 'YYYY-MM-DD HH24:MI:SS') AS checkpoint_time
FROM v$datafile
ORDER BY file#;

-- 主备文件数量一致性
-- 主库: SELECT COUNT(*) FROM v$datafile;
-- 备库: SELECT COUNT(*) FROM v$datafile;
-- 主库: SELECT COUNT(*) FROM v$tempfile;
-- 备库: SELECT COUNT(*) FROM v$tempfile;
```

### 3.8 监听与网络可达性检查

```sql
-- 从主库 TNS 连接备库（仅测试连接）
-- 使用 tnsping <standby_tns_alias> 或 SQL*Plus 连接测试

-- 检查主库 DG 配置中备库的网络服务名
SELECT dest_id,
       destination,
       status,
       error
FROM v$archive_dest
WHERE destination IS NOT NULL;
```

### 3.9 校验结果汇总查询

```sql
-- 一键 DG 健康检查（主库）
SELECT 'DB_ROLE' AS check_item,
       database_role AS value,
       CASE WHEN database_role = 'PRIMARY' THEN 'PASS' ELSE 'FAIL' END AS result
FROM v$database
UNION ALL
SELECT 'SWITCHOVER_STATUS',
       switchover_status,
       CASE WHEN switchover_status IN ('TO STANDBY', 'SESSIONS ACTIVE') THEN 'PASS' ELSE 'FAIL' END
FROM v$database
UNION ALL
SELECT 'PROTECTION_MODE',
       protection_mode,
       'INFO'
FROM v$database
UNION ALL
SELECT 'DEST_STATUS',
       status,
       CASE WHEN status = 'VALID' THEN 'PASS' ELSE 'FAIL' END
FROM v$archive_dest_status
WHERE dest_id = 2
UNION ALL
SELECT 'GAP_STATUS',
       NVL(gap_status, 'NO GAP'),
       CASE WHEN NVL(gap_status, 'NO GAP') = 'NO GAP' THEN 'PASS' ELSE 'FAIL' END
FROM v$archive_dest_status
WHERE dest_id = 2;
```

---

## 四、切换执行命令

### 4.1 标准 SQL*Plus 切换（推荐）

#### 步骤 1：主库切换为备库

```sql
-- 主库执行：切换为 PHYSICAL STANDBY
-- 切换前确保 switchover_status 为 TO STANDBY 或 SESSIONS ACTIVE

-- 如果 switchover_status = TO STANDBY（无活动会话）
ALTER DATABASE COMMIT TO SWITCHOVER TO PHYSICAL STANDBY;

-- 如果 switchover_status = SESSIONS ACTIVE（有活动会话）
-- ALTER DATABASE COMMIT TO SWITCHOVER TO PHYSICAL STANDBY WITH SESSION SHUTDOWN;

-- 切换后关闭并启动到 MOUNT 状态
SHUTDOWN IMMEDIATE;
STARTUP MOUNT;
```

#### 步骤 2：备库切换为主库

```sql
-- 备库执行：切换为 PRIMARY
-- 切换前确认 switchover_status 为 TO PRIMARY

-- 验证切换通知已收到
SELECT switchover_status FROM v$database;

-- 执行切换
ALTER DATABASE COMMIT TO SWITCHOVER TO PRIMARY;

-- 打开数据库
ALTER DATABASE OPEN;
```

#### 步骤 3：新备库启动 MRP

```sql
-- 在新备库（原主库）上启动 Managed Recovery Process
ALTER DATABASE RECOVER MANAGED STANDBY DATABASE DISCONNECT FROM SESSION;
-- 或使用实时应用
ALTER DATABASE RECOVER MANAGED STANDBY DATABASE USING CURRENT LOGFILE DISCONNECT FROM SESSION;
```

### 4.2 DataGuard Broker 切换（DGMGRL）

```bash
# 通过 DataGuard Broker 执行切换（需已配置 Broker）

# 检查 DG 配置
dgmgrl / <<EOF
SHOW CONFIGURATION;
SHOW DATABASE '<primary_unique_name>';
SHOW DATABASE '<standby_unique_name>';
EOF

# 执行切换
dgmgrl / <<EOF
SWITCHOVER TO '<standby_unique_name>';
EOF

# 验证切换结果
dgmgrl / <<EOF
SHOW CONFIGURATION;
SHOW DATABASE '<standby_unique_name>';
EOF
```

### 4.3 切换流程时序图

```
时间线:
    T0: 开始切换前通告（业务方）
    T1: 前置校验通过 → 输出校验报告
    T2: 双签确认 → 用户确认执行
    T3: 主库执行 SWITCHOVER TO STANDBY（主库服务中断）
    T4: 原主库 SHUTDOWN → STARTUP MOUNT
    T5: 备库执行 SWITCHOVER TO PRIMARY
    T6: 新主库 OPEN（服务恢复）
    T7: 新备库启动 MRP（同步恢复）
    T8: 切换后验证 → 输出切换报告
```

---

## 五、切换后验证

### 5.1 角色确认

```sql
-- 新主库角色确认
SELECT name,
       db_unique_name,
       database_role,
       open_mode,
       switchover_status
FROM v$database;

-- 新备库角色确认
-- 同上在新备库执行
```

### 5.2 新备库同步状态

```sql
-- 新备库 MRP 状态
SELECT process,
       status,
       sequence#,
       thread#,
       block#,
       blocks
FROM v$managed_standby
WHERE process LIKE 'MRP%'
   OR process LIKE 'RFS%';

-- 新备库同步延迟
SELECT name,
       value,
       time_computed,
       datum_time
FROM v$dataguard_stats
WHERE name IN ('transport lag', 'apply lag', 'apply finish time');
```

### 5.3 新主库归档传输状态

```sql
-- 新主库归档传输到新备库
SELECT dest_id,
       dest_name,
       status,
       type,
       database_mode,
       error,
       recovery_mode,
       synchronizing_status,
       gap_status
FROM v$archive_dest_status
WHERE database_mode = 'STANDBY';
```

### 5.4 数据文件一致性

```sql
-- 新主库数据文件状态
SELECT file#,
       name,
       status,
       TO_CHAR(checkpoint_time, 'YYYY-MM-DD HH24:MI:SS') AS checkpoint_time
FROM v$datafile
WHERE status != 'ONLINE';

-- 新备库数据文件状态
-- 同上在新备库执行
```

### 5.5 新主库读写验证

```sql
-- 新主库读写测试（创建临时表验证后可删除）
CREATE TABLE switchover_rw_test (id NUMBER, test_time TIMESTAMP);
INSERT INTO switchover_rw_test VALUES (1, SYSTIMESTAMP);
SELECT * FROM switchover_rw_test;
DROP TABLE switchover_rw_test PURGE;
```

---

## 六、切换前后状态对比

| 检查项 | 切换前（主库） | 切换前（备库） | 切换后（新主库） | 切换后（新备库） |
|--------|-------------|-------------|----------------|----------------|
| 数据库角色 | PRIMARY | PHYSICAL STANDBY | PRIMARY | PHYSICAL STANDBY |
| DB_UNIQUE_NAME | <primary_name> | <standby_name> | <standby_name> | <primary_name> |
| OPEN_MODE | READ WRITE | READ ONLY WITH APPLY | READ WRITE | MOUNTED / READ ONLY WITH APPLY |
| SWITCHOVER_STATUS | TO STANDBY | TO PRIMARY | TO STANDBY | TO PRIMARY |
| SCN | <scn> | <scn> | <scn> | <scn> |
| 归档传输 | → standby | ← primary | → standby | ← primary |
| MRP 状态 | N/A | RUNNING | N/A | RUNNING |

---

## 七、回退方案

切换完成后如需回退（将角色恢复为切换前状态），执行反向 SWITCHOVER：

```sql
-- 反向 SWITCHOVER（在新主库执行）
-- 步骤 1：新主库切换为备库
ALTER DATABASE COMMIT TO SWITCHOVER TO PHYSICAL STANDBY;
SHUTDOWN IMMEDIATE;
STARTUP MOUNT;

-- 步骤 2：新备库切换为主库
ALTER DATABASE COMMIT TO SWITCHOVER TO PRIMARY;
ALTER DATABASE OPEN;

-- 步骤 3：新备库（原主库）启动 MRP
ALTER DATABASE RECOVER MANAGED STANDBY DATABASE DISCONNECT FROM SESSION;
```

**注意：** 回退操作同样需要双签审批，且切换过程中产生的数据变更会同步到对端，回退后数据一致。

---

## 八、切换前安全检查清单

| 检查项 | 检查方式 | 通过标准 | 阻断级别 |
|--------|----------|----------|----------|
| 双签审批 | approver_one ≠ approver_two ≠ 空 | 双人均已审批 | 阻断 |
| 主库角色 | `SELECT database_role FROM v$database;` | PRIMARY | 阻断 |
| 备库角色 | 同上在备库执行 | PHYSICAL STANDBY | 阻断 |
| Switchover 就绪 | `SELECT switchover_status FROM v$database;` | TO STANDBY / SESSIONS ACTIVE（主库） / TO PRIMARY（备库） | 阻断 |
| 归档传输状态 | `SELECT status FROM v$archive_dest_status WHERE dest_id=2;` | VALID | 阻断 |
| GAP 检查 | `SELECT gap_status FROM v$archive_dest_status WHERE dest_id=2;` | NO GAP | 阻断 |
| 同步延迟 | `SELECT * FROM v$dataguard_stats;` | apply lag < max_lag_seconds | 告警 |
| SRL 配置 | `SELECT COUNT(*) FROM v$standby_log;` | >= 在线 REDO 组数 + 1 | 告警 |
| SRL 大小 | 对比 v$standby_log.bytes 与 v$log.bytes | 大小一致 | 告警 |
| 数据文件数 | `SELECT COUNT(*) FROM v$datafile;` 主备对比 | 数量一致 | 阻断 |
| 数据文件状态 | `SELECT file#, status FROM v$datafile;` | 全部 ONLINE | 阻断 |
| FRA 空间 | `SELECT * FROM v$recovery_file_dest;` | used_pct < 85% | 告警 |
| 监听可达性 | tnsping / SQL*Plus 连接测试 | 可达 | 阻断 |
| 主库归档连续性 | `SELECT * FROM v$archive_gap;` | 无 GAP | 告警 |

---

## 九、异常处理

| 异常场景 | 处理方式 |
|----------|---------|
| 双签不完整 | 终止操作，提示需双人审批（approver_one + approver_two 均必填） |
| switchover_status ≠ TO STANDBY | 主库不满足切换条件，检查是否有活动备库角色或 DG 配置异常 |
| 备库 switchover_status ≠ TO PRIMARY | 备库未收到切换通知，检查归档传输与 GAP 状态 |
| 归档传输中断（status ≠ VALID） | 检查网络/监听/日志传输配置，修复后重新校验 |
| 存在 GAP（gap_status ≠ NO GAP） | 检查归档日志连续性，手动传输缺失的归档日志 |
| 同步延迟超过阈值 | 等待备库追平或扩大 max_lag_seconds，确认数据丢失风险 |
| SRL 配置不足 | 提示添加 SRL 组，建议配置为在线 REDO 组数 + 1 |
| FRA 空间不足 | 提示清理过期归档/备份，或扩展 FRA 空间 |
| 数据文件数量不一致 | 检查备库数据文件是否全部创建，执行 RECOVER 补齐 |
| 备库不可达 | 检查网络/监听/防火墙，确认备库服务正常 |
| 切换过程中主库断开 | 切换可能处于中间状态，需要 DBA 手动介入，检查 alert log |
| 切换后新备库 MRP 启动失败 | 检查 MRP 状态与 alert log，确认归档传输已恢复 |
| Broker 切换失败 | 检查 DGMGRL 配置状态，可能需要手动 SQL*Plus 切换 |

---

## 十、输出格式

结构化输出：
1. **双签审批记录**：审批人、审批时间、审批结果
2. **前置校验报告**：逐项检查结果（通过/告警/阻断），含具体数值
3. **校验结论**：是否允许切换，阻塞项详情与修复建议
4. **切换执行摘要**（如执行）：切换开始时间、结束时间、耗时、各步骤状态
5. **切换前后状态对比**：角色/SCN/同步状态/归档传输对比表
6. **切换后验证**：角色确认、同步状态、读写验证、数据文件一致性
7. **回退方案**：反向 SWITCHOVER 步骤