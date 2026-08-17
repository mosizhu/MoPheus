---
name: "db-oracle-restore"
description: "Oracle RMAN 恢复执行技能（高危，需双签）。核心能力：全量数据库恢复（RESTORE DATABASE + RECOVER DATABASE）、时间点恢复（PITR / UNTIL TIME / UNTIL SCN / UNTIL SEQUENCE）、表空间恢复（RESTORE TABLESPACE）、数据文件恢复（RESTORE DATAFILE）、控制文件恢复（RESTORE CONTROLFILE FROM AUTOBACKUP）、参数文件恢复（RESTORE SPFILE）、数据块恢复（BLOCKRECOVER）、恢复预览与校验（RESTORE PREVIEW / VALIDATE）、闪回数据库（FLASHBACK DATABASE）、表闪回（FLASHBACK TABLE）。适用场景：数据库灾难恢复（介质故障/数据文件损坏/误删数据）、时间点恢复（逻辑错误回退/误操作恢复）、表空间/数据文件级恢复、控制文件/参数文件丢失恢复、数据块逻辑损坏修复、恢复演练与验证。功能限制：恢复操作不可逆且覆盖当前数据库，必须通过双人审批（双签）后方可执行；不执行备份（BACKUP）、不执行 DDL/DML、不修改非恢复相关 RMAN 配置；恢复前必须完成前置校验（备份可用性/归档日志连续性/目标状态确认）。"
version: "v1.0.0"
tags: db-ops
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "restore_type"
    type: "string"
    required: true
    default: ""
    desc: "恢复类型：full（全量数据库恢复）/ pitr（时间点恢复，需指定 until_time/until_scn/until_sequence）/ tablespace（表空间恢复，需指定 tablespace_name）/ datafile（数据文件恢复，需指定 datafile_id）/ controlfile（控制文件恢复）/ spfile（参数文件恢复）/ blockrecover（数据块恢复，需指定 block_id）/ flashback_db（闪回数据库）/ flashback_table（表闪回，需指定 table_name）/ preview（仅预览恢复计划不执行）/ validate（仅校验备份可恢复性不实际恢复）"
  - name: "until_time"
    type: "string"
    required: false
    default: ""
    desc: "PITR 目标时间点（格式：YYYY-MM-DD HH24:MI:SS），仅 pitr 模式有效"
  - name: "until_scn"
    type: "string"
    required: false
    default: ""
    desc: "PITR 目标 SCN 号，仅 pitr 模式有效（与 until_time 二选一）"
  - name: "until_sequence"
    type: "string"
    required: false
    default: ""
    desc: "PITR 目标归档日志序列号（格式：thread,sequence），仅 pitr 模式有效"
  - name: "tablespace_name"
    type: "string"
    required: false
    default: ""
    desc: "待恢复表空间名称，仅 tablespace 模式有效，多个用逗号分隔"
  - name: "datafile_id"
    type: "string"
    required: false
    default: ""
    desc: "待恢复数据文件编号或路径，仅 datafile 模式有效，多个用逗号分隔"
  - name: "block_id"
    type: "string"
    required: false
    default: ""
    desc: "待恢复数据块信息（格式：datafile_id:block_id），仅 blockrecover 模式有效"
  - name: "table_name"
    type: "string"
    required: false
    default: ""
    desc: "待闪回的表名（格式：schema.table_name），仅 flashback_table 模式有效"
  - name: "flashback_scn"
    type: "string"
    required: false
    default: ""
    desc: "闪回目标 SCN，仅 flashback_table 模式有效（与 flashback_timestamp 二选一）"
  - name: "flashback_timestamp"
    type: "string"
    required: false
    default: ""
    desc: "闪回目标时间戳，仅 flashback_table 模式有效"
  - name: "restore_dest"
    type: "string"
    required: false
    default: ""
    desc: "恢复文件目标路径（仅控制文件/参数文件恢复时有效），为空则使用原始路径"
  - name: "parallelism"
    type: "integer"
    required: false
    default: 4
    desc: "恢复并行通道数，默认 4"
  - name: "approver_one"
    type: "string"
    required: false
    default: ""
    desc: "第一审批人标识（双签第一签，必填，高危操作须双人审批）"
  - name: "approver_two"
    type: "string"
    required: false
    default: ""
    desc: "第二审批人标识（双签第二签，必填，须与第一审批人不同）"
  - name: "open_resetlogs"
    type: "boolean"
    required: false
    default: true
    desc: "恢复完成后是否以 RESETLOGS 方式打开数据库（默认 true，PITR/控制文件恢复后必须 RESETLOGS）"
  - name: "dry_run"
    type: "boolean"
    required: false
    default: true
    desc: "是否为试运行模式（默认 true），true 时仅输出恢复计划与校验结果，不实际执行恢复"
support_db: oracle
safe_level: "danger"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle RMAN 恢复执行（高危，需双签）

> 执行 Oracle RMAN 恢复操作：全量数据库恢复、时间点恢复（PITR）、表空间/数据文件级恢复、控制文件/参数文件恢复、数据块恢复、闪回数据库/表闪回、恢复预览与校验。本技能为 **danger 级高危操作**，执行不可逆的数据库恢复，**必须完成双人审批（双签）后方可执行**。默认 dry_run=true 仅输出恢复计划。

## 核心能力
- 单一职责：Oracle RMAN 恢复执行（前置校验 → 双签审批 → 恢复计划确认 → 执行恢复 → 恢复后验证）。
- 覆盖全量恢复、时间点恢复（PITR）、表空间/数据文件级恢复、控制文件/SPFILE 恢复、数据块恢复。
- 支持闪回数据库（FLASHBACK DATABASE）与表闪回（FLASHBACK TABLE）作为轻量级恢复方案。
- 支持恢复预览（RESTORE PREVIEW）与备份校验（RESTORE VALIDATE）模式。

## 适用场景
- 数据库灾难恢复：存储介质故障、数据文件全部损坏
- 时间点恢复：逻辑错误回退（误删表/误改数据）、应用升级失败回滚
- 表空间/数据文件级恢复：单个表空间或数据文件损坏
- 控制文件丢失：所有控制文件损坏或丢失
- 参数文件丢失：SPFILE 损坏或丢失
- 数据块逻辑损坏：DBVERIFY 检测到坏块
- 闪回操作：DROP TABLE 误删恢复、表数据误改回退
- 恢复演练：定期验证备份可恢复性

## 功能限制 / 安全边界
- 不执行备份（不执行 BACKUP DATABASE / BACKUP ARCHIVELOG）
- 不修改非恢复相关 RMAN 配置（不执行 CONFIGURE）
- 不执行 DDL/DML（恢复操作本身已覆盖数据库，不额外修改数据）
- 恢复操作 **不可逆**，一旦执行将覆盖当前数据库文件
- PITR / 控制文件恢复后必须 RESETLOGS 打开，意味着新的化身（INCARNATION）开始
- 表空间/数据文件恢复期间目标对象处于 OFFLINE 状态，影响业务访问
- 闪回数据库需要开启闪回日志（FLASHBACK ON）且闪回目标在闪回保留窗口内
- 表闪回（FLASHBACK TABLE）依赖 UNDO 数据，超时则无法闪回
- **本操作为 danger 级，必须双人审批（双签）后方可执行**

---

## 零、双签审批流程（高危操作强制要求）

```
恢复请求发起
    |
    v
[审批人一] 审核恢复计划
    | 确认恢复类型、目标时间点、影响范围
    | 确认备份可用性与归档日志连续性
    | 确认 dry_run 校验已通过
    | 审批人标识: approver_one
    v
[审批人二] 复核确认
    | 独立复核恢复计划与校验结果
    | 确认 approver_one 与 approver_two 不同
    | 审批人标识: approver_two
    v
[双签通过] dry_run=false 执行恢复
    | 记录双签信息到恢复日志
    v
[恢复执行] 不得中途取消
```

> **双签不通过时，不得执行恢复。** 即使 dry_run=false，若 approver_one 或 approver_two 为空或相同，拒绝执行并提示完成双签。

---

## 一、推理框架：RMAN 恢复执行链

```
用户提出恢复需求（恢复类型/目标/范围）
    |
    v
[1] 前置校验（只读，不执行恢复）
    | 数据库当前状态（OPEN / MOUNT / NOMOUNT）
    | 备份可用性检查（RESTORE PREVIEW / LIST BACKUP）
    | 归档日志连续性检查（是否有日志缺失）
    | 恢复目标时间点/SCH 合法性验证
    | 恢复所需空间估算
    | 双签状态检查（approver_one / approver_two）
    v
[2] 恢复计划输出
    | 恢复类型与范围
    | 将使用的备份集清单（备份集号/时间/大小）
    | 需要应用的归档日志范围
    | 预估恢复时间
    | 恢复后数据库状态（OPEN RESETLOGS / READ WRITE）
    | 影响范围（哪些表空间/数据文件受影响）
    v
[3] dry_run 校验（默认 true 时至此结束）
    | 输出完整恢复计划，不实际执行
    | 提示切换 dry_run=false 并完成双签后执行
    v
[4] 执行恢复（dry_run=false + 双签通过）
    | 关闭/启动数据库到目标状态（MOUNT / NOMOUNT）
    | 执行 RESTORE 命令（从备份恢复文件）
    | 执行 RECOVER 命令（应用归档日志/增量备份）
    | OPEN DATABASE（RESETLOGS 或正常打开）
    | 恢复临时表空间 TEMPFILE
    v
[5] 恢复后验证
    | 数据库打开状态验证
    | 数据文件 ONLINE 状态验证
    | 关键表数据抽样验证
    | 归档日志连续性验证
    v
[6] 结果输出
    | 恢复作业摘要（是否成功/耗时/恢复到的 SCN/时间）
    | 恢复后数据库状态
    | 后续操作建议（全量备份/归档日志备份）
```

---

## 二、前置校验（只读，不执行恢复）

### 2.1 数据库当前状态

```sql
-- 数据库状态（必须确认恢复前状态）
SELECT name AS db_name,
       open_mode,
       log_mode,
       database_role,
       flashback_on,
       TO_CHAR(current_scn) AS current_scn,
       TO_CHAR(controlfile_type) AS controlfile_type
FROM v$database;

-- 实例状态
SELECT instance_name,
       host_name,
       version_full,
       status,
       TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time,
       database_status
FROM v$instance;

-- 数据文件状态
SELECT file#,
       name,
       status,
       enabled,
       ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb,
       TO_CHAR(checkpoint_time, 'YYYY-MM-DD HH24:MI:SS') AS ckp_time
FROM v$datafile
ORDER BY file#;

-- 控制文件清单
SELECT name, status FROM v$controlfile;

-- 当前 REDO 日志组
SELECT group#, thread#, sequence#, bytes / 1024 / 1024 AS size_mb, status
FROM v$log
ORDER BY group#;

-- 当前化身（INCARNATION）
SELECT incarnation#,
       status,
       TO_CHAR(resetlogs_time, 'YYYY-MM-DD HH24:MI:SS') AS resetlogs_time,
       prior_incarnation#
FROM v$database_incarnation
WHERE status = 'CURRENT';
```

### 2.2 备份可用性检查

```sql
-- 备份集摘要（最近 30 天）
SELECT bs_key,
       backup_type,
       incremental_level,
       status,
       ROUND(input_bytes / 1024 / 1024 / 1024, 2) AS input_gb,
       ROUND(output_bytes / 1024 / 1024 / 1024, 2) AS output_gb,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI:SS') AS completion_time,
       tag
FROM v$backup_set
WHERE completion_time > SYSDATE - 30
  AND backup_type IN ('D', 'I')  -- D=Full, I=Incremental
ORDER BY completion_time DESC;

-- 归档日志备份状态
SELECT thread#,
       sequence#,
       TO_CHAR(first_time, 'YYYY-MM-DD HH24:MI:SS') AS first_time,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI:SS') AS completion_time,
       status,
       backed_up
FROM v$archived_log
WHERE completion_time > SYSDATE - 7
ORDER BY completion_time DESC;
```

### 2.3 恢复目标时间点校验

```sql
-- 校验 PITR 目标时间点是否在备份覆盖范围内
-- 最早可用备份时间
SELECT MIN(completion_time) AS earliest_backup_time
FROM v$backup_set
WHERE backup_type IN ('D', 'I');

-- 最早可用归档日志时间
SELECT MIN(completion_time) AS earliest_arch_time
FROM v$archived_log
WHERE backed_up = 'YES'
  AND deleted = 'NO';

-- 待恢复目标时间点：<until_time>
-- 必须在 earliest_arch_time 之后，earliest_backup_time 之后
```

### 2.4 闪回数据库前置检查

```sql
-- 闪回数据库是否开启
SELECT flashback_on FROM v$database;

-- 闪回保留目标（分钟）
SELECT name, value / 60 AS retention_hours
FROM v$parameter
WHERE name = 'db_flashback_retention_target';

-- 最早可闪回时间点
SELECT TO_CHAR(oldest_flashback_time, 'YYYY-MM-DD HH24:MI:SS') AS oldest_flashback_time,
       TO_CHAR(oldest_flashback_scn) AS oldest_flashback_scn
FROM v$flashback_database_log;

-- 闪回日志大小
SELECT ROUND(flashback_size / 1024 / 1024 / 1024, 2) AS flashback_gb,
       ROUND(estimated_flashback_size / 1024 / 1024 / 1024, 2) AS estimated_flashback_gb
FROM v$flashback_database_log;
```

### 2.5 表闪回前置检查

```sql
-- 检查表是否可闪回（UNDO 数据是否足够）
-- 闪回目标时间必须大于 UNDO_RETENTION 覆盖的时间范围
SELECT name, value / 60 AS undo_retention_minutes
FROM v$parameter
WHERE name = 'undo_retention';

-- 当前 UNDO 表空间大小与使用率
SELECT tablespace_name,
       ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) AS total_gb,
       ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) - ROUND(SUM(free_bytes) / 1024 / 1024 / 1024, 2) AS used_gb
FROM (
    SELECT tablespace_name, bytes FROM dba_data_files WHERE tablespace_name LIKE 'UNDO%'
    UNION ALL
    SELECT tablespace_name, 0 AS bytes FROM dba_free_space WHERE tablespace_name LIKE 'UNDO%'
)
GROUP BY tablespace_name;
```

### 2.6 恢复空间估算

```bash
# 检查恢复目标路径磁盘空间
df -h <datafile_dest_path>
df -h <tempfile_dest_path>

# 估算恢复所需空间（约为数据库大小 + 归档日志大小）
# 查看当前数据文件总大小
# SELECT ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) AS total_gb FROM v$datafile;
```

---

## 三、恢复执行命令

### 3.1 全量数据库恢复（RESTORE DATABASE + RECOVER DATABASE）

> 适用场景：所有数据文件损坏/丢失、存储介质故障、数据库完全不可用

```bash
# === Oracle RMAN 全量数据库恢复 ===
# 前置条件：数据库处于 MOUNT 状态（或可启动到 MOUNT）
# 恢复后：数据库 OPEN，数据文件 ONLINE

rman target / <<EOF
STARTUP MOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK;

  RESTORE DATABASE;
  RECOVER DATABASE;

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

ALTER DATABASE OPEN;
EXIT;
EOF
```

### 3.2 时间点恢复（PITR - UNTIL TIME）

> 适用场景：逻辑错误回退（误删表/误改数据）、应用升级失败回滚到指定时间点

```bash
# === Oracle RMAN 时间点恢复（PITR - UNTIL TIME） ===
# 恢复到指定时间点，之后的所有变更将丢失
# 恢复后必须以 RESETLOGS 方式打开

rman target / <<EOF
STARTUP MOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK;

  SET UNTIL TIME "TO_DATE('${UNTIL_TIME}', 'YYYY-MM-DD HH24:MI:SS')";
  RESTORE DATABASE;
  RECOVER DATABASE;

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

ALTER DATABASE OPEN RESETLOGS;
EXIT;
EOF
```

### 3.3 时间点恢复（PITR - UNTIL SCN）

```bash
# === Oracle RMAN 时间点恢复（PITR - UNTIL SCN） ===
# 恢复到指定 SCN 号

rman target / <<EOF
STARTUP MOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK;

  SET UNTIL SCN ${UNTIL_SCN};
  RESTORE DATABASE;
  RECOVER DATABASE;

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

ALTER DATABASE OPEN RESETLOGS;
EXIT;
EOF
```

### 3.4 时间点恢复（PITR - UNTIL SEQUENCE）

```bash
# === Oracle RMAN 时间点恢复（PITR - UNTIL SEQUENCE） ===
# 恢复到指定归档日志序列号

rman target / <<EOF
STARTUP MOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK;

  SET UNTIL SEQUENCE ${UNTIL_SEQUENCE};
  RESTORE DATABASE;
  RECOVER DATABASE;

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

ALTER DATABASE OPEN RESETLOGS;
EXIT;
EOF
```

### 3.5 表空间恢复（RESTORE TABLESPACE + RECOVER TABLESPACE）

> 适用场景：单个或多个表空间数据文件损坏，其他表空间正常

```bash
# === Oracle RMAN 表空间恢复 ===
# 恢复期间目标表空间 OFFLINE，业务不可访问该表空间
# 恢复后表空间 ONLINE

rman target / <<EOF

RUN {
  -- 将目标表空间 OFFLINE
  SQL "ALTER TABLESPACE ${TABLESPACE_NAME} OFFLINE IMMEDIATE";

  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK;

  RESTORE TABLESPACE ${TABLESPACE_NAME};
  RECOVER TABLESPACE ${TABLESPACE_NAME};

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;

  -- 恢复后 ONLINE
  SQL "ALTER TABLESPACE ${TABLESPACE_NAME} ONLINE";
}

EXIT;
EOF
```

### 3.6 数据文件恢复（RESTORE DATAFILE + RECOVER DATAFILE）

> 适用场景：单个或多个数据文件损坏/丢失

```bash
# === Oracle RMAN 数据文件恢复 ===
# 恢复期间目标数据文件 OFFLINE
# 恢复后可 ONLINE

rman target / <<EOF

RUN {
  -- 将目标数据文件 OFFLINE
  SQL "ALTER DATABASE DATAFILE ${DATAFILE_ID} OFFLINE";

  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;

  RESTORE DATAFILE ${DATAFILE_ID};
  RECOVER DATAFILE ${DATAFILE_ID};

  RELEASE CHANNEL ch1;

  -- 恢复后 ONLINE
  SQL "ALTER DATABASE DATAFILE ${DATAFILE_ID} ONLINE";
}

EXIT;
EOF
```

### 3.7 控制文件恢复（RESTORE CONTROLFILE FROM AUTOBACKUP）

> 适用场景：所有控制文件损坏或丢失，数据库无法启动到 MOUNT

```bash
# === Oracle RMAN 控制文件恢复（从自动备份） ===
# 前置条件：数据库处于 NOMOUNT 状态，需指定 DBID
# 恢复后需 MOUNT 数据库并执行 RECOVER，最后 RESETLOGS 打开

rman target / <<EOF
STARTUP NOMOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;

  -- 从自动备份恢复控制文件（需指定 DBID）
  -- SET DBID <dbid>;
  RESTORE CONTROLFILE FROM AUTOBACKUP;

  RELEASE CHANNEL ch1;
}

ALTER DATABASE MOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK;

  RECOVER DATABASE;

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
}

ALTER DATABASE OPEN RESETLOGS;
EXIT;
EOF
```

### 3.8 参数文件恢复（RESTORE SPFILE）

> 适用场景：SPFILE 损坏或丢失，数据库无法启动到 NOMOUNT

```bash
# === Oracle RMAN 参数文件恢复（从自动备份） ===
# 前置条件：数据库未启动，需指定 DBID
# 恢复后 SPFILE 在默认位置或指定路径

rman target / <<EOF
STARTUP NOMOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;

  -- 从自动备份恢复 SPFILE 到指定路径
  RESTORE SPFILE TO '${RESTORE_DEST}/spfile${ORACLE_SID}.ora' FROM AUTOBACKUP;

  -- 或恢复到默认位置
  -- RESTORE SPFILE FROM AUTOBACKUP;

  RELEASE CHANNEL ch1;
}

-- 使用恢复的 SPFILE 重启实例
SHUTDOWN IMMEDIATE;
STARTUP;
EXIT;
EOF
```

### 3.9 数据块恢复（BLOCKRECOVER）

> 适用场景：DBVERIFY 或 v$database_block_corruption 检测到特定数据块逻辑损坏

```bash
# === Oracle RMAN 数据块恢复（BLOCKRECOVER） ===
# 仅恢复指定数据块，不影响其他数据，无需 OFFLINE 数据文件
# 恢复期间数据块不可访问，可能导致短暂行锁等待

rman target / <<EOF

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;

  -- 恢复单个数据块
  BLOCKRECOVER DATAFILE ${DATAFILE_ID} BLOCK ${BLOCK_ID};

  -- 恢复多个数据块
  -- BLOCKRECOVER DATAFILE ${DATAFILE_ID} BLOCK ${BLOCK_ID_1}, ${BLOCK_ID_2};

  -- 自动恢复所有已知坏块
  -- BLOCKRECOVER CORRUPTION LIST;

  RELEASE CHANNEL ch1;
}

EXIT;
EOF
```

### 3.10 闪回数据库（FLASHBACK DATABASE）

> 适用场景：逻辑错误回退（如误删表、误改大量数据），比 PITR 更快，无需从备份恢复

```bash
# === Oracle 闪回数据库（FLASHBACK DATABASE） ===
# 前置条件：数据库开启 FLASHBACK ON，闪回目标在闪回保留窗口内
# 比 PITR 恢复更快，无需从备份恢复文件

rman target / <<EOF
STARTUP MOUNT;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;

  -- 闪回到指定时间点
  FLASHBACK DATABASE TO TIME "TO_DATE('${FLASHBACK_TIMESTAMP}', 'YYYY-MM-DD HH24:MI:SS')";

  -- 或闪回到指定 SCN
  -- FLASHBACK DATABASE TO SCN ${FLASHBACK_SCN};

  -- 或闪回到指定还原点
  -- FLASHBACK DATABASE TO RESTORE POINT '<restore_point_name>';

  RELEASE CHANNEL ch1;
}

-- 以只读方式打开验证数据
ALTER DATABASE OPEN READ ONLY;

-- 验证数据无误后，RESETLOGS 打开
-- SHUTDOWN IMMEDIATE;
-- STARTUP MOUNT;
-- ALTER DATABASE OPEN RESETLOGS;

EXIT;
EOF
```

### 3.11 表闪回（FLASHBACK TABLE）

> 适用场景：误删表后从回收站恢复（FLASHBACK TABLE TO BEFORE DROP）、误改表数据后回退到历史时间点

```bash
# === Oracle 表闪回（FLASHBACK TABLE） ===
# 使用 RMAN 调用 SQL 执行闪回

sqlplus / as sysdba <<EOF

-- 方式一：从回收站恢复误删的表（FLASHBACK TABLE TO BEFORE DROP）
FLASHBACK TABLE ${TABLE_NAME} TO BEFORE DROP;

-- 如果表名已被占用，重命名恢复
-- FLASHBACK TABLE ${TABLE_NAME} TO BEFORE DROP RENAME TO ${TABLE_NAME}_recovered;

-- 方式二：闪回到指定时间点（需开启行移动）
ALTER TABLE ${TABLE_NAME} ENABLE ROW MOVEMENT;
FLASHBACK TABLE ${TABLE_NAME} TO TIMESTAMP TO_TIMESTAMP('${FLASHBACK_TIMESTAMP}', 'YYYY-MM-DD HH24:MI:SS');

-- 方式三：闪回到指定 SCN
-- ALTER TABLE ${TABLE_NAME} ENABLE ROW MOVEMENT;
-- FLASHBACK TABLE ${TABLE_NAME} TO SCN ${FLASHBACK_SCN};

-- 验证
SELECT COUNT(*) FROM ${TABLE_NAME};

EXIT;
EOF
```

---

## 四、恢复预览与校验（不实际恢复）

### 4.1 恢复预览（RESTORE PREVIEW）

```bash
# === RMAN 恢复预览 ===
# 输出恢复计划，不实际执行恢复
# 可查看恢复所需的备份集与归档日志清单

rman target / <<EOF

-- 全量恢复预览
RESTORE DATABASE PREVIEW;

-- PITR 恢复预览
-- RESTORE DATABASE PREVIEW UNTIL TIME "TO_DATE('${UNTIL_TIME}', 'YYYY-MM-DD HH24:MI:SS')";

-- 恢复预览摘要
RESTORE DATABASE PREVIEW SUMMARY;

EXIT;
EOF
```

### 4.2 备份校验（RESTORE VALIDATE / VALIDATE）

```bash
# === RMAN 备份校验（不实际恢复） ===
# 验证备份集可恢复性，不写入任何数据文件

rman target / <<EOF

-- 校验全量恢复链
RESTORE DATABASE VALIDATE;

-- 校验 PITR 恢复链
-- RESTORE DATABASE VALIDATE UNTIL TIME "TO_DATE('${UNTIL_TIME}', 'YYYY-MM-DD HH24:MI:SS')";

-- 校验归档日志恢复链
RESTORE ARCHIVELOG ALL VALIDATE;

-- 校验特定数据文件
-- RESTORE DATAFILE ${DATAFILE_ID} VALIDATE;

-- 物理+逻辑完整性校验
-- BACKUP VALIDATE CHECK LOGICAL DATABASE;

EXIT;
EOF
```

### 4.3 校验恢复演

```bash
# === 完整恢复演练（建议每季度执行） ===
# 在生产环境之外的异机执行完整恢复流程，验证：
# 1. 备份集可恢复性
# 2. 归档日志连续性
# 3. 恢复时间是否满足 RTO
# 4. 恢复后数据一致性

# 异机恢复演练步骤：
# 1. 将备份集与归档日志复制到演机
# 2. 创建与生产相同的目录结构
# 3. 使用 RMAN DUPLICATE 或手动 RESTORE
# 4. 恢复完成后验证数据
# 5. 记录恢复耗时，评估 RTO 达标情况
```

---

## 五、恢复后验证

### 5.1 数据库状态验证

```sql
-- 数据库打开状态
SELECT name, open_mode, log_mode, database_role, flashback_on
FROM v$database;

-- 实例状态
SELECT instance_name, status, TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time
FROM v$instance;

-- 当前化身（INCARNATION）
SELECT incarnation#,
       status,
       TO_CHAR(resetlogs_time, 'YYYY-MM-DD HH24:MI:SS') AS resetlogs_time,
       TO_CHAR(resetlogs_scn) AS resetlogs_scn
FROM v$database_incarnation
WHERE status = 'CURRENT';
```

### 5.2 数据文件状态验证

```sql
-- 数据文件状态（全部应为 ONLINE）
SELECT file#, name, status, enabled, online_status,
       ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb
FROM v$datafile
ORDER BY file#;

-- 检查是否有需要恢复的数据文件
SELECT file#, name, status, error, recover
FROM v$datafile_header
WHERE error IS NOT NULL OR recover = 'YES';

-- 临时文件状态
SELECT file#, name, status, ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb
FROM v$tempfile
ORDER BY file#;
```

### 5.3 恢复完成后补充临时表空间

```bash
# === 恢复完成后补充临时表空间 TEMPFILE ===
# 全量恢复后临时表空间 TEMPFILE 可能丢失，需要重新添加

sqlplus / as sysdba <<EOF

-- 检查临时文件状态
SELECT tablespace_name, file_name, bytes / 1024 / 1024 / 1024 AS size_gb, status
FROM dba_temp_files;

-- 如果临时文件丢失，添加 TEMPFILE
ALTER TABLESPACE TEMP ADD TEMPFILE '/<path>/temp01.dbf'
  SIZE 32G AUTOEXTEND ON NEXT 1G MAXSIZE 64G;

-- 验证
SELECT tablespace_name, file_name, bytes / 1024 / 1024 / 1024 AS size_gb, status
FROM dba_temp_files;

EXIT;
EOF
```

### 5.4 数据一致性抽样验证

```sql
-- 关键业务表行数验证
SELECT COUNT(*) AS row_count FROM <schema>.<key_table>;

-- 恢复后 SCN 与目标 SCN 对比
SELECT TO_CHAR(current_scn) AS current_scn FROM v$database;

-- 归档日志连续性验证
SELECT thread#, sequence#, first_time, next_time
FROM v$archived_log
WHERE completion_time > SYSDATE - 1
ORDER BY thread#, sequence#;
```

---

## 六、恢复场景决策矩阵

| 故障场景 | 数据库状态 | 推荐恢复方式 | 恢复步骤 | 预计耗时 |
|---------|-----------|-------------|---------|---------|
| 单个数据文件损坏 | OPEN | 数据文件恢复 | OFFLINE → RESTORE + RECOVER → ONLINE | 分钟级 |
| 单个表空间损坏 | OPEN | 表空间恢复 | OFFLINE → RESTORE + RECOVER → ONLINE | 分钟级 |
| 多个数据文件损坏 | MOUNT 或 CRASH | 全量恢复 | RESTORE + RECOVER → OPEN | 小时级 |
| 所有数据文件丢失 | NOMOUNT | 全量恢复 | RESTORE + RECOVER → OPEN | 小时级 |
| 控制文件全部丢失 | NOMOUNT | 控制文件恢复 | RESTORE CONTROLFILE → MOUNT → RECOVER → RESETLOGS | 分钟级 |
| SPFILE 丢失 | 无法启动 | SPFILE 恢复 | RESTORE SPFILE → 重启 | 分钟级 |
| 逻辑错误（误删表） | OPEN | 表闪回 | FLASHBACK TABLE TO BEFORE DROP | 秒级 |
| 逻辑错误（误改数据） | OPEN | PITR 或表闪回 | PITR: MOUNT → RESTORE+RECOVER → RESETLOGS | 小时级 |
| 逻辑错误（大量误操作） | OPEN | 闪回数据库 | MOUNT → FLASHBACK DATABASE → READ ONLY 验证 → RESETLOGS | 分钟级 |
| 数据块逻辑损坏 | OPEN | 数据块恢复 | BLOCKRECOVER | 分钟级 |
| DROP TABLESPACE 误删 | MOUNT | 全量 PITR | PITR 到删除前时间点 → RESETLOGS | 小时级 |

---

## 七、恢复最佳实践

### 7.1 恢复前检查清单

1. 确认数据库当前状态（v$database / v$instance）
2. 确认备份可用性（LIST BACKUP / RESTORE PREVIEW）
3. 确认归档日志连续性（v$archived_log 无缺失）
4. 确认恢复目标时间点（PITR）/SCN 在备份覆盖范围内
5. 确认恢复目标路径有足够磁盘空间（至少 1.5 倍数据库大小）
6. 确认双签已通过（approver_one / approver_two 均非空且不同）
7. 确认 dry_run 校验已通过（RESTORE VALIDATE）
8. 通知业务方恢复窗口与影响范围
9. 记录当前 SCN 与时间（用于恢复后对比）
10. 如有条件，先备份当前控制文件与控制文件自动备份

### 7.2 恢复后必做操作

1. 立即执行全量备份（RESETLOGS 后无法使用之前的增量备份）
2. 补充临时表空间 TEMPFILE（全量恢复后 TEMPFILE 丢失）
3. 验证关键业务表数据完整性
4. 验证归档日志正常生成
5. 更新监控告警规则
6. 记录恢复事件与耗时

### 7.3 恢复并行度建议

| 场景 | 建议 parallelism | 说明 |
|------|-----------------|------|
| 小库（< 100GB） | 2 | 减少 IO 影响 |
| 中库（100GB ~ 1TB） | 4 | 默认推荐值 |
| 大库（> 1TB） | 8 | 缩短恢复时间 |
| 控制文件/SPFILE 恢复 | 1 | 单通道即可 |

### 7.4 恢复时间预估

```
恢复时间 ≈ 备份集恢复时间 + 归档日志应用时间 + 数据库打开时间

全量备份恢复时间 ≈ Database_Size_GB / 恢复速率(GB/h)
归档日志应用时间 ≈ 归档日志总大小 / 恢复速率
数据库打开时间 ≈ 实例恢复（SMON） + 临时表空间重建

典型恢复速率：
  - 本地 SSD: 200-500 GB/h
  - 本地 HDD: 100-200 GB/h
  - NFS/网络存储: 50-150 GB/h
  - 磁带: 30-80 GB/h（含寻道时间）
```

---

## 八、异常处理

| 异常场景 | 处理方式 |
|----------|---------|
| 备份集不可用（EXPIRED） | 中断恢复，提示备份集已过期，检查备份集物理文件是否存在 |
| 归档日志缺失（GAP） | 中断恢复，提示缺失的归档日志序列号范围，检查是否有额外备份 |
| 恢复目标时间点超出备份覆盖范围 | 中断恢复，提示最早可恢复时间点，调整 until_time 参数 |
| 恢复空间不足 | 中断恢复，提示所需空间与可用空间差值，建议扩容或更换路径 |
| 恢复过程中断（网络/存储故障） | 重新执行恢复，RMAN 自动跳过已恢复的文件 |
| 控制文件恢复后无法 MOUNT | 检查 DBID 是否正确，检查控制文件备份位置 |
| RESETLOGS 打开失败 | 检查 REDO 日志组状态，可能需要 CLEAR LOGFILE |
| 临时表空间文件丢失 | 恢复后手动 ADD TEMPFILE |
| 双签未通过 | 拒绝执行恢复，提示完成双人审批（approver_one 与 approver_two 须不同且非空） |
| 闪回数据库目标超出保留窗口 | 提示最早可闪回时间点，建议改用 PITR 恢复 |
| 表闪回 UNDO 数据不足 | 提示 ORA-01555 快照太旧，建议改用 PITR 恢复 |
| 数据库未处于 ARCHIVELOG 模式 | PITR 不可用，提示仅支持全量恢复 |
| 本技能执行实际 RMAN 恢复操作，单次执行耗时取决于数据量与恢复类型，无第三方依赖、无常驻逻辑。 |

---

## 输出格式

结构化输出：

1. **前置校验结果**
   - 数据库当前状态（名称/OPEN_MODE/LOG_MODE/CURRENT_SCN）
   - 备份可用性（最近备份时间/类型/大小）
   - 归档日志连续性（是否缺失）
   - 恢复目标校验（时间点/SCN 是否在覆盖范围内）
   - 恢复空间检查（目标路径可用空间）

2. **双签审批状态**
   - approver_one: 审批人一标识
   - approver_two: 审批人二标识
   - 双签状态: 通过 / 未通过

3. **恢复计划**（dry_run 模式下输出）
   - 恢复类型与范围
   - 将使用的备份集清单（备份集号/时间/大小/TAG）
   - 需要应用的归档日志范围（序列号/时间范围）
   - 预估恢复时间
   - 恢复后数据库状态（OPEN RESETLOGS / READ WRITE）
   - 受影响的表空间/数据文件

4. **恢复执行摘要**（dry_run=false 时输出）
   - 恢复开始时间/结束时间/总耗时
   - 恢复后 SCN 与时间
   - 恢复状态（成功/失败）

5. **恢复后验证结果**
   - 数据库打开状态
   - 数据文件 ONLINE 状态
   - 恢复后 SCN 对比
   - 关键表数据抽样

6. **后续操作建议**
   - 立即全量备份
   - 补充临时表空间
   - 验证归档日志
   - 更新监控