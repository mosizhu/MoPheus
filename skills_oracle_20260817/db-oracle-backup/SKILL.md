---
name: "db-oracle-backup"
description: "Oracle RMAN 备份执行技能。核心能力：执行全量备份（FULL/LEVEL 0）、增量备份（差异增量/累积增量 LEVEL 1）、归档日志备份、备份校验与交叉检查、备份集删除清理、备份状态查询。适用场景：日常备份执行、按需临时备份、备份策略自动化调度、备份验证与清理。功能限制：不执行数据库恢复（RESTORE/RECOVER）、不修改非备份相关 RMAN 配置（如加密/压缩策略由 db-oracle-plan-backup 方案决定）、不执行 DDL/DML；高危操作（DELETE OBSOLETE/EXPIRED）需明确确认后执行。"
version: "v1.0.0"
tags: db-ops
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "backup_type"
    type: "string"
    required: false
    default: "full"
    desc: "备份类型：full（全量备份）/ incr0（增量 LEVEL 0 基准备份）/ incr1_diff（差异增量 LEVEL 1）/ incr1_cuml（累积增量 LEVEL 1）/ archivelog（仅归档日志备份）/ validate（仅校验备份不执行备份）/ crosscheck（交叉检查）/ status（仅查询备份状态）"
  - name: "backup_dest"
    type: "string"
    required: false
    default: "disk"
    desc: "备份目标介质：disk（磁盘）/ tape（磁带）"
  - name: "backup_path"
    type: "string"
    required: false
    default: "/backup"
    desc: "磁盘备份路径（仅 disk 模式有效），默认 /backup"
  - name: "parallelism"
    type: "integer"
    required: false
    default: 4
    desc: "备份并行通道数，默认 4"
  - name: "compression"
    type: "string"
    required: false
    default: ""
    desc: "压缩算法：BASIC / LOW / MEDIUM / HIGH，为空则不压缩"
  - name: "tag"
    type: "string"
    required: false
    default: ""
    desc: "备份集标签（TAG），为空则自动生成"
  - name: "include_archivelog"
    type: "boolean"
    required: false
    default: true
    desc: "全量/增量备份时是否同时备份归档日志并删除已备份的归档（默认 true）"
  - name: "delete_obsolete"
    type: "boolean"
    required: false
    default: false
    desc: "备份完成后是否清理过期备份（需确认，默认 false）"
  - name: "duration_minutes"
    type: "integer"
    required: false
    default: 0
    desc: "备份窗口限制（分钟），0 表示不限制，超时自动中断"
  - name: "rate_limit_mb"
    type: "integer"
    required: false
    default: 0
    desc: "备份速率限制（MB/s），0 表示不限制"
support_db: oracle
safe_level: "danger"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle RMAN 备份执行

> 执行 Oracle RMAN 备份操作：全量备份、增量备份（差异/累积）、归档日志备份、备份校验与交叉检查、备份集清理、备份状态查询。本技能为 danger 级操作技能，实际执行 RMAN 命令，使用前需确认备份策略与窗口。

## 核心能力
- 单一职责：Oracle RMAN 备份执行（备份类型选型 → 通道配置 → 备份执行 → 后处理校验/清理）。
- 覆盖全量备份、增量 LEVEL 0 基准、增量 LEVEL 1（差异/累积）、归档日志备份、备份校验、交叉检查、过期备份清理。
- 支持磁盘（DISK）与磁带（SBT_TAPE）两种目标介质。

## 适用场景
- 日常定时备份执行（全量/增量/归档日志）
- 数据库变更前（升级/迁移/DDL）的临时全量备份
- 备份策略调整后的首次基准备份
- 归档日志积压时的紧急备份清理
- 备份校验与交叉检查（定期验证备份可恢复性）
- 备份集过期清理与空间回收
- 备份作业状态查询与历史回溯

## 功能限制 / 安全边界
- 不执行数据库恢复（不执行 RESTORE DATABASE / RECOVER DATABASE / DUPLICATE）
- 不修改非备份相关 RMAN 配置（加密/压缩策略应由 db-oracle-plan-backup 方案确定后人工配置）
- 不执行 DDL/DML（不创建/删除表空间、不修改数据）
- 不 KILL 会话、不修改数据库参数
- DELETE OBSOLETE / DELETE EXPIRED BACKUP 需明确设置 `delete_obsolete=true` 才执行
- 单次执行耗时取决于备份数据量，大库备份可能耗时数小时

---

## 一、推理框架：RMAN 备份执行链

```
用户提出备份执行需求（备份类型/目标/并行度）
    |
    v
[1] 前置检查
    | 数据库状态（OPEN / MOUNT / NOMOUNT）
    | 归档模式确认（ARCHIVELOG）
    | 备份目标路径可用性（磁盘空间检查）
    | 当前备份状态（最近备份时间/类型）
    v
[2] 通道配置
    | 根据 parallelism 分配通道数
    | 磁盘模式：FORMAT 路径 + 压缩（如启用）
    | 磁带模式：SBT_TAPE 通道 + 多路复用
    v
[3] 备份执行
    | 全量备份：BACKUP DATABASE + ARCHIVELOG（可选）
    | 增量 LEVEL 0：等同全量，标记为增量基准
    | 增量 LEVEL 1 DIFFERENTIAL：差异增量
    | 增量 LEVEL 1 CUMULATIVE：累积增量
    | 归档日志备份：BACKUP ARCHIVELOG + DELETE INPUT
    v
[4] 后处理
    | 交叉检查（CROSSCHECK BACKUP）
    | 过期备份清理（DELETE OBSOLETE，如启用）
    | 备份校验（VALIDATE BACKUPSET）
    v
[5] 结果输出
    | 备份作业状态（成功/失败/耗时）
    | 备份集大小与压缩比
    | 备份片路径与 TAG
    | 备份状态汇总
```

---

## 二、前置检查（只读 SQL）

### 2.1 数据库状态与归档模式

```sql
-- 数据库状态
SELECT name AS db_name,
       open_mode,
       log_mode,
       database_role,
       switchover_status,
       TO_CHAR(current_scn) AS current_scn
FROM v$database;

-- 实例状态
SELECT instance_name,
       host_name,
       version,
       status,
       TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time,
       database_status
FROM v$instance;
```

### 2.2 备份目标路径磁盘空间（OS 命令）

```bash
# 检查备份目录磁盘空间
df -h <backup_path>
```

### 2.3 最近备份状态

```sql
-- 最近备份作业摘要
SELECT *
FROM (
    SELECT input_type,
           status,
           ROUND(input_bytes / 1024 / 1024 / 1024, 2) AS input_gb,
           ROUND(output_bytes / 1024 / 1024 / 1024, 2) AS output_gb,
           ROUND(elapsed_seconds / 60, 2) AS elapsed_min,
           TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI:SS') AS start_time,
           TO_CHAR(end_time, 'YYYY-MM-DD HH24:MI:SS') AS end_time
    FROM v$rman_backup_job_details
    ORDER BY start_time DESC
)
WHERE ROWNUM <= 10;

-- 最近备份集详情
SELECT bs_key,
       backup_type,
       incremental_level,
       status,
       compressed,
       ROUND(input_bytes / 1024 / 1024 / 1024, 2) AS input_gb,
       ROUND(output_bytes / 1024 / 1024 / 1024, 2) AS output_gb,
       TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI:SS') AS start_time,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI:SS') AS completion_time,
       elapsed_seconds
FROM v$backup_set
WHERE completion_time > SYSDATE - 7
ORDER BY completion_time DESC;
```

---

## 三、备份执行命令

### 3.1 全量备份（FULL）

```bash
# Oracle RMAN 全量备份（BACKUP DATABASE）
# 备份所有数据文件 + 控制文件 + SPFILE + 归档日志（可选）

rman target / <<EOF
CONFIGURE CONTROLFILE AUTOBACKUP ON;
CONFIGURE DEVICE TYPE DISK PARALLELISM ${PARALLELISM};

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/full/%d_FULL_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/full/%d_FULL_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/full/%d_FULL_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/full/%d_FULL_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG '${TAG}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

CROSSCHECK BACKUP;
EXIT;
EOF
```

### 3.2 增量 LEVEL 0 基准备份（INCREMENTAL LEVEL 0）

```bash
# Oracle RMAN 增量 LEVEL 0 基准备份
# 等同于全量备份，但标记为增量策略的基准，后续增量备份依赖此备份

rman target / <<EOF
CONFIGURE CONTROLFILE AUTOBACKUP ON;
CONFIGURE DEVICE TYPE DISK PARALLELISM ${PARALLELISM};

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr0/%d_INCR0_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr0/%d_INCR0_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr0/%d_INCR0_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr0/%d_INCR0_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET INCREMENTAL LEVEL 0 DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG '${TAG}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

CROSSCHECK BACKUP;
EXIT;
EOF
```

### 3.3 差异增量备份（LEVEL 1 DIFFERENTIAL）

```bash
# Oracle RMAN 差异增量备份（LEVEL 1 DIFFERENTIAL）
# 备份自上次 LEVEL 0 或 LEVEL 1 以来的所有变化数据块
# 恢复路径：LEVEL 0 + 最近一次 LEVEL 1 DIFFERENTIAL

rman target / <<EOF
CONFIGURE CONTROLFILE AUTOBACKUP ON;
CONFIGURE DEVICE TYPE DISK PARALLELISM ${PARALLELISM};

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr1/%d_INCR1_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr1/%d_INCR1_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr1/%d_INCR1_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/incr1/%d_INCR1_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET INCREMENTAL LEVEL 1 DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG '${TAG}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

CROSSCHECK BACKUP;
EXIT;
EOF
```

### 3.4 累积增量备份（LEVEL 1 CUMULATIVE）

```bash
# Oracle RMAN 累积增量备份（LEVEL 1 CUMULATIVE）
# 备份自上次 LEVEL 0 以来的所有变化数据块
# 恢复路径：LEVEL 0 + 最近一次 LEVEL 1 CUMULATIVE
# 优势：减少恢复步骤，但备份文件更大

rman target / <<EOF
CONFIGURE CONTROLFILE AUTOBACKUP ON;
CONFIGURE DEVICE TYPE DISK PARALLELISM ${PARALLELISM};

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/cuml/%d_CUML_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/cuml/%d_CUML_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/cuml/%d_CUML_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/cuml/%d_CUML_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET INCREMENTAL LEVEL 1 CUMULATIVE DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG '${TAG}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

CROSSCHECK BACKUP;
EXIT;
EOF
```

### 3.5 归档日志备份

```bash
# Oracle RMAN 归档日志备份
# 备份所有归档日志，删除已备份的归档日志文件释放空间

rman target / <<EOF
CONFIGURE CONTROLFILE AUTOBACKUP ON;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/arch/%d_ARCH_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '${BACKUP_PATH}/arch/%d_ARCH_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET ARCHIVELOG ALL
    DELETE INPUT
    TAG '${TAG}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
}

CROSSCHECK ARCHIVELOG ALL;
EXIT;
EOF
```

### 3.6 磁带备份（SBT_TAPE）

```bash
# Oracle RMAN 磁带备份
# 使用磁带介质，适用于长期归档与异地容灾

rman target / <<EOF
CONFIGURE DEFAULT DEVICE TYPE TO SBT_TAPE;
CONFIGURE DEVICE TYPE SBT_TAPE PARALLELISM ${PARALLELISM};
CONFIGURE CONTROLFILE AUTOBACKUP ON;

RUN {
  BACKUP AS COMPRESSED BACKUPSET DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG '${TAG}';
}

CROSSCHECK BACKUP;
EXIT;
EOF
```

---

## 四、备份校验与交叉检查

### 4.1 备份逻辑校验

```bash
# 验证备份集可恢复性（不实际恢复，仅校验）
rman target / <<EOF
RESTORE DATABASE VALIDATE;
EXIT;
EOF

# 验证特定备份集
# rman target /
# RMAN> VALIDATE BACKUPSET <bs_key>;

# 逻辑+物理完整校验
# rman target /
# RMAN> BACKUP VALIDATE CHECK LOGICAL DATABASE;
```

### 4.2 交叉检查

```bash
# 交叉检查备份物理文件是否存在
rman target / <<EOF
CROSSCHECK BACKUP;
CROSSCHECK ARCHIVELOG ALL;
CROSSCHECK BACKUP OF CONTROLFILE;
EXIT;
EOF
```

### 4.3 备份校验调度建议

| 校验类型 | 频率 | 命令 | 说明 |
|---------|------|------|------|
| `CROSSCHECK BACKUP` | 每天 | `RMAN> CROSSCHECK BACKUP;` | 快速检查物理文件是否存在 |
| `VALIDATE BACKUPSET` | 每天 | `RMAN> VALIDATE BACKUPSET <bs_key>;` | 验证最近备份集数据完整性 |
| `RESTORE DATABASE VALIDATE` | 每周 | `RMAN> RESTORE DATABASE VALIDATE;` | 验证完整恢复链（耗时较长） |
| `BACKUP VALIDATE CHECK LOGICAL` | 每月 | `RMAN> BACKUP VALIDATE CHECK LOGICAL DATABASE;` | 完整逻辑+物理校验 |

---

## 五、备份清理

### 5.1 过期备份清理（需确认）

```bash
# 根据保留策略删除过期备份
rman target / <<EOF
DELETE NOPROMPT OBSOLETE;
DELETE NOPROMPT EXPIRED BACKUP;
EXIT;
EOF
```

### 5.2 按时间删除归档日志

```bash
# 删除指定天数前的归档日志（需确保全量备份已覆盖此时间窗口）
rman target / <<EOF
DELETE NOPROMPT ARCHIVELOG ALL COMPLETED BEFORE 'SYSDATE-<days>';
EXIT;
EOF
```

### 5.3 删除特定备份集

```bash
# 删除指定备份集（需确认备份集号）
rman target /
RMAN> DELETE BACKUPSET <bs_key>;
RMAN> EXIT;
```

---

## 六、备份状态查询

### 6.1 备份摘要查询

```sql
-- 按备份类型汇总最近 30 天备份
SELECT input_type,
       COUNT(*) AS backup_count,
       ROUND(SUM(input_bytes) / 1024 / 1024 / 1024, 2) AS total_input_gb,
       ROUND(SUM(output_bytes) / 1024 / 1024 / 1024, 2) AS total_output_gb,
       ROUND((1 - SUM(output_bytes) / SUM(input_bytes)) * 100, 2) AS compression_pct,
       ROUND(AVG(elapsed_seconds) / 60, 2) AS avg_elapsed_min,
       MIN(start_time) AS first_backup,
       MAX(start_time) AS last_backup
FROM v$rman_backup_job_details
WHERE start_time > SYSDATE - 30
GROUP BY input_type
ORDER BY last_backup DESC;
```

### 6.2 备份集清单

```sql
-- 最近备份集详情
SELECT bs_key,
       backup_type,
       incremental_level,
       status,
       ROUND(input_bytes / 1024 / 1024 / 1024, 2) AS input_gb,
       ROUND(output_bytes / 1024 / 1024 / 1024, 2) AS output_gb,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI:SS') AS completion_time,
       elapsed_seconds,
       tag
FROM v$backup_set
WHERE completion_time > SYSDATE - 7
ORDER BY completion_time DESC;
```

### 6.3 数据文件备份状态

```sql
-- 各数据文件最近备份时间
SELECT file#,
       status,
       TO_CHAR(checkpoint_time, 'YYYY-MM-DD HH24:MI:SS') AS checkpoint_time,
       incremental_level,
       ROUND(SYSDATE - checkpoint_time, 2) AS days_since_backup
FROM v$backup_datafile
WHERE completion_time > SYSDATE - 30
ORDER BY file#;
```

### 6.4 归档日志备份状态

```sql
-- 未备份的归档日志数量
SELECT thread#,
       COUNT(*) AS unbacked_count,
       ROUND(SUM(blocks * block_size) / 1024 / 1024, 2) AS unbacked_mb
FROM v$archived_log
WHERE backed_up = 'NO'
  AND deleted = 'NO'
GROUP BY thread#;
```

---

## 七、备份执行最佳实践

### 7.1 备份前检查清单

1. 数据库处于 ARCHIVELOG 模式（`SELECT log_mode FROM v$database;`）
2. 备份目标路径有足够磁盘空间（至少 1.5 倍数据库大小）
3. 控制文件自动备份已开启（`CONFIGURE CONTROLFILE AUTOBACKUP ON;`）
4. 备份窗口评估（检查当前是否有业务高峰期）
5. 确认备份类型与策略（全量/增量/归档日志）

### 7.2 备份策略建议

| 场景 | 备份类型 | 频率 | 说明 |
|------|---------|------|------|
| 小库（< 100GB） | 全量备份 | 每天 | 直接全量备份，恢复最快 |
| 中库（100GB ~ 1TB） | LEVEL 0 + 差异增量 | 周 LEVEL 0 + 日 LEVEL 1 | 平衡备份时间与恢复时间 |
| 大库（> 1TB） | LEVEL 0 + 累积增量 | 月 LEVEL 0 + 周 LEVEL 1 CUMULATIVE | 减少恢复步骤 |
| 变更前备份 | 全量备份 | 按需 | 数据库升级/迁移前的安全保障 |
| 归档日志 | 归档日志备份 | 每 30min ~ 4h | 满足 RPO 要求 |

### 7.3 通道数建议

| 场景 | 建议 parallelism | 说明 |
|------|-----------------|------|
| 小库 / 低负载 | 2 | 减少 IO 影响 |
| 中库 / 正常负载 | 4 | 默认推荐值 |
| 大库 / 高 IO 能力 | 8 | 需存储支持高并发 IO |
| 磁带备份 | 磁带驱动器数 | 匹配物理磁带驱动器数量 |

---

## 八、异常处理
- 数据库未处于 ARCHIVELOG 模式时，提示无法执行在线备份，需先开启归档模式。
- 数据库处于 NOMOUNT/MOUNT 状态时，只有部分备份类型可执行，提示当前状态限制。
- 备份目标路径空间不足时，提示清理空间或更换目标路径，不强制执行。
- 备份过程中出现 ORA- 错误时，记录错误码与信息，输出失败原因与建议。
- RMAN 通道分配失败时，检查 parallelism 参数是否超过系统限制。
- 备份窗口超时（duration_minutes 限制），提示部分备份未完成，下次可继续。
- 本技能执行实际 RMAN 操作，单次执行耗时取决于备份数据量，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. **前置检查结果**：数据库状态、归档模式、备份路径空间
  2. **备份执行摘要**：备份类型、开始时间、结束时间、耗时、状态
  3. **备份集详情**：备份集号、备份片路径、大小、压缩比、TAG
  4. **后处理结果**：交叉检查结果、过期备份清理结果（如启用）
  5. **备份状态汇总**：最近备份时间、未备份归档日志数量、备份成功率