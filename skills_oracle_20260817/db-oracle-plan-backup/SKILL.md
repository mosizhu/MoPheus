---
name: "db-oracle-plan-backup"
description: "Oracle RMAN 备份策略设计技能（只读方案）。核心能力：根据数据库规模与 RPO/RTO 需求，生成完整的 RMAN 备份策略方案——备份类型选型（全量/增量/归档日志）、备份频率与保留策略、备份目标配置（磁盘/FRA/磁带）、备份性能优化（并行度/压缩/加密/多路复用）、备份校验与完整性检查、恢复策略与演练方案、异地容灾与备份归档。适用场景：新建 Oracle 数据库备份策略设计、现有备份策略评估与优化、RPO/RTO 达标的备份体系设计、备份窗口与性能权衡分析、备份存储规划、灾备体系中的备份策略制定。功能限制：仅输出方案与建议，不实际执行 RMAN 备份（不执行 BACKUP DATABASE/BACKUP ARCHIVELOG）、不修改 RMAN 配置（不执行 CONFIGURE）、不恢复数据库（不执行 RESTORE/RECOVER）；备份执行由 DBA 按计划实施。"
version: "v1.0.0"
tags: db-ops
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "backup_scope"
    type: "string"
    required: false
    default: "full"
    desc: "备份策略范围：full（全量+归档）/ full_incr（全量+增量+归档）/ archivelog_only（仅归档日志）/ custom（自定义）"
  - name: "rpo_hours"
    type: "integer"
    required: false
    default: 1
    desc: "恢复点目标（小时），即最大可容忍数据丢失时间，默认 1"
  - name: "rto_hours"
    type: "integer"
    required: false
    default: 4
    desc: "恢复时间目标（小时），即最大可容忍恢复耗时，默认 4"
  - name: "data_size_gb"
    type: "integer"
    required: false
    default: 0
    desc: "数据库近似大小（GB），为空则自动探测"
  - name: "backup_dest"
    type: "string"
    required: false
    default: "disk"
    desc: "备份目标介质：disk（磁盘本地/FRA）/ tape（磁带库）/ disk_tape（磁盘+磁带两级）/ cloud（云存储）"
  - name: "retention_days"
    type: "integer"
    required: false
    default: 7
    desc: "备份保留天数（REDUNDANCY 或 RECOVERY WINDOW 策略），默认 7"
  - name: "include_offsite"
    type: "boolean"
    required: false
    default: false
    desc: "是否包含异地容灾备份策略（默认 false）"
  - name: "include_encryption"
    type: "boolean"
    required: false
    default: false
    desc: "是否包含备份加密策略（默认 false）"
  - name: "daily_change_pct"
    type: "integer"
    required: false
    default: 5
    desc: "日均数据变更比例（%），用于评估增量备份大小，默认 5"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle RMAN 备份策略设计

> 根据数据库规模、RPO/RTO 需求与业务特征，生成完整 RMAN 备份策略方案：备份类型选型、频率与保留策略、目标介质配置、性能优化、校验与完整性检查、恢复演练方案、异地容灾。本技能为 query 级方案，仅输出策略不执行备份。自包含。

## 核心能力
- 单一职责：Oracle RMAN 备份策略方案设计（需求分析 → 策略选型 → 配置方案 → 校验方案 → 恢复演练方案）。
- 覆盖全量备份、增量备份（差异增量/累积增量）、归档日志备份、控制文件/SPFILE 自动备份。
- 支持磁盘（FRA）、磁带、云存储、多级介质组合策略。

## 适用场景
- 新建 Oracle 数据库时需要制定备份策略
- 现有备份策略评估与优化（RPO/RTO 不达标）
- 备份窗口与性能权衡分析（备份对业务影响评估）
- 备份存储容量规划与成本估算
- 灾备体系中的备份策略制定（本地 + 异地）
- 合规审计要求的备份策略设计（如金融行业日志保留 6 个月）
- 数据库迁移/升级前的备份加固方案
- 备份加密与数据安全策略设计

## 功能限制 / 安全边界
- 不实际执行 RMAN 备份（不执行 BACKUP DATABASE / BACKUP ARCHIVELOG / BACKUP INCREMENTAL）
- 不修改 RMAN 配置（不执行 CONFIGURE ...、不执行 ALTER SYSTEM SET db_recovery_file_dest）
- 不恢复数据库（不执行 RESTORE DATABASE / RECOVER DATABASE / DUPLICATE）
- 不删除备份片（不执行 DELETE OBSOLETE / DELETE EXPIRED BACKUP）
- 不执行备份校验（不执行 RESTORE VALIDATE / BACKUP VALIDATE）
- 仅输出方案与建议，由 DBA 审查后实施；单次生成耗时 ≤5s

---

## 一、推理框架：RMAN 备份策略设计链

```
用户提出备份策略需求（RPO/RTO/数据规模/备份介质）
    |
    v
[1] 环境信息采集（前置分析）
    | 数据库版本、大小、归档模式、字符集
    | 当前 RMAN 配置（SHOW ALL）
    | 当前备份状态（LIST BACKUP SUMMARY）
    | 归档日志生成速率
    | 现有备份策略与保留策略
    v
[2] 需求分析
    | RPO 解析 → 确定备份频率（全量/增量/归档间隔）
    | RTO 解析 → 确定恢复方案（全量恢复时间 / 增量恢复时间）
    | 备份窗口分析 → 确定备份并行度与压缩策略
    | 存储容量估算 → 保留策略与存储规划
    v
[3] 备份类型选型
    | 全量备份（FULL）：频率/窗口/并行度
    | 增量备份（INCREMENTAL LEVEL 0/1）：差异增量 vs 累积增量
    | 归档日志备份：频率（与 RPO 匹配）
    | 控制文件/SPFILE 自动备份配置
    v
[4] 备份保留策略
    | REDUNDANCY（按副本数） vs RECOVERY WINDOW（按天数）
    | 归档日志保留策略（与全量备份的依赖关系）
    | 异地备份保留策略（独立于本地策略）
    v
[5] 备份性能优化
    | 并行通道配置（磁盘/磁带）
    | 压缩算法选择（BASIC/LOW/MEDIUM/HIGH）
    | 多路复用（磁带场景）
    | 备份片大小与 MAXSETSIZE
    | 备份限速（DURATION / RATE）
    v
[6] 备份校验与完整性
    | 备份逻辑校验（RESTORE VALIDATE / VALIDATE DATAFILE）
    | 备份物理校验（交叉检查 CROSSCHECK）
    | 归档日志连续性校验
    | 定期恢复演练建议
    v
[7] 异地容灾与安全
    | 备份加密（透明加密 / 密码加密 / 钱包加密）
    | 异地备份传输方案（rsync / Data Guard / 磁带出库）
    | 备份集防篡改建议
    v
[8] 输出备份策略方案
    | 策略总览（备份类型/频率/保留/目标）
    | RMAN 配置命令（仅输出，不执行）
    | 备份脚本模板（每日/每周/每月）
    | 存储容量估算表
    | 恢复演练方案
    | 监控与告警建议
```

---

## 二、环境信息采集（前置分析，只读 SQL）

### 2.1 数据库基础信息

```sql
-- 数据库版本与平台
SELECT banner_full AS full_version FROM v$version;

-- 数据库名称、归档模式、闪回状态
SELECT name AS db_name,
       created,
       log_mode,
       flashback_on,
       open_mode,
       platform_name
FROM v$database;

-- 数据库大小（GB）
SELECT ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) AS total_gb
FROM v$datafile
UNION ALL
SELECT ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) AS total_gb
FROM v$tempfile;

-- 数据文件清单
SELECT file#, name, ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb
FROM v$datafile
ORDER BY file#;

-- 控制文件清单
SELECT name, ROUND(block_size * file_size_blks / 1024 / 1024, 2) AS size_mb
FROM v$controlfile;
```

### 2.2 归档日志生成速率（用于确定增量备份大小与存储容量）

```sql
-- 按小时统计归档日志生成量（最近 7 天）
SELECT TO_CHAR(TRUNC(completion_time, 'HH'), 'YYYY-MM-DD HH24') AS hour,
       COUNT(*) AS archive_count,
       ROUND(SUM(blocks * block_size) / 1024 / 1024, 2) AS total_mb
FROM v$archived_log
WHERE completion_time > SYSDATE - 7
  AND dest_id = 1
GROUP BY TRUNC(completion_time, 'HH')
ORDER BY hour DESC;

-- 日均归档日志生成量（GB）
SELECT ROUND(AVG(daily_size) / 1024, 2) AS avg_daily_archivelog_gb,
       ROUND(MAX(daily_size) / 1024, 2) AS peak_daily_archivelog_gb
FROM (
    SELECT TRUNC(completion_time) AS day,
           SUM(blocks * block_size) / 1024 / 1024 AS daily_size
    FROM v$archived_log
    WHERE completion_time > SYSDATE - 30
      AND dest_id = 1
    GROUP BY TRUNC(completion_time)
);

-- 当前 REDO 日志大小与切换频率
SELECT group#,
       thread#,
       sequence#,
       bytes / 1024 / 1024 AS size_mb,
       members,
       status
FROM v$log
ORDER BY group#;

-- 最近 24 小时日志切换频率
SELECT TO_CHAR(first_time, 'YYYY-MM-DD HH24') AS hour,
       COUNT(*) AS switches_per_hour,
       ROUND(COUNT(*) * (SELECT bytes / 1024 / 1024 / 1024 FROM v$log WHERE ROWNUM = 1), 2) AS redo_gb_per_hour
FROM v$log_history
WHERE first_time > SYSDATE - 1
GROUP BY TO_CHAR(first_time, 'YYYY-MM-DD HH24')
ORDER BY hour DESC;
```

### 2.3 当前 RMAN 配置（只读）

```sql
-- RMAN 持久化配置（通过 SQL 查询）
-- 注：RMAN 配置信息存储在控制文件中，完整信息需通过 RMAN SHOW ALL 获取
-- 以下为部分可查询的配置信息

-- 归档日志目标
SELECT dest_name,
       destination,
       status,
       type,
       target
FROM v$archive_dest
WHERE status = 'VALID';

-- 快速恢复区（FRA）使用情况
SELECT name,
       ROUND(space_limit / 1024 / 1024 / 1024, 2) AS space_limit_gb,
       ROUND(space_used / 1024 / 1024 / 1024, 2) AS space_used_gb,
       ROUND(space_reclaimable / 1024 / 1024 / 1024, 2) AS reclaimable_gb,
       ROUND((space_used - space_reclaimable) / space_limit * 100, 2) AS pct_used,
       number_of_files
FROM v$recovery_file_dest;

-- 备份集历史摘要
SELECT *
FROM (
    SELECT db_name,
           input_type,
           status,
           ROUND(SUM(input_bytes) / 1024 / 1024 / 1024, 2) AS total_gb,
           ROUND(SUM(output_bytes) / 1024 / 1024 / 1024, 2) AS compressed_gb,
           ROUND((1 - SUM(output_bytes) / SUM(input_bytes)) * 100, 2) AS compression_pct,
           MIN(start_time) AS first_backup,
           MAX(end_time) AS last_backup,
           COUNT(*) AS backup_count
    FROM v$rman_backup_job_details
    WHERE start_time > SYSDATE - 30
    GROUP BY db_name, input_type, status
    ORDER BY last_backup DESC
)
WHERE ROWNUM <= 20;
```

---

## 三、RMAN 备份类型选型

### 3.1 备份类型说明

| 备份类型 | 说明 | 备份内容 | 恢复步骤 | 适用场景 |
|---------|------|---------|---------|---------|
| **FULL（全量备份）** | 备份所有数据文件 + 控制文件 + SPFILE | 全部数据块 | 直接恢复（最快） | 基准备份、小库（< 100GB） |
| **INCREMENTAL LEVEL 0** | 增量基准备份（等同于 FULL） | 全部数据块（标记为增量基准） | 先恢复 LEVEL 0，再应用增量 | 增量策略的基准 |
| **INCREMENTAL LEVEL 1 DIFFERENTIAL** | 差异增量备份（自上次 LEVEL 0 或 LEVEL 1 以来的变化） | 变化的数据块 | LEVEL 0 + 最近一次 LEVEL 1 | 每日增量备份，恢复快 |
| **INCREMENTAL LEVEL 1 CUMULATIVE** | 累积增量备份（自上次 LEVEL 0 以来的所有变化） | 自 LEVEL 0 以来的所有变化块 | LEVEL 0 + 最近一次 LEVEL 1 CUMULATIVE | 减少恢复步骤，但备份更大 |
| **ARCHIVELOG BACKUP** | 归档日志备份 | 归档日志文件 | 用于不完全恢复 / PITR | 满足 RPO 要求，支持时间点恢复 |
| **CONTROLFILE AUTOBACKUP** | 控制文件 + SPFILE 自动备份 | 控制文件 + SPFILE | 恢复控制文件 | 必须开启，每次备份后自动执行 |

### 3.2 备份策略选型决策树

```
                              ┌── 数据量 < 100GB? ──┐
                              │ 是                   │ 否
                              v                      v
                        每日全量备份              ┌── RPO ≤ 1h? ──┐
                        (FULL)                   │ 是              │ 否
                                                 v                 v
                                          增量备份策略         全量 + 归档
                                          (LEVEL 0/1)         (FULL + ARCH)
                                                 │
                                    ┌────────────┼────────────┐
                                    v            v            v
                              ┌── RTO ≤ 2h? ──┐           ┌── 磁带? ──┐
                              │ 是             │ 否         │ 是         │ 否
                              v                v            v            v
                          累积增量        差异增量      多路复用      正常并行
                          (CUMULATIVE)  (DIFFERENTIAL)  (DUPLEX)
```

### 3.3 策略推荐矩阵

| 条件 | 推荐策略 | 全量频率 | 增量频率 | 归档频率 | 保留策略 |
|------|---------|---------|---------|---------|---------|
| 小库（< 100GB），RPO=24h | 每日全量 + 归档 | 每天 | — | 每 4h | 7 天 |
| 中库（100GB~1TB），RPO=1h | 周全量 + 日差异增量 + 归档 | 每周 | 每天 | 每 30min | 14 天 |
| 中库（100GB~1TB），RPO=4h | 周全量 + 日累积增量 + 归档 | 每周 | 每天 | 每 2h | 14 天 |
| 大库（> 1TB），RPO=1h | 月全量 + 周 LEVEL 0 + 日差异增量 + 归档 | 每月 | 每天 | 每 30min | 30 天 |
| 大库（> 1TB），RPO=4h | 月全量 + 周累积增量 + 归档 | 每月 | 每周 | 每 2h | 30 天 |
| 极严 RPO（< 30min） | 日全量 + 归档日志实时传输 | 每天 | — | 持续 | 7 天 |
| 合规归档（金融/审计） | 全量+增量+归档 + 异地 | 每周 | 每天 | 每 30min | 本地 14 天 + 异地 6 月 |

---

## 四、备份保留策略

### 4.1 REDUNDANCY vs RECOVERY WINDOW

| 策略 | 含义 | 示例 | 适用场景 |
|------|------|------|---------|
| `REDUNDANCY n` | 保留最近 n 个全量备份及对应的增量/归档 | `REDUNDANCY 2`：保留最近 2 个全量周期 | 备份存储空间有限，关注副本数量 |
| `RECOVERY WINDOW OF n DAYS` | 保留最近 n 天内任意时间点恢复所需的所有备份 | `RECOVERY WINDOW OF 7 DAYS`：保留 7 天内 PITR 所需 | 合规要求，关注可恢复时间范围 |

### 4.2 归档日志保留策略

```sql
-- 归档日志删除策略（仅输出，不执行）
-- 原则：归档日志必须在与其关联的全量备份过期之后才能删除
-- 即：归档日志保留时间 ≥ 全量备份保留时间

-- 策略 A：RMAN 自动管理（推荐）
-- CONFIGURE ARCHIVELOG DELETION POLICY TO BACKED UP 1 TIMES TO DISK;
-- 含义：归档日志在备份到磁盘 1 次后可以删除

-- 策略 B：基于应用窗口
-- CONFIGURE ARCHIVELOG DELETION POLICY TO APPLIED ON ALL STANDBY BACKED UP 1 TIMES TO DISK;
-- 含义：归档日志在所有备库应用完成且备份 1 次后可删除

-- 策略 C：时间窗口
-- DELETE ARCHIVELOG ALL COMPLETED BEFORE 'SYSDATE-7';
-- 含义：删除 7 天前的归档日志（需确保全量备份覆盖此时间窗口）
```

### 4.3 备份保留清理策略

```bash
# 自动清理过期备份（建议在备份脚本末尾执行）
# DELETE OBSOLETE;  -- 根据保留策略删除过期备份
# DELETE EXPIRED BACKUP;  -- 删除标记为 EXPIRED 的备份记录
# CROSSCHECK BACKUP;  -- 交叉检查备份物理文件是否存在
```

---

## 五、RMAN 配置与优化

### 5.1 基础配置（仅输出，不执行）

```bash
# === RMAN 持久化配置建议 ===
# 注意：以下命令仅作方案输出，不实际执行

# 1. 备份目标设备
# CONFIGURE DEFAULT DEVICE TYPE TO DISK;  -- 默认磁盘
# CONFIGURE DEFAULT DEVICE TYPE TO SBT_TAPE;  -- 默认磁带

# 2. 备份并行度
# CONFIGURE DEVICE TYPE DISK PARALLELISM 4;  -- 磁盘并行通道数
# CONFIGURE DEVICE TYPE SBT_TAPE PARALLELISM 2;  -- 磁带并行通道数

# 3. 压缩策略
# CONFIGURE COMPRESSION ALGORITHM 'MEDIUM';  -- 压缩级别：BASIC/LOW/MEDIUM/HIGH
# 压缩级别对比：
#   BASIC:  压缩比约 2-3x，CPU 开销低
#   LOW:    压缩比约 3-4x，CPU 开销中低（推荐 OLTP）
#   MEDIUM: 压缩比约 4-5x，CPU 开销中（推荐混合负载）
#   HIGH:   压缩比约 5-7x，CPU 开销高（仅在备份窗口充裕时使用）

# 4. 加密策略
# CONFIGURE ENCRYPTION FOR DATABASE ON;  -- 开启透明加密
# CONFIGURE ENCRYPTION ALGORITHM 'AES256';  -- 加密算法

# 5. 控制文件自动备份
# CONFIGURE CONTROLFILE AUTOBACKUP ON;  -- 必须开启
# CONFIGURE CONTROLFILE AUTOBACKUP FORMAT FOR DEVICE TYPE DISK TO '/backup/%F.ctl';

# 6. 备份片格式
# CONFIGURE CHANNEL DEVICE TYPE DISK FORMAT '/backup/%d_%T_%s_%p.bak';

# 7. 备份优化
# CONFIGURE BACKUP OPTIMIZATION ON;  -- 跳过未变化的文件（减少备份量）

# 8. 备份冗余策略
# CONFIGURE RETENTION POLICY TO RECOVERY WINDOW OF 7 DAYS;  -- 恢复窗口
# 或
# CONFIGURE RETENTION POLICY TO REDUNDANCY 2;  -- 副本数

# 9. 归档日志删除策略
# CONFIGURE ARCHIVELOG DELETION POLICY TO BACKED UP 1 TIMES TO DISK;
```

### 5.2 备份性能优化参数

| 参数 | 建议值 | 说明 |
|------|--------|------|
| `PARALLELISM` | 磁盘：CPU 核数 × 0.5；磁带：磁带驱动器数 | 根据 IO 能力调整，避免 I/O 瓶颈 |
| `COMPRESSION ALGORITHM` | OLTP: LOW；混合: MEDIUM；DW: HIGH | 压缩比与 CPU 开销权衡 |
| `MAXSETSIZE` | 磁盘：不限制；磁带：磁带容量 | 控制单个备份片大小 |
| `SECTION SIZE` | 大文件（> 100GB）建议 16GB-32GB | 大文件分段并行备份 |
| `FILESPERSET` | 磁盘：不限制；磁带：≤ 64 | 磁带场景控制每集合文件数 |
| `MAXOPENFILES` | 磁盘：16-32；磁带：8-16 | 同时打开文件数 |
| `DURATION` | 限制备份窗口，如 `DURATION 4:00` | 4 小时内完成，超时自动中断 |
| `RATE` | 限制备份速率，如 `RATE 200M` | 避免备份占用过多 IO 带宽 |

### 5.3 大文件分段备份（Section Backup）

```bash
# 大文件（> 100GB）使用分段备份，并行处理
# SECTION SIZE 建议：使每个数据文件至少分成 4 个段
# 示例：256GB 数据文件，SECTION SIZE 32GB → 8 个并行段
BACKUP SECTION SIZE 32G DATAFILE '/data/orcl/bigfile01.dbf';
```

### 5.4 通道限速配置

```bash
# 限制备份 IO 带宽，避免影响业务（OLTP 高峰期）
# BACKUP DURATION 4:00 PARTIAL MINIMIZE LOAD DATABASE;
# 含义：4 小时内完成，超时部分可下次继续，最小化对数据库负载

# 限制速率
# BACKUP AS COMPRESSED BACKUPSET DATABASE
#   SECTION SIZE 16G
#   RATE 200M;  -- 限制 200MB/s
```

---

## 六、备份脚本模板（仅输出，不执行）

### 6.1 全量备份脚本（Level 0）

```bash
#!/bin/bash
# Oracle RMAN 全量备份脚本（Level 0）
# 频率：每周日 02:00
# 保留：RECOVERY WINDOW OF 14 DAYS

export ORACLE_SID=<db_name>
export ORACLE_HOME=<oracle_home>
BACKUP_DATE=$(date +%Y%m%d_%H%M)
LOG_FILE=/backup/logs/full_backup_${BACKUP_DATE}.log

rman target / log=${LOG_FILE} <<EOF
CONFIGURE RETENTION POLICY TO RECOVERY WINDOW OF 14 DAYS;
CONFIGURE CONTROLFILE AUTOBACKUP ON;
CONFIGURE BACKUP OPTIMIZATION ON;
CONFIGURE COMPRESSION ALGORITHM 'MEDIUM';
CONFIGURE DEVICE TYPE DISK PARALLELISM 4;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '/backup/full/%d_FULL_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '/backup/full/%d_FULL_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK FORMAT '/backup/full/%d_FULL_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK FORMAT '/backup/full/%d_FULL_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET INCREMENTAL LEVEL 0 DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG 'FULL_BACKUP_${BACKUP_DATE}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

# 清理过期备份
DELETE NOPROMPT OBSOLETE;
DELETE NOPROMPT EXPIRED BACKUP;

# 交叉检查
CROSSCHECK BACKUP;
CROSSCHECK ARCHIVELOG ALL;

EXIT;
EOF

# 检查备份结果
if grep -q "ERROR" ${LOG_FILE}; then
    echo "Backup FAILED: $(date)" >> /backup/logs/backup_alert.log
    # 发送告警
else
    echo "Backup SUCCESS: $(date)" >> /backup/logs/backup_alert.log
fi
```

### 6.2 差异增量备份脚本（Level 1 DIFFERENTIAL）

```bash
#!/bin/bash
# Oracle RMAN 差异增量备份脚本（Level 1 DIFFERENTIAL）
# 频率：周一至周六 02:00
# 依赖：需有 Level 0 备份基准

export ORACLE_SID=<db_name>
export ORACLE_HOME=<oracle_home>
BACKUP_DATE=$(date +%Y%m%d_%H%M)
LOG_FILE=/backup/logs/incr_backup_${BACKUP_DATE}.log

rman target / log=${LOG_FILE} <<EOF
CONFIGURE DEVICE TYPE DISK PARALLELISM 4;
CONFIGURE BACKUP OPTIMIZATION ON;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '/backup/incr/%d_INCR_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '/backup/incr/%d_INCR_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK FORMAT '/backup/incr/%d_INCR_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK FORMAT '/backup/incr/%d_INCR_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET INCREMENTAL LEVEL 1 DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG 'INCR_BACKUP_${BACKUP_DATE}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

CROSSCHECK BACKUP;
DELETE NOPROMPT OBSOLETE;
EXIT;
EOF
```

### 6.3 归档日志备份脚本（满足 RPO ≤ 30min）

```bash
#!/bin/bash
# Oracle RMAN 归档日志备份脚本
# 频率：每 30 分钟
# 目的：满足 RPO ≤ 30min

export ORACLE_SID=<db_name>
export ORACLE_HOME=<oracle_home>
LOG_FILE=/backup/logs/arch_backup_$(date +%Y%m%d_%H%M).log

rman target / log=${LOG_FILE} <<EOF
BACKUP AS COMPRESSED BACKUPSET ARCHIVELOG ALL
  DELETE INPUT
  FORMAT '/backup/arch/%d_ARCH_%T_%s_%p.bak'
  TAG 'ARCH_BACKUP';
EXIT;
EOF
```

### 6.4 累积增量备份脚本（Level 1 CUMULATIVE）

```bash
#!/bin/bash
# Oracle RMAN 累积增量备份脚本（Level 1 CUMULATIVE）
# 频率：每周（周三/周六），替代差异增量
# 优势：恢复时只需 Level 0 + 最近一次累积增量，减少恢复步骤

export ORACLE_SID=<db_name>
export ORACLE_HOME=<oracle_home>
BACKUP_DATE=$(date +%Y%m%d_%H%M)
LOG_FILE=/backup/logs/cuml_backup_${BACKUP_DATE}.log

rman target / log=${LOG_FILE} <<EOF
CONFIGURE DEVICE TYPE DISK PARALLELISM 4;

RUN {
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK FORMAT '/backup/incr/%d_CUML_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch2 DEVICE TYPE DISK FORMAT '/backup/incr/%d_CUML_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch3 DEVICE TYPE DISK FORMAT '/backup/incr/%d_CUML_%T_%s_%p.bak';
  ALLOCATE CHANNEL ch4 DEVICE TYPE DISK FORMAT '/backup/incr/%d_CUML_%T_%s_%p.bak';

  BACKUP AS COMPRESSED BACKUPSET INCREMENTAL LEVEL 1 CUMULATIVE DATABASE
    PLUS ARCHIVELOG DELETE INPUT
    TAG 'CUMULATIVE_BACKUP_${BACKUP_DATE}';

  RELEASE CHANNEL ch1;
  RELEASE CHANNEL ch2;
  RELEASE CHANNEL ch3;
  RELEASE CHANNEL ch4;
}

CROSSCHECK BACKUP;
DELETE NOPROMPT OBSOLETE;
EXIT;
EOF
```

---

## 七、备份校验与完整性检查

### 7.1 备份校验 SQL（只读）

```sql
-- 备份集完整性检查（最近 7 天）
SELECT bs_key,
       backup_type,
       status,
       compressed,
       TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI') AS start_time,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI') AS end_time,
       ROUND(input_bytes / 1024 / 1024 / 1024, 2) AS input_gb,
       ROUND(output_bytes / 1024 / 1024 / 1024, 2) AS output_gb,
       ROUND((1 - output_bytes / input_bytes) * 100, 2) AS compression_pct,
       elapsed_seconds
FROM v$backup_set
WHERE completion_time > SYSDATE - 7
ORDER BY completion_time DESC;

-- 数据文件备份状态
SELECT file#,
       status,
       TO_CHAR(checkpoint_change#, '9999999999999999') AS ckp_scn,
       TO_CHAR(checkpoint_time, 'YYYY-MM-DD HH24:MI:SS') AS checkpoint_time,
       incremental_level
FROM v$backup_datafile
WHERE completion_time > SYSDATE - 7
ORDER BY file#, completion_time DESC;

-- 归档日志备份状态
SELECT sequence#,
       thread#,
       TO_CHAR(first_time, 'YYYY-MM-DD HH24:MI') AS first_time,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI') AS completion_time,
       status,
       deleted
FROM v$archived_log
WHERE completion_time > SYSDATE - 7
ORDER BY completion_time DESC;

-- 备份作业执行详情
SELECT input_type,
       status,
       ROUND(input_bytes / 1024 / 1024 / 1024, 2) AS input_gb,
       ROUND(output_bytes / 1024 / 1024 / 1024, 2) AS output_gb,
       ROUND(elapsed_seconds / 60, 2) AS elapsed_min,
       TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI') AS start_time,
       TO_CHAR(end_time, 'YYYY-MM-DD HH24:MI') AS end_time,
       input_type
FROM v$rman_backup_job_details
WHERE start_time > SYSDATE - 7
ORDER BY start_time DESC;
```

### 7.2 备份校验命令（仅输出，不执行）

```bash
# === 备份逻辑校验（推荐每周执行一次） ===
# 验证备份集可恢复性（不实际恢复）
rman target /
RMAN> RESTORE DATABASE VALIDATE;
RMAN> RESTORE ARCHIVELOG ALL VALIDATE;

# 验证特定备份集
# RMAN> VALIDATE BACKUPSET <bs_key>;
# RMAN> VALIDATE DATAFILE 1,2,3;

# 验证备份完整性（检查物理损坏）
# RMAN> BACKUP VALIDATE CHECK LOGICAL DATABASE;

# 交叉检查（物理文件是否存在）
# RMAN> CROSSCHECK BACKUP;
# RMAN> CROSSCHECK ARCHIVELOG ALL;
# RMAN> CROSSCHECK BACKUP OF CONTROLFILE;

# 验证归档日志连续性
# RMAN> RESTORE ARCHIVELOG FROM SEQUENCE <seq_start> UNTIL SEQUENCE <seq_end> VALIDATE HEADER;
```

### 7.3 备份校验调度建议

| 校验类型 | 频率 | 说明 |
|---------|------|------|
| `CROSSCHECK BACKUP` | 每天 | 快速检查物理文件是否存在 |
| `VALIDATE BACKUPSET` | 每天（最近的备份） | 验证备份集数据完整性 |
| `RESTORE DATABASE VALIDATE` | 每周 | 验证完整恢复链（耗时较长） |
| `RESTORE VALIDATE + CHECK LOGICAL` | 每月 | 完整的逻辑+物理校验（最耗时） |
| 异机恢复演练 | 每季度 | 在生产环境之外验证备份可恢复性 |

---

## 八、加密与异地容灾

### 8.1 备份加密策略

```bash
# === 备份加密配置（仅输出方案，不执行） ===

# 方式一：密码加密（跨平台兼容性最好）
# SET ENCRYPTION ON IDENTIFIED BY '<password>' ONLY;
# BACKUP AS COMPRESSED BACKUPSET DATABASE;

# 方式二：Oracle Wallet 透明加密（推荐生产环境）
# 1. 创建 Wallet
# ADMINISTER KEY MANAGEMENT CREATE KEYSTORE '/wallet/path' IDENTIFIED BY "<wallet_pwd>";
# ADMINISTER KEY MANAGEMENT SET KEYSTORE OPEN IDENTIFIED BY "<wallet_pwd>";
# ADMINISTER KEY MANAGEMENT SET KEY IDENTIFIED BY "<wallet_pwd>" WITH BACKUP;
# 2. RMAN 配置
# CONFIGURE ENCRYPTION FOR DATABASE ON;
# CONFIGURE ENCRYPTION ALGORITHM 'AES256';

# 加密算法对比
# | 算法    | 强度 | 性能影响 | 适用场景 |
# | AES128  | 中   | 低       | 一般安全需求 |
# | AES192  | 高   | 中       | 较高安全需求 |
# | AES256  | 最高 | 高       | 金融/合规要求 |
```

### 8.2 异地容灾备份策略

```bash
# === 异地备份传输方案 ===

# 方案 A：rsync 同步到异地（适用于磁盘备份）
# 在备份脚本末尾添加：
rsync -avz --progress /backup/full/ oracle@<offsite_host>:/offsite_backup/full/
rsync -avz --progress /backup/incr/ oracle@<offsite_host>:/offsite_backup/incr/
rsync -avz --progress /backup/arch/ oracle@<offsite_host>:/offsite_backup/arch/

# 方案 B：RMAN 双写（DISK + TAPE）
# CONFIGURE CHANNEL DEVICE TYPE DISK FORMAT '/backup/%U', '/nfs_offsite/%U';
# 或使用 BACKUP COPIES
# BACKUP AS COMPRESSED BACKUPSET COPIES 2 DATABASE;

# 方案 C：磁带副本出库
# 备份到磁带后，通过磁带管理系统出库异地存放

# 异地保留策略（独立于本地）
# 本地：7-14 天（快速恢复）
# 异地：30 天-6 个月（合规归档 / 灾难恢复）
```

### 8.3 备份集防篡改建议

```bash
# 备份完成后生成校验和文件
sha256sum /backup/full/*.bak > /backup/full/checksums.sha256
# 异地传输后校验
sha256sum -c /backup/full/checksums.sha256
```

---

## 九、存储容量规划

### 9.1 备份存储容量估算公式

```
# 全量备份大小（压缩后）
Full_Backup_Size = Database_Size_GB × (1 - Compression_Ratio)

# 增量备份大小（压缩后，差异增量）
Incr_Backup_Size = Database_Size_GB × Daily_Change_Pct × (1 - Compression_Ratio)

# 累积增量备份大小（压缩后）
Cumulative_Backup_Size = Database_Size_GB × Daily_Change_Pct × Days_Since_Level_0 × (1 - Compression_Ratio)

# 归档日志大小（压缩后）
Arch_Backup_Size = Daily_Arch_GB × (1 - Compression_Ratio)

# 总存储需求
Total_Storage = (Full_Count × Full_Size) + (Incr_Count × Incr_Size) + (Arch_Count × Arch_Size) + Safety_Margin
Safety_Margin = 20% ~ 30%
```

### 9.2 容量估算表（示例）

| 数据库大小 | 日变更 | 压缩比 | 策略 | 周备份量 | 保留 14 天 | 保留 30 天 |
|-----------|--------|--------|------|---------|-----------|-----------|
| 100 GB | 5% | 3x | 日全量 | 7 × 33GB = 233GB | 466GB | 1TB |
| 500 GB | 5% | 3x | 周全量+日增量 | 167+7×8=223GB | 446GB | 956GB |
| 1 TB | 5% | 3x | 周全量+日增量 | 333+7×17=452GB | 904GB | 1.94TB |
| 5 TB | 5% | 3x | 月全量+周增量 | 1667+7×83=2248GB | 4.5TB | 9.6TB |

---

## 十、备份策略输出模板

### 输出结构

**1. 环境评估**
- 数据库版本、大小、归档模式
- 当前备份状态（最近备份时间、备份类型、备份大小）
- 归档日志生成速率（日均/峰值）
- FRA 使用情况（如有）

**2. RPO/RTO 需求分析**
- RPO 需求 → 确定的备份频率
- RTO 需求 → 确定的恢复方案
- 备份窗口约束 → 并行度与压缩策略

**3. 备份策略总览**

| 备份类型 | 频率 | 时间窗口 | 目标路径 | 压缩 | 保留 |
|---------|------|---------|---------|------|------|
| 全量备份 | 每周日 | 02:00-06:00 | /backup/full/ | MEDIUM | 14天 |
| 增量备份 | 每天 | 02:00-03:00 | /backup/incr/ | LOW | 14天 |
| 归档日志 | 每30min | 实时 | /backup/arch/ | LOW | 7天 |

**4. RMAN 配置建议**
- 持久化配置命令（CONFIGURE ...）
- 通道配置方案
- 保留策略配置

**5. 备份脚本**
- 全量备份脚本
- 增量备份脚本
- 归档日志备份脚本
- 清理脚本

**6. 存储容量估算**
- 日备份量估算
- 周/月备份量估算
- 保留周期内总存储需求
- 存储增长预测

**7. 备份校验方案**
- 日常校验（CROSSCHECK + VALIDATE）
- 周度校验（RESTORE VALIDATE）
- 恢复演练计划（季度）

**8. 异地容灾方案**（如启用）
- 异地传输方式
- 异地保留策略
- 加密方案

**9. 监控与告警建议**
- 备份失败告警
- 备份超时告警
- 存储空间告警
- 归档日志积压告警

**10. 恢复方案**
- 全量恢复步骤
- 增量恢复步骤
- 时间点恢复（PITR）步骤
- 恢复时间预估

---

## 十一、常见备份场景速查

| 场景 | 推荐策略 | 关键配置 |
|------|---------|---------|
| 新建小库（< 100GB） | 每日全量 + 归档每 4h | `COMPRESSION MEDIUM`, `PARALLELISM 2` |
| 新建中库（100GB~1TB） | 周全量 + 日差异增量 + 归档每 30min | `COMPRESSION MEDIUM`, `PARALLELISM 4` |
| 新建大库（> 1TB） | 月全量 + 周累积增量 + 归档每 30min | `SECTION SIZE 16G`, `PARALLELISM 8` |
| 金融合规（6 个月归档） | 全量+增量+归档 + 异地 6 月 | `RECOVERY WINDOW OF 180 DAYS`, 加密 AES256 |
| 零数据丢失（RPO=0） | 每日全量 + 归档日志实时传输到备库 | `ARCHIVELOG DELETION POLICY TO APPLIED ON STANDBY` |
| 磁带备份 | 磁盘全量 → 磁带副本 | `DUPLEX`, `SBT_TAPE PARALLELISM` 匹配磁带驱动器数 |
| 云存储备份 | 磁盘备份 + S3/OSS 同步 | rsync/s3cmd 到云存储，异地保留 30 天 |
| 最小备份窗口 | 增量合并（BLOCK CHANGE TRACKING） | `BLOCK CHANGE TRACKING` 启用，累积增量策略 |

---

## 十二、RMAN 恢复方案速查（仅输出，不执行）

### 12.1 全量恢复

```bash
# 全量恢复（数据库完全丢失）
rman target /
RMAN> STARTUP NOMOUNT;
RMAN> RESTORE CONTROLFILE FROM AUTOBACKUP;
RMAN> ALTER DATABASE MOUNT;
RMAN> RESTORE DATABASE;
RMAN> RECOVER DATABASE;
RMAN> ALTER DATABASE OPEN RESETLOGS;
```

### 12.2 增量恢复

```bash
# 增量恢复（恢复 Level 0 + 增量 Level 1）
rman target /
RMAN> STARTUP NOMOUNT;
RMAN> RESTORE CONTROLFILE FROM AUTOBACKUP;
RMAN> ALTER DATABASE MOUNT;
RMAN> RESTORE DATABASE;  -- 自动选择最优恢复链
RMAN> RECOVER DATABASE;
RMAN> ALTER DATABASE OPEN RESETLOGS;
```

### 12.3 时间点恢复（PITR）

```bash
# 时间点恢复（恢复到指定时间点）
rman target /
RMAN> STARTUP NOMOUNT;
RMAN> RESTORE CONTROLFILE FROM AUTOBACKUP;
RMAN> ALTER DATABASE MOUNT;
RMAN> RUN {
  SET UNTIL TIME "TO_DATE('2026-08-17 10:00:00', 'YYYY-MM-DD HH24:MI:SS')";
  RESTORE DATABASE;
  RECOVER DATABASE;
}
RMAN> ALTER DATABASE OPEN RESETLOGS;
```

### 12.4 恢复时间预估

```
恢复时间 ≈ 全量备份恢复时间 + 增量恢复时间 + 归档日志应用时间

全量备份恢复时间 ≈ Database_Size_GB / 恢复速率(GB/h)
典型恢复速率：
  - 本地 SSD: 200-500 GB/h
  - 本地 HDD: 100-200 GB/h
  - NFS/网络存储: 50-150 GB/h
  - 磁带: 30-80 GB/h（含寻道时间）

增量恢复时间 ≈ 增量备份大小 / 恢复速率
归档日志应用时间 ≈ 归档日志大小 / 恢复速率
```

---

## 十三、监控与告警建议

### 13.1 关键监控指标

| 监控项 | 告警阈值 | 检查 SQL/脚本 |
|--------|---------|-------------|
| 最近备份时间 | 超过备份周期未备份 | 检查 `v$rman_backup_job_details` 最近记录 |
| 备份失败 | 任一备份作业失败 | 检查日志中的 ERROR / ORA- |
| 归档日志积压 | 未备份归档日志 > 50 个 | `SELECT COUNT(*) FROM v$archived_log WHERE backed_up='NO'` |
| FRA 使用率 | > 80% | `SELECT * FROM v$recovery_file_dest` |
| 备份目录空间 | > 80% | `df -h /backup` |
| 备份超时 | 超过预期备份窗口 | 对比 `elapsed_seconds` 与历史均值 |
| 备份压缩比异常 | 压缩比 < 1.5x | 检查压缩配置是否生效 |

### 13.2 告警查询 SQL

```sql
-- 检查未备份的归档日志数量
SELECT thread#,
       COUNT(*) AS unbacked_arch_count
FROM v$archived_log
WHERE backed_up = 'NO'
  AND deleted = 'NO'
  AND completion_time > SYSDATE - 3
GROUP BY thread#;

-- 检查最近 24 小时是否有备份完成
SELECT CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'NO BACKUP IN LAST 24H' END AS backup_status
FROM v$rman_backup_job_details
WHERE start_time > SYSDATE - 1
  AND status = 'COMPLETED';

-- 备份文件时效性检查
SELECT file#,
       MAX(completion_time) AS last_backup,
       ROUND(SYSDATE - MAX(completion_time), 2) AS days_since_backup
FROM v$backup_datafile
GROUP BY file#
HAVING ROUND(SYSDATE - MAX(completion_time), 2) > 7;
```

---

## 异常处理
- 归档日志生成速率异常（如批量作业导致日志暴增），提示调整备份频率或增加临时归档日志备份。
- 部分性能视图（如 `v$rman_backup_job_details`）在早期版本可能不可用，回退到 `v$backup_set` 查询。
- 备份空间不足时，提示缩短保留周期或增加存储容量。
- 备份窗口超时，提示调整并行度、压缩级别或使用增量合并策略。
- 本技能仅做只读诊断与方案输出，不执行任何备份/恢复操作，单次执行耗时 ≤5s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. **环境评估**：数据库版本/大小/归档模式/归档日志生成速率/FRA使用情况
  2. **RPO/RTO 需求分析**：备份频率确定依据
  3. **备份策略总览**：备份类型/频率/时间窗口/目标路径/压缩/保留（表格）
  4. **RMAN 配置建议**：持久化配置命令（仅输出，不执行）
  5. **备份脚本**：全量/增量/归档日志备份脚本模板
  6. **存储容量估算**：日/周/月备份量 + 保留周期总需求
  7. **备份校验方案**：日常/周度/恢复演练校验计划
  8. **异地容灾方案**（如启用）：传输方式/保留策略/加密
  9. **恢复方案**：全量恢复/增量恢复/PITR 步骤 + 恢复时间预估
  10. **监控与告警建议**：关键指标 + 告警阈值 + 告警 SQL