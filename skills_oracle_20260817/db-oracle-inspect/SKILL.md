---
name: "db-oracle-inspect"
description: "Oracle 数据库健康巡检技能。核心能力：实例基础信息采集（版本/运行时间/归档模式/字符集）、配置参数审查（SGA/PGA/memory_target/processes/sessions/open_cursors/redo 大小/闪回开关）、表空间使用率诊断（使用率/自动扩展/离线表空间/ASM 磁盘组）、性能基线评估（Buffer Hit/ Library Hit/ 软解析率/ 内存排序率等命中率指标）、等待事件 TOP N 分析（当前实时等待 + 历史等待类分布）、会话负载分析（活跃会话/阻塞会话/长时间运行 SQL）、备份状态检查（RMAN 最近备份时间/归档日志连续性/闪回区空间）、DG/备库同步状态（传输延迟/应用延迟/GAP 检查）、无效对象检测（INVALID 对象/不可用索引）、告警日志错误扫描（最近 N 天 ORA- 错误统计）。适用场景：定期数据库健康巡检、上线前环境验收、故障排查前的全面体检、运维交接时的环境盘点。功能限制：纯只读巡检（query 安全等级），不执行 DDL/DML、不修改参数、不 KILL 会话、不执行备份恢复、不调用其他 Skill；单次巡检耗时取决于数据库规模，建议在低负载时段执行。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "inspect_scope"
    type: "string"
    required: false
    default: "full"
    desc: "巡检范围：full（全面巡检）/ basic（基础信息+表空间+性能）/ perf（仅性能指标）/ storage（仅存储与表空间）/ backup（仅备份与 DG）/ security（仅对象状态与安全）"
  - name: "alert_log_days"
    type: "integer"
    required: false
    default: 7
    desc: "告警日志扫描天数，默认最近 7 天"
  - name: "tablespace_alert_pct"
    type: "integer"
    required: false
    default: 80
    desc: "表空间使用率告警阈值（%），超过此阈值标记为告警，默认 80"
  - name: "top_n"
    type: "integer"
    required: false
    default: 10
    desc: "返回 TOP N 条等待事件 / SQL，默认 10"
  - name: "include_asm"
    type: "boolean"
    required: false
    default: true
    desc: "是否包含 ASM 磁盘组巡检（默认 true，非 ASM 环境自动跳过）"
  - name: "include_dg"
    type: "boolean"
    required: false
    default: true
    desc: "是否包含 DataGuard 备库同步状态检查（默认 true，非 DG 环境自动跳过）"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 数据库健康巡检

本技能为只读巡检技能，从 Oracle 数据字典（DBA_*/V$ 视图）全面采集数据库健康指标，涵盖实例基础信息、配置参数、表空间存储、性能基线、等待事件、会话负载、备份状态、DG 同步、对象状态、告警日志等 10 大维度，产出结构化健康报告与风险评级（不执行任何变更）。

---

## 核心能力

- 实例基础信息采集（版本、运行时间、归档模式、字符集、闪回状态、日志模式）
- 配置参数审查（SGA/PGA/memory_target/processes/sessions/open_cursors/redo 大小/块大小等）
- 表空间使用率诊断（使用率排名、自动扩展状态、离线表空间、数据文件状态、ASM 磁盘组使用率）
- 性能基线评估（Buffer Hit / Library Hit / 软解析率 / 内存排序率 / 行缓存命中率等命中率指标）
- 等待事件 TOP N 分析（当前实时等待 + 等待类分布）
- 会话负载分析（活跃会话数、阻塞会话、长时间运行 SQL、连接来源分布）
- 备份状态检查（RMAN 最近备份时间、归档日志连续性、闪回恢复区空间）
- DG/备库同步状态（传输延迟、应用延迟、GAP 检查）
- 无效对象检测（INVALID 对象、不可用索引）
- 告警日志错误扫描（最近 N 天 ORA- 错误统计）

## 适用场景

- 定期数据库健康巡检（建议每周/每月执行）
- 新实例上线前环境验收
- 故障排查前的全面体检
- 运维交接时环境盘点
- 合规审计前的数据库状态自检
- 容量规划基础数据采集
- 数据库迁移/升级前状态基线

## 功能限制 / 安全边界

- 纯只读巡检（query 安全等级），不执行任何 DDL/DML
- 不修改数据库参数、不 KILL 会话、不执行备份恢复
- 不生成 AWR 快照、不收集统计信息
- 不调用其他 Skill、不自动修复、仅按需手动触发
- 告警日志扫描依赖数据库服务器文件系统权限，若无权限则跳过并标注
- ASM 和 DG 检查在非 ASM/DG 环境中自动跳过，不报错

---

## 一、推理框架：巡检执行链

```
用户提交数据库巡检需求
    |
    v
[1] 实例基础信息采集
    | 版本、补丁、运行时间、归档模式、字符集、闪回状态
    v
[2] 配置参数审查
    | SGA/PGA、processes/sessions、open_cursors、redo 大小
    v
[3] 表空间与存储诊断
    | 表空间使用率、自动扩展、离线表空间、数据文件、ASM 磁盘组
    v
[4] 性能基线评估
    | 命中率指标（Buffer/Library/软解析/内存排序/行缓存）
    v
[5] 等待事件分析
    | 当前实时等待 + 等待类分布
    v
[6] 会话负载分析
    | 活跃会话、阻塞会话、长时间 SQL、连接来源
    v
[7] 备份状态检查
    | RMAN 最近备份、归档连续性、闪回区空间
    v
[8] DG/备库同步状态
    | 传输延迟、应用延迟、GAP（非 DG 环境跳过）
    v
[9] 无效对象检测
    | INVALID 对象、UNUSABLE 索引
    v
[10] 告警日志错误扫描
    | 最近 N 天 ORA- 错误统计
    v
[11] 综合健康评分与建议
    | 按维度评分 + 风险项汇总 + 修复建议
```

---

## 二、实例基础信息采集（只读）

```sql
-- 数据库版本与补丁
SELECT banner FROM v$version WHERE ROWNUM <= 3;

-- 实例名、主机名、版本、运行时间、状态
SELECT instance_name,
       host_name,
       version,
       TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time,
       status,
       database_status,
       ROUND(SYSDATE - startup_time, 2) AS uptime_days
FROM v$instance;

-- 数据库名、归档模式、闪回状态、日志模式
SELECT name AS db_name,
       db_unique_name,
       created,
       TO_CHAR(resetlogs_time, 'YYYY-MM-DD HH24:MI:SS') AS resetlogs_time,
       log_mode,
       open_mode,
       database_role,
       flashback_on,
       force_logging,
       protection_mode,
       platform_name
FROM v$database;

-- 字符集信息
SELECT parameter, value
FROM nls_database_parameters
WHERE parameter IN ('NLS_CHARACTERSET', 'NLS_NCHAR_CHARACTERSET', 'NLS_LANGUAGE', 'NLS_TERRITORY');
```

---

## 三、配置参数审查（只读）

```sql
-- 核心内存参数
SELECT name,
       ROUND(value / 1024 / 1024 / 1024, 2) AS value_gb,
       CASE name
         WHEN 'memory_target' THEN '自动内存管理总大小'
         WHEN 'memory_max_target' THEN '自动内存管理最大限制'
         WHEN 'sga_target' THEN 'SGA 自动管理目标'
         WHEN 'sga_max_size' THEN 'SGA 最大限制'
         WHEN 'pga_aggregate_target' THEN 'PGA 聚合目标'
         ELSE ''
       END AS desc_cn
FROM v$parameter
WHERE name IN ('memory_target', 'memory_max_target', 'sga_target', 'sga_max_size', 'pga_aggregate_target')
ORDER BY name;

-- 连接与游标参数
SELECT name,
       value,
       CASE name
         WHEN 'processes' THEN '最大进程数'
         WHEN 'sessions' THEN '最大会话数'
         WHEN 'open_cursors' THEN '最大打开游标数'
         WHEN 'session_cached_cursors' THEN '会话缓存游标数'
         WHEN 'cursor_sharing' THEN '游标共享模式'
         WHEN 'db_block_size' THEN '数据块大小(Bytes)'
         WHEN 'db_files' THEN '最大数据文件数'
         WHEN 'undo_retention' THEN 'UNDO 保留时间(秒)'
         ELSE ''
       END AS desc_cn
FROM v$parameter
WHERE name IN ('processes', 'sessions', 'open_cursors', 'session_cached_cursors',
               'cursor_sharing', 'db_block_size', 'db_files', 'undo_retention')
ORDER BY name;

-- 在线 REDO 日志配置
SELECT group#,
       thread#,
       sequence#,
       ROUND(bytes / 1024 / 1024, 2) AS size_mb,
       members,
       status,
       archived
FROM v$log
ORDER BY group#, thread#;

-- 在线 REDO 日志成员
SELECT group#,
       member,
       type,
       status
FROM v$logfile
ORDER BY group#, member;
```

---

## 四、表空间与存储诊断（只读）

### 4.1 表空间使用率

```sql
-- 表空间使用率排名（含使用率、自动扩展、数据文件数）
SELECT a.tablespace_name,
       ROUND(a.total_mb, 2) AS total_mb,
       ROUND(NVL(b.used_mb, 0), 2) AS used_mb,
       ROUND(NVL(a.total_mb - NVL(b.used_mb, 0), 0), 2) AS free_mb,
       ROUND(NVL(b.used_mb, 0) / a.total_mb * 100, 2) AS used_pct,
       a.autoextensible,
       a.file_count,
       CASE
         WHEN b.used_mb / a.total_mb * 100 >= 95 THEN 'CRITICAL'
         WHEN b.used_mb / a.total_mb * 100 >= 80 THEN 'WARNING'
         ELSE 'OK'
       END AS status
FROM (
    SELECT tablespace_name,
           ROUND(SUM(bytes) / 1024 / 1024, 2) AS total_mb,
           MAX(autoextensible) AS autoextensible,
           COUNT(*) AS file_count
    FROM dba_data_files
    GROUP BY tablespace_name
    UNION ALL
    SELECT tablespace_name,
           ROUND(SUM(bytes) / 1024 / 1024, 2) AS total_mb,
           'YES' AS autoextensible,
           COUNT(*) AS file_count
    FROM dba_temp_files
    GROUP BY tablespace_name
) a
LEFT JOIN (
    SELECT tablespace_name,
           ROUND(SUM(bytes) / 1024 / 1024, 2) AS used_mb
    FROM dba_segments
    GROUP BY tablespace_name
) b ON a.tablespace_name = b.tablespace_name
ORDER BY used_pct DESC NULLS LAST;
```

### 4.2 离线表空间与数据文件状态

```sql
-- 离线表空间
SELECT tablespace_name, status
FROM dba_tablespaces
WHERE status != 'ONLINE';

-- 数据文件状态异常
SELECT file_name,
       tablespace_name,
       status,
       online_status,
       ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb,
       autoextensible
FROM dba_data_files
WHERE status != 'AVAILABLE' OR online_status != 'ONLINE';
```

### 4.3 ASM 磁盘组使用率（ASM 环境）

```sql
-- ASM 磁盘组使用率
SELECT name,
       ROUND(total_mb / 1024, 2) AS total_gb,
       ROUND(free_mb / 1024, 2) AS free_gb,
       ROUND((total_mb - free_mb) / 1024, 2) AS used_gb,
       ROUND((total_mb - free_mb) / total_mb * 100, 2) AS used_pct,
       type,
       state,
       sector_size,
       allocation_unit_size / 1024 / 1024 AS au_mb
FROM v$asm_diskgroup
ORDER BY name;
```

### 4.4 表空间增长趋势（最近 30 天）

```sql
-- 表空间日增量（基于 DBA_HIST 数据）
SELECT a.tablespace_name,
       ROUND((a.total_mb - NVL(b.total_mb, 0)), 2) AS growth_mb_30d,
       ROUND((a.total_mb - NVL(b.total_mb, 0)) / 30, 2) AS avg_daily_growth_mb,
       ROUND((a.total_mb - NVL(b.total_mb, 0)) / a.total_mb * 100, 2) AS growth_pct_30d
FROM (
    SELECT tablespace_name, ROUND(SUM(tablespace_size * 8192) / 1024 / 1024, 2) AS total_mb
    FROM dba_hist_tbspc_space_usage
    WHERE snap_id = (SELECT MAX(snap_id) FROM dba_hist_tbspc_space_usage)
    GROUP BY tablespace_name
) a
LEFT JOIN (
    SELECT tablespace_name, ROUND(SUM(tablespace_size * 8192) / 1024 / 1024, 2) AS total_mb
    FROM dba_hist_tbspc_space_usage
    WHERE snap_id = (SELECT MIN(snap_id) FROM dba_hist_tbspc_space_usage
                     WHERE snap_id >= (SELECT MAX(snap_id) - 30 FROM dba_hist_snapshot))
    GROUP BY tablespace_name
) b ON a.tablespace_name = b.tablespace_name
ORDER BY growth_mb_30d DESC;
```

---

## 五、性能基线评估（只读）

### 5.1 命中率指标

```sql
-- 核心命中率指标（基于当前累积值，非增量）
SELECT 'Buffer Cache Hit Ratio' AS metric_name,
       ROUND((1 - (phy.value / (cur.value + con.value))) * 100, 2) AS hit_pct,
       CASE
         WHEN (1 - (phy.value / (cur.value + con.value))) * 100 >= 95 THEN 'OK'
         WHEN (1 - (phy.value / (cur.value + con.value))) * 100 >= 90 THEN 'WARNING'
         ELSE 'CRITICAL'
       END AS status
FROM v$sysstat cur, v$sysstat phy, v$sysstat con
WHERE cur.name = 'db block gets'
  AND con.name = 'consistent gets'
  AND phy.name = 'physical reads'
UNION ALL
SELECT 'Library Cache Hit Ratio',
       ROUND((1 - (pinhits.value / pins.value)) * 100, 2),
       CASE
         WHEN (1 - (pinhits.value / pins.value)) * 100 >= 95 THEN 'OK'
         WHEN (1 - (pinhits.value / pins.value)) * 100 >= 90 THEN 'WARNING'
         ELSE 'CRITICAL'
       END
FROM v$librarycache
WHERE namespace = 'SQL AREA'
UNION ALL
SELECT 'Soft Parse Ratio',
       ROUND((1 - (hard.value / total.value)) * 100, 2),
       CASE
         WHEN (1 - (hard.value / total.value)) * 100 >= 95 THEN 'OK'
         WHEN (1 - (hard.value / total.value)) * 100 >= 90 THEN 'WARNING'
         ELSE 'CRITICAL'
       END
FROM v$sysstat hard, v$sysstat total
WHERE hard.name = 'parse count (hard)'
  AND total.name = 'parse count (total)'
UNION ALL
SELECT 'Memory Sorts Ratio',
       ROUND((mem.value / (mem.value + disk.value)) * 100, 2),
       CASE
         WHEN (mem.value / (mem.value + disk.value)) * 100 >= 95 THEN 'OK'
         WHEN (mem.value / (mem.value + disk.value)) * 100 >= 90 THEN 'WARNING'
         ELSE 'CRITICAL'
       END
FROM v$sysstat mem, v$sysstat disk
WHERE mem.name = 'sorts (memory)'
  AND disk.name = 'sorts (disk)'
UNION ALL
SELECT 'Row Cache Hit Ratio',
       ROUND(SUM(gets - getmisses) / SUM(gets) * 100, 2),
       CASE
         WHEN SUM(gets - getmisses) / SUM(gets) * 100 >= 90 THEN 'OK'
         WHEN SUM(gets - getmisses) / SUM(gets) * 100 >= 85 THEN 'WARNING'
         ELSE 'CRITICAL'
       END
FROM v$rowcache
UNION ALL
SELECT 'Latch Hit Ratio',
       ROUND((1 - (m.value / g.value)) * 100, 2),
       CASE
         WHEN (1 - (m.value / g.value)) * 100 >= 99 THEN 'OK'
         WHEN (1 - (m.value / g.value)) * 100 >= 95 THEN 'WARNING'
         ELSE 'CRITICAL'
       END
FROM v$sysstat m, v$sysstat g
WHERE m.name = 'latch misses'
  AND g.name = 'latch gets';
```

### 5.2 命中率健康阈值参考

| 命中率指标 | 健康阈值 | 低于阈值排查方向 |
|-----------|---------|----------------|
| Buffer Cache Hit Ratio | > 95% | 增大 SGA / 检查全表扫描 SQL |
| Library Cache Hit Ratio | > 95% | 检查硬解析、未使用绑定变量、增大共享池 |
| Soft Parse Ratio | > 95% | 检查绑定变量使用、CURSOR_SHARING |
| Memory Sorts Ratio | > 95% | 增大 PGA_AGGREGATE_TARGET |
| Row Cache Hit Ratio | > 90% | 检查 DDL 频率、增大共享池 |
| Latch Hit Ratio | > 99% | 检查热块 SQL、高并发访问 |

---

## 六、等待事件分析（只读）

### 6.1 当前实时等待事件 TOP N

```sql
-- 当前实时等待事件分布
SELECT event,
       wait_class,
       COUNT(*) AS session_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM v$session
WHERE wait_class != 'Idle'
  AND status = 'ACTIVE'
GROUP BY event, wait_class
ORDER BY session_count DESC;
```

### 6.2 系统级等待事件累计（自实例启动）

```sql
-- 系统级等待事件按等待类聚合（自实例启动累计）
SELECT wait_class,
       ROUND(SUM(time_waited_micro) / 1000000, 2) AS total_wait_sec,
       ROUND(SUM(time_waited_micro) * 100.0 / SUM(SUM(time_waited_micro)) OVER (), 2) AS pct
FROM v$system_event
WHERE wait_class != 'Idle'
  AND time_waited_micro > 0
GROUP BY wait_class
ORDER BY total_wait_sec DESC;
```

### 6.3 等待事件 TOP N（自实例启动）

```sql
-- 等待事件 TOP N
SELECT *
FROM (
    SELECT event,
           wait_class,
           ROUND(time_waited_micro / 1000000, 2) AS wait_sec,
           total_waits,
           ROUND(time_waited_micro / GREATEST(total_waits, 1) / 1000, 2) AS avg_wait_ms
    FROM v$system_event
    WHERE wait_class != 'Idle'
      AND time_waited_micro > 0
    ORDER BY wait_sec DESC
)
WHERE ROWNUM <= 10;
```

---

## 七、会话负载分析（只读）

### 7.1 会话概览

```sql
-- 会话状态统计
SELECT status, type, COUNT(*) AS session_count
FROM v$session
GROUP BY status, type
ORDER BY status, type;

-- 按用户名统计活跃会话
SELECT username, COUNT(*) AS active_count
FROM v$session
WHERE status = 'ACTIVE'
  AND type = 'USER'
  AND username IS NOT NULL
GROUP BY username
ORDER BY active_count DESC;

-- 按机器来源统计连接数
SELECT machine,
       COUNT(*) AS connection_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM v$session
WHERE type = 'USER'
  AND username IS NOT NULL
GROUP BY machine
ORDER BY connection_count DESC;
```

### 7.2 阻塞会话检测

```sql
-- 当前阻塞会话链
SELECT blocking_session_status,
       blocking_instance,
       blocking_session,
       sid,
       serial#,
       username,
       status,
       seconds_in_wait,
       wait_class,
       event,
       state,
       sql_id,
       ROW_WAIT_OBJ#,
       TO_CHAR(sql_exec_start, 'YYYY-MM-DD HH24:MI:SS') AS sql_start_time
FROM v$session
WHERE blocking_session IS NOT NULL
  AND blocking_session_status = 'VALID'
ORDER BY blocking_session, sid;
```

### 7.3 长时间运行 SQL（活跃 > 5 分钟）

```sql
-- 长时间运行的活跃 SQL
SELECT s.sid,
       s.serial#,
       s.username,
       s.machine,
       s.program,
       s.status,
       s.last_call_et AS run_seconds,
       ROUND(s.last_call_et / 60, 2) AS run_minutes,
       s.sql_id,
       s.event,
       SUBSTR(q.sql_text, 1, 200) AS sql_text,
       TO_CHAR(s.sql_exec_start, 'YYYY-MM-DD HH24:MI:SS') AS exec_start
FROM v$session s
LEFT JOIN v$sql q ON s.sql_id = q.sql_id
WHERE s.status = 'ACTIVE'
  AND s.type = 'USER'
  AND s.last_call_et > 300
ORDER BY s.last_call_et DESC;
```

### 7.4 资源使用率检查

```sql
-- 当前会话数 vs 最大会话数
SELECT
    (SELECT COUNT(*) FROM v$session) AS current_sessions,
    (SELECT value FROM v$parameter WHERE name = 'sessions') AS max_sessions,
    ROUND((SELECT COUNT(*) FROM v$session) / (SELECT value FROM v$parameter WHERE name = 'sessions') * 100, 2) AS session_used_pct;

-- 当前进程数 vs 最大进程数
SELECT
    (SELECT COUNT(*) FROM v$process) AS current_processes,
    (SELECT value FROM v$parameter WHERE name = 'processes') AS max_processes,
    ROUND((SELECT COUNT(*) FROM v$process) / (SELECT value FROM v$parameter WHERE name = 'processes') * 100, 2) AS process_used_pct;

-- 当前打开游标数 vs 最大游标数
SELECT
    (SELECT COUNT(*) FROM v$open_cursor) AS current_open_cursors,
    (SELECT value FROM v$parameter WHERE name = 'open_cursors') AS max_open_cursors,
    ROUND((SELECT COUNT(*) FROM v$open_cursor) / (SELECT value FROM v$parameter WHERE name = 'open_cursors') * 100, 2) AS cursor_used_pct;
```

---

## 八、备份状态检查（只读）

### 8.1 RMAN 最近备份状态

```sql
-- 最近备份概览
SELECT input_type AS backup_type,
       status,
       TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI:SS') AS start_time,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI:SS') AS completion_time,
       ROUND(elapsed_seconds / 60, 2) AS elapsed_min,
       ROUND(input_bytes / 1024 / 1024 / 1024, 2) AS input_gb,
       ROUND(output_bytes / 1024 / 1024 / 1024, 2) AS output_gb,
       input_type,
       ROUND(compression_ratio, 2) AS compression_ratio
FROM v$rman_backup_job_details
WHERE start_time > SYSDATE - 30
ORDER BY start_time DESC;
```

### 8.2 归档日志连续性

```sql
-- 归档日志序列号连续性检查
SELECT thread#,
       MIN(sequence#) AS min_seq,
       MAX(sequence#) AS max_seq,
       COUNT(*) AS arc_count,
       MAX(sequence#) - MIN(sequence#) + 1 - COUNT(*) AS gap_count
FROM v$archived_log
WHERE completion_time > SYSDATE - 7
GROUP BY thread#;

-- 最近归档日志生成时间
SELECT thread#,
       sequence#,
       TO_CHAR(first_time, 'YYYY-MM-DD HH24:MI:SS') AS first_time,
       TO_CHAR(completion_time, 'YYYY-MM-DD HH24:MI:SS') AS completion_time,
       ROUND((completion_time - first_time) * 24 * 60, 2) AS generation_min
FROM v$archived_log
WHERE completion_time > SYSDATE - 1
ORDER BY thread#, sequence# DESC;
```

### 8.3 闪回恢复区

```sql
-- 闪回恢复区空间使用率
SELECT name,
       ROUND(space_limit / 1024 / 1024 / 1024, 2) AS limit_gb,
       ROUND(space_used / 1024 / 1024 / 1024, 2) AS used_gb,
       ROUND(space_reclaimable / 1024 / 1024 / 1024, 2) AS reclaimable_gb,
       ROUND((space_used - space_reclaimable) / space_limit * 100, 2) AS used_pct,
       number_of_files,
       con_id
FROM v$recovery_file_dest;
```

---

## 九、DG/备库同步状态（只读，非 DG 环境自动跳过）

### 9.1 DG 配置状态

```sql
-- 主库 DG 目标配置
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

-- DG 传输与应用延迟
SELECT name,
       value,
       time_computed,
       datum_time
FROM v$dataguard_stats
WHERE name IN ('transport lag', 'apply lag', 'apply finish time');
```

### 9.2 备库 MRP 状态

```sql
-- 备库 MRP 进程状态（在备库执行）
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

---

## 十、无效对象检测（只读）

### 10.1 无效对象

```sql
-- 无效对象统计
SELECT object_type,
       owner,
       COUNT(*) AS invalid_count
FROM dba_objects
WHERE status = 'INVALID'
GROUP BY object_type, owner
ORDER BY invalid_count DESC;

-- 无效对象详情（最多 20 条）
SELECT *
FROM (
    SELECT owner,
           object_name,
           object_type,
           status,
           TO_CHAR(last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') AS last_ddl_time
    FROM dba_objects
    WHERE status = 'INVALID'
    ORDER BY last_ddl_time DESC
)
WHERE ROWNUM <= 20;
```

### 10.2 不可用索引

```sql
-- 不可用索引
SELECT owner,
       index_name,
       table_name,
       status,
       tablespace_name,
       TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed
FROM dba_indexes
WHERE status = 'UNUSABLE'
ORDER BY owner, index_name;
```

### 10.3 统计信息陈旧对象

```sql
-- 统计信息超过 30 天未更新的表
SELECT owner,
       table_name,
       num_rows,
       blocks,
       TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed,
       ROUND(SYSDATE - last_analyzed, 0) AS days_stale
FROM dba_tables
WHERE last_analyzed IS NOT NULL
  AND owner NOT IN ('SYS', 'SYSTEM', 'AUDSYS', 'XDB', 'DBSNMP', 'APPQOSSYS', 'WMSYS', 'MDSYS')
  AND SYSDATE - last_analyzed > 30
ORDER BY num_rows DESC NULLS LAST;
```

---

## 十一、告警日志错误扫描（只读）

```sql
-- 查询最近 N 天的 ORA- 错误（基于 ADR 命令行视图）
-- 方式一：通过 v$diag_alert_ext 读取告警日志（12c+）
SELECT originating_timestamp,
       message_type,
       message_text
FROM v$diag_alert_ext
WHERE message_text LIKE '%ORA-%'
  AND originating_timestamp > SYSDATE - 7
ORDER BY originating_timestamp DESC;

-- 方式二：通过外部表读取告警日志（11g）
-- CREATE DIRECTORY alert_dir AS '<alert_log_path>';
-- 然后通过外部表访问，此处省略 DDL
```

### 告警日志错误统计

```sql
-- ORA- 错误分类统计（12c+）
SELECT REGEXP_SUBSTR(message_text, 'ORA-\d{5}') AS error_code,
       COUNT(*) AS occurrence_count,
       MIN(TO_CHAR(originating_timestamp, 'YYYY-MM-DD HH24:MI:SS')) AS first_occurrence,
       MAX(TO_CHAR(originating_timestamp, 'YYYY-MM-DD HH24:MI:SS')) AS last_occurrence
FROM v$diag_alert_ext
WHERE message_text LIKE '%ORA-%'
  AND originating_timestamp > SYSDATE - 7
GROUP BY REGEXP_SUBSTR(message_text, 'ORA-\d{5}')
ORDER BY occurrence_count DESC;
```

---

## 十二、综合健康评分

巡检完成后，按以下维度输出综合评分（满分 100）：

| 维度 | 权重 | 评分项 | 扣分规则 |
|------|------|--------|---------|
| 表空间 | 20 | 使用率 | 每个 CRITICAL 表空间扣 5 分，WARNING 扣 2 分 |
| 性能 | 25 | 命中率 | 每项不达标扣 5 分 |
| 会话 | 10 | 连接资源 | 会话/进程使用率 > 80% 扣 5 分 |
| 备份 | 15 | 备份时效 | 最近全量备份超过 7 天扣 5 分，超过 14 天扣 10 分 |
| DG | 10 | 同步状态 | 存在 GAP 或延迟 > 30s 扣 5 分（非 DG 跳过） |
| 对象 | 10 | 无效对象 | 存在 INVALID 对象扣 3 分，UNUSABLE 索引扣 5 分 |
| 告警 | 10 | 错误日志 | 存在 ORA- 错误扣 5 分，严重错误（ORA-00600/ORA-07445）扣 10 分 |

---

## 异常处理

- 单条查询失败不影响整体，标记该维度异常后继续其余查询
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈
- ASM 相关查询在非 ASM 环境返回空结果属正常，标记"非 ASM 环境"
- DG 相关查询在非 DG 环境返回空结果属正常，标记"非 DG 环境"
- 告警日志查询在无权限时跳过，标记"无告警日志访问权限"
- 本技能仅做只读巡检，不执行任何 DDL/DML，单次执行耗时取决于数据库规模，建议在低负载时段执行
- 无第三方依赖、无常驻逻辑

## 输出格式

结构化输出：
1. **巡检概览**：实例名、版本、运行时间、巡检时间、巡检范围
2. **实例基础信息**：版本、补丁、归档模式、字符集、闪回状态、日志模式
3. **配置参数摘要**：SGA/PGA、连接参数、REDO 配置
4. **表空间使用率**：排名表 + 告警列表 + 增长趋势 + ASM 磁盘组
5. **性能基线**：各项命中率指标 + 状态
6. **等待事件 TOP N**：当前实时等待 + 等待类分布
7. **会话负载**：活跃会话、阻塞会话、长时间 SQL、连接来源
8. **备份状态**：最近备份时间、归档连续性、闪回区空间
9. **DG 同步状态**：传输/应用延迟、GAP 状态（非 DG 跳过）
10. **无效对象**：INVALID 对象列表、UNUSABLE 索引
11. **告警日志**：最近 N 天 ORA- 错误统计
12. **综合健康评分**：各维度得分 + 风险项汇总 + 修复建议