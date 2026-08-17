---
name: "db-oracle-diagnose-perf"
description: "Oracle 综合性能诊断技能（CPU / IO / 锁三维一体）。核心能力：(1) CPU 诊断：OS 级 CPU 负载、DB CPU 与时间模型分解、TOP CPU 消耗 SQL 定位、CPU 相关等待事件分析；(2) IO 诊断：表空间/数据文件 IO 读写分布与吞吐、IO 等待事件（db file sequential/scattered read、log file parallel write 等）、Temp 表空间使用与排序溢出检测；(3) 锁诊断：实时锁等待链（V$LOCK / DBA_WAITERS）、阻塞会话与等待 SQL 关联、enqueue 锁类型（TX/TM/UL）争用分析、锁等待历史趋势。适用场景：数据库综合性能瓶颈定位（CPU 高/IO 慢/锁等待）、慢 SQL 问题分维度排查、定期性能巡检。功能限制：仅做只读诊断与参考，不 KILL 会话、不修改参数、不执行 DDL/DML。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "diagnose_scope"
    type: "string"
    required: false
    default: "all"
    desc: "诊断范围：all（全部）/ cpu（仅 CPU）/ io（仅 IO）/ lock（仅锁）"
  - name: "top_n"
    type: "integer"
    required: false
    default: 10
    desc: "返回 TOP N 条结果，默认 10"
  - name: "time_range_hours"
    type: "integer"
    required: false
    default: 24
    desc: "历史数据查询时间范围（小时），默认最近 24 小时"
  - name: "snap_id_begin"
    type: "integer"
    required: false
    default: 0
    desc: "AWR 历史查询起始快照 ID（为 0 则自动选择最近一对快照）"
  - name: "snap_id_end"
    type: "integer"
    required: false
    default: 0
    desc: "AWR 历史查询结束快照 ID（为 0 则自动选择最近一对快照）"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 综合性能诊断：CPU / IO / 锁

本技能为只读诊断技能，从 v$ 动态视图、AWR 历史快照（DBA_HIST_*）与 OS 层统计信息三个维度，对 Oracle 数据库进行 CPU、IO、锁的综合性能诊断，定位瓶颈并给出优化方向建议（不执行任何变更）。

---

## 核心能力

### CPU 诊断
- OS 级 CPU 使用率（OS Load、%User/%Sys/%Idle、CPU 核数）
- DB CPU 与时间模型分解（DB Time vs DB CPU、sql execute / parse / PL/SQL 占比）
- TOP CPU 消耗 SQL 定位（按 CPU Time / Elapsed Time 排序）
- CPU 相关等待事件（CPU + CPU Wait / scheduler / resmgr 等）
- 实例 CPU 使用率趋势（AWR 历史）

### IO 诊断
- IO 等待事件分析（db file sequential/scattered read、log file parallel write、direct path read 等）
- 表空间 IO 读写分布（物理读/写次数与吞吐量）
- 数据文件 IO 性能（平均读/写耗时、IOPS）
- Temp 表空间使用与排序溢出检测
- IO 吞吐量与延迟趋势

### 锁诊断
- 实时锁等待链（V$LOCK / DBA_BLOCKERS / DBA_WAITERS）
- 阻塞会话详情（阻塞者与被阻塞者、锁类型、等待 SQL）
- enqueue 锁类型争用分析（TX / TM / UL 等）
- 锁等待历史趋势（AWR 历史 enqueue 统计）
- 热块冲突与 ITL 等待检测

## 适用场景
- 数据库响应变慢，需综合定位是 CPU 瓶颈 / IO 瓶颈 / 锁等待
- 应用反馈"时而快时而慢"，需同时排查 CPU 波动与锁争用
- 定期性能巡检，产出 CPU/IO/锁三维健康报告
- AWR 报告辅助解读，快速定位核心瓶颈维度
- 高并发 OLTP 系统锁争用与 CPU 关联分析
- 批量任务期间的 IO 吞吐与 CPU 压力评估

## 功能限制 / 安全边界
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改实例参数（不执行 ALTER SYSTEM SET）
- 不调整表/索引存储参数（不执行 ALTER TABLE/INDEX）
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）
- 不执行 SQL Profile/SPM 操作
- 不调用其它 Skill、不自动修复、仅按需手动触发

---

## 一、推理框架：综合性能诊断链

```
用户报告数据库性能问题（慢/卡/CPU 高）
    |
    v
[1] 宏观诊断：CPU / IO / 锁 快速概览
    | OS CPU 负载 + DB CPU 占比
    | IO 等待事件占比 + 实时锁等待分布
    v
[2] CPU 深度诊断
    | 时间模型分解（DB Time 分布）
    | TOP CPU SQL 定位
    | CPU 等待事件排查
    v
[3] IO 深度诊断
    | 等待事件 IO 分类（User I/O / System I/O）
    | 表空间/数据文件 IO 热点
    | Temp 溢出检测
    v
[4] 锁深度诊断
    | 当前锁等待链（递归树）
    | 阻塞会话与 SQL 关联
    | enqueue 锁类型争用统计
    | 锁等待历史趋势
    v
[5] 综合诊断结论
    | 三维度瓶颈排序（主瓶颈 > 次瓶颈）
    | 关联分析（锁等待导致 CPU 空转？IO 慢导致 CPU 低？）
    | 优化方向建议（参考，不执行）
```

---

## 二、宏观诊断概览（快速定位瓶颈维度，只读）

### 2.1 OS 级 CPU 负载与 DB CPU 占比

```sql
-- 数据库 CPU 核心数
SELECT value AS cpu_count
FROM v$parameter
WHERE name = 'cpu_count';

-- 当前 OS 级 CPU 使用率（需 OS 工具配合）
-- 可通过 v$osstat 获取 OS 统计
SELECT stat_name,
       value,
       cumulative
FROM v$osstat
WHERE stat_name IN (
    'NUM_CPUS',
    'NUM_CPU_CORES',
    'NUM_CPU_SOCKETS',
    'IDLE_TIME',
    'BUSY_TIME',
    'USER_TIME',
    'SYS_TIME',
    'IOWAIT_TIME',
    'NICE_TIME',
    'LOAD'
)
ORDER BY stat_name;

-- DB CPU 占 OS CPU 的比例
SELECT ROUND(
    (SELECT SUM(value) FROM v$sys_time_model WHERE stat_name = 'DB CPU')
    / (SELECT value FROM v$osstat WHERE stat_name = 'BUSY_TIME' AND cumulative = 'NO')
    * 100, 2
) AS db_cpu_pct
FROM dual;
```

### 2.2 等待事件 IO 大类占比

```sql
-- 等待事件按等待类聚合（非空闲）
SELECT wait_class,
       ROUND(SUM(time_waited_micro) / 1000000, 2) AS total_wait_sec,
       ROUND(SUM(time_waited_micro) * 100.0 / SUM(SUM(time_waited_micro)) OVER (), 2) AS pct_of_total
FROM v$system_event
WHERE wait_class != 'Idle'
  AND time_waited_micro > 0
GROUP BY wait_class
ORDER BY total_wait_sec DESC;

-- IO 相关等待事件 TOP N
SELECT *
FROM (
    SELECT event,
           wait_class,
           total_waits,
           ROUND(time_waited_micro / 1000000, 2) AS total_wait_sec,
           ROUND(time_waited_micro / GREATEST(total_waits, 1) / 1000, 2) AS avg_wait_ms
    FROM v$system_event
    WHERE wait_class IN ('User I/O', 'System I/O')
      AND time_waited_micro > 0
    ORDER BY time_waited_micro DESC
)
WHERE ROWNUM <= 10;
```

### 2.3 实时锁等待概览

```sql
-- 当前锁等待会话数
SELECT COUNT(DISTINCT sid) AS sessions_blocked,
       COUNT(DISTINCT blocking_session) AS sessions_blocking
FROM v$session
WHERE blocking_session IS NOT NULL;

-- 当前锁等待按类型分组
SELECT DECODE(l.type,
           'TX', 'TX (事务锁-行级)',
           'TM', 'TM (表锁/DML)',
           'UL', 'UL (用户锁)',
           'MR', 'MR (介质恢复)',
           'RT', 'RT (Redo 线程)',
           l.type) AS lock_type_desc,
       COUNT(*) AS lock_count,
       COUNT(DISTINCT l.sid) AS session_count
FROM v$lock l
WHERE l.request > 0
  AND l.type IN ('TX', 'TM', 'UL')
GROUP BY l.type
ORDER BY lock_count DESC;
```

---

## 三、CPU 深度诊断（只读）

### 3.1 DB Time 模型分解

```sql
-- 时间模型分解（DB Time 在各维度的占比）
SELECT stat_name,
       ROUND(value / 1000000, 2) AS total_sec,
       ROUND(value * 100.0 / SUM(value) OVER (), 2) AS pct_of_db_time
FROM v$sys_time_model
WHERE stat_name IN (
    'DB time', 'DB CPU',
    'sql execute elapsed time', 'parse time elapsed',
    'hard parse elapsed time', 'soft parse elapsed time',
    'PL/SQL execution elapsed time',
    'connection management call elapsed time',
    'sequence load elapsed time',
    'failed parse elapsed time',
    'inbound PL/SQL rpc elapsed time',
    'RMAN cpu time (backup/restore)',
    'Java execution elapsed time'
)
ORDER BY value DESC;
```

### 3.2 实例级 CPU 使用率

```sql
-- 实例 CPU 使用率（每秒）
SELECT name,
       value
FROM v$sysstat
WHERE name IN (
    'CPU used by this session',
    'parse time cpu',
    'recursive cpu usage',
    'OS CPU Qt wait time'
)
ORDER BY name;

-- CPU 使用率（从 v$sysmetric_history 获取近期趋势）
SELECT begin_time,
       end_time,
       metric_name,
       value,
       metric_unit
FROM v$sysmetric_history
WHERE metric_name IN (
    'Host CPU Utilization (%)',
    'Database CPU Time Ratio',
    'OS Load'
)
  AND begin_time >= SYSDATE - NUMTODSINTERVAL(1, 'HOUR')
ORDER BY begin_time DESC;
```

### 3.3 TOP CPU 消耗 SQL

```sql
-- 实时 TOP CPU SQL（v$sqlstats）
SELECT *
FROM (
    SELECT sql_id,
           SUBSTR(sql_text, 1, 200) AS sql_text,
           ROUND(cpu_time / 1000000, 2) AS cpu_sec,
           ROUND(elapsed_time / 1000000, 2) AS elapsed_sec,
           executions,
           ROUND(cpu_time / GREATEST(executions, 1) / 1000000, 4) AS avg_cpu_sec,
           buffer_gets,
           disk_reads,
           ROUND(cpu_time * 100.0 / SUM(cpu_time) OVER (), 2) AS cpu_pct
    FROM v$sqlstats
    WHERE executions > 0
      AND cpu_time > 0
    ORDER BY cpu_time DESC
)
WHERE ROWNUM <= 10;

-- AWR 历史 TOP CPU SQL（按快照差值）
SELECT *
FROM (
    SELECT s.sql_id,
           SUBSTR(t.sql_text, 1, 200) AS sql_text,
           ROUND(SUM(s.cpu_time_delta) / 1000000, 2) AS total_cpu_sec,
           ROUND(SUM(s.elapsed_time_delta) / 1000000, 2) AS total_elapsed_sec,
           SUM(s.executions_delta) AS executions,
           ROUND(SUM(s.cpu_time_delta) / GREATEST(SUM(s.executions_delta), 1) / 1000000, 4) AS avg_cpu_sec,
           ROUND(SUM(s.cpu_time_delta) * 100.0 / SUM(SUM(s.cpu_time_delta)) OVER (), 2) AS cpu_pct
    FROM dba_hist_sqlstat s
    JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
    WHERE s.snap_id = &snap_id_end
      AND s.cpu_time_delta > 0
    GROUP BY s.sql_id, t.sql_text
    ORDER BY total_cpu_sec DESC
)
WHERE ROWNUM <= 10;
```

### 3.4 CPU 相关等待事件

```sql
-- CPU 相关等待事件（resmgr、scheduler、CPU 队列）
SELECT event,
       wait_class,
       ROUND(time_waited_micro / 1000000, 2) AS total_wait_sec,
       total_waits,
       ROUND(time_waited_micro / GREATEST(total_waits, 1) / 1000, 2) AS avg_wait_ms
FROM v$system_event
WHERE event IN (
    'resmgr:cpu quantum',
    'resmgr:internal state change',
    'scheduler: waiting for cpu',
    'latch: shared pool',
    'latch: library cache',
    'latch: cache buffers chains',
    'cursor: pin S wait on X'
)
  AND time_waited_micro > 0
ORDER BY time_waited_micro DESC;
```

### 3.5 CPU 诊断解读

| 状态 | 判断标准 | 解读 |
|------|---------|------|
| CPU 正常 | DB CPU 占比 < 60%，OS CPU Idle > 20% | 系统 CPU 资源充足 |
| CPU 中等 | DB CPU 占比 60%~85% | 需关注热点 SQL，可能有优化空间 |
| CPU 瓶颈 | DB CPU 占比 > 85%，OS CPU Idle < 10% | 需优化 TOP SQL 或扩容 |
| CPU 空转 | DB CPU 占比低，但锁等待/IO 等待占比高 | 瓶颈在锁或 IO，而非 CPU |
| 硬解析 | hard parse elapsed time 占比 > 5% | 检查绑定变量使用情况 |

---

## 四、IO 深度诊断（只读）

### 4.1 IO 等待事件 TOP N（按等待类分类）

```sql
-- IO 等待事件 TOP N（User I/O + System I/O）
SELECT *
FROM (
    SELECT event,
           wait_class,
           total_waits,
           ROUND(time_waited_micro / 1000000, 2) AS total_wait_sec,
           ROUND(time_waited_micro / 1000000 * 100.0 / SUM(time_waited_micro / 1000000) OVER (), 2) AS pct_of_io,
           ROUND(time_waited_micro / GREATEST(total_waits, 1) / 1000, 2) AS avg_wait_ms
    FROM v$system_event
    WHERE wait_class IN ('User I/O', 'System I/O')
      AND time_waited_micro > 0
    ORDER BY time_waited_micro DESC
)
WHERE ROWNUM <= 10;

-- IO 等待事件关键指标解读
-- db file sequential read  → 单块读（索引扫描），avg_wait_ms > 10ms 需关注存储
-- db file scattered read  → 多块读（全表扫描），avg_wait_ms > 20ms 需关注存储
-- log file parallel write  → LGWR 写 redo 日志，avg_wait_ms > 5ms 需关注
-- direct path read         → 直接路径读（并行/排序落盘），avg_wait_ms > 20ms 需关注
-- direct path write        → 直接路径写（排序落盘），检查 PGA 大小
```

### 4.2 表空间 IO 读写分布

```sql
-- 表空间 IO 读写分布（物理读/写次数 + 吞吐量）
SELECT *
FROM (
    SELECT ts.name AS tablespace_name,
           fs.phyrds AS physical_reads,
           fs.phywrts AS physical_writes,
           ROUND(fs.phyblkrd * p.block_size / 1024 / 1024, 2) AS read_mb,
           ROUND(fs.phyblkwrt * p.block_size / 1024 / 1024, 2) AS write_mb,
           ROUND(fs.readtim / GREATEST(fs.phyrds, 1) * 10, 2) AS avg_read_ms,
           ROUND(fs.writetim / GREATEST(fs.phywrts, 1) * 10, 2) AS avg_write_ms,
           ROUND(fs.phyblkrd / GREATEST(fs.phyrds, 1), 2) AS avg_blocks_per_read
    FROM v$filestat fs
    JOIN v$tablespace ts ON fs.ts# = ts.ts#
    JOIN (SELECT value AS block_size FROM v$parameter WHERE name = 'db_block_size') p ON 1=1
    ORDER BY (fs.phyblkrd + fs.phyblkwrt) DESC
)
WHERE ROWNUM <= 10;

-- 从 AWR 历史获取表空间 IO 统计
SELECT ts.name AS tablespace_name,
       SUM(fs.phyrds) AS total_reads,
       SUM(fs.phywrts) AS total_writes,
       ROUND(SUM(fs.readtim) / GREATEST(SUM(fs.phyrds), 1) * 10, 2) AS avg_read_ms,
       ROUND(SUM(fs.writetim) / GREATEST(SUM(fs.phywrts), 1) * 10, 2) AS avg_write_ms
FROM v$filestat fs
JOIN v$tablespace ts ON fs.ts# = ts.ts#
GROUP BY ts.name
ORDER BY total_reads + total_writes DESC;
```

### 4.3 数据文件 IO 性能

```sql
-- 数据文件 IO 性能（按 IO 次数排序）
SELECT *
FROM (
    SELECT df.name AS file_name,
           SUBSTR(df.name, INSTR(df.name, '/', -1) + 1) AS short_name,
           fs.phyrds AS reads,
           fs.phywrts AS writes,
           ROUND(fs.singleblkrds / GREATEST(fs.phyrds, 1) * 100, 2) AS single_block_read_pct,
           ROUND(fs.readtim / GREATEST(fs.phyrds, 1) * 10, 2) AS avg_read_ms,
           ROUND(fs.writetim / GREATEST(fs.phywrts, 1) * 10, 2) AS avg_write_ms,
           ROUND(fs.phyblkrd / GREATEST(fs.phyrds, 1), 2) AS avg_blocks_per_read,
           ROUND(fs.singleblkrdtim / GREATEST(fs.singleblkrds, 1) * 10, 2) AS avg_single_read_ms
    FROM v$filestat fs
    JOIN v$datafile df ON fs.file# = df.file#
    ORDER BY (fs.phyblkrd + fs.phyblkwrt) DESC
)
WHERE ROWNUM <= 10;
```

### 4.4 Temp 表空间使用与排序溢出

```sql
-- Temp 表空间使用概览
SELECT tablespace_name,
       ROUND(SUM(bytes) / 1024 / 1024, 2) AS total_mb,
       ROUND(SUM(bytes_free) / 1024 / 1024, 2) AS free_mb,
       ROUND(SUM(bytes_used) / 1024 / 1024, 2) AS used_mb,
       ROUND(SUM(bytes_used) * 100.0 / SUM(bytes), 2) AS used_pct
FROM v$temp_space_header
GROUP BY tablespace_name;

-- 当前 Temp 使用详情（按会话）
SELECT s.sid,
       s.username,
       s.osuser,
       s.program,
       s.sql_id,
       tu.tablespace,
       ROUND(tu.blocks * p.block_size / 1024 / 1024, 2) AS temp_used_mb,
       s.status
FROM v$sort_usage tu
JOIN v$session s ON tu.session_addr = s.saddr
JOIN (SELECT value AS block_size FROM v$parameter WHERE name = 'db_block_size') p ON 1=1
ORDER BY temp_used_mb DESC;

-- 排序溢出统计（磁盘排序 vs 内存排序）
SELECT name,
       value
FROM v$sysstat
WHERE name IN (
    'sorts (memory)',
    'sorts (disk)',
    'sorts (rows)'
)
ORDER BY name;

-- 排序溢出率
SELECT ROUND(
    (SELECT value FROM v$sysstat WHERE name = 'sorts (disk)')
    / GREATEST((SELECT value FROM v$sysstat WHERE name = 'sorts (memory)')
              + (SELECT value FROM v$sysstat WHERE name = 'sorts (disk)'), 1)
    * 100, 2
) AS disk_sort_pct
FROM dual;
```

### 4.5 IO 诊断解读

| 状态 | 判断标准 | 解读 |
|------|---------|------|
| IO 正常 | avg_read_ms < 10ms, avg_write_ms < 5ms | 存储 IO 性能充足 |
| IO 中等 | avg_read_ms 10~20ms, avg_write_ms 5~10ms | 需关注 IO 热点，可能存在优化空间 |
| IO 瓶颈 | avg_read_ms > 20ms, IO 等待类占比 > 30% | 存储 IO 是主要瓶颈，需优化 SQL 或扩容 |
| 排序溢出 | disk_sort_pct > 5% | 排序频繁落盘，检查 PGA_AGGREGATE_TARGET |
| Temp 紧张 | used_pct > 80% | Temp 表空间不足，检查大排序/哈希操作 |
| 热文件 | 单个文件 IO 占比 > 30% | 可能存在 IO 热点，考虑数据文件分散部署 |

---

## 五、锁深度诊断（只读）

### 5.1 当前锁等待链（递归树）

```sql
-- 锁等待链递归查询（从顶层阻塞者到最底层等待者）
SELECT LEVEL AS chain_level,
       LPAD(' ', (LEVEL - 1) * 4) || s.username AS user_name,
       s.sid,
       s.serial#,
       s.status,
       s.event,
       s.seconds_in_wait,
       s.blocking_session,
       s.sql_id,
       s.sql_child_number,
       s.row_wait_obj#,
       s.row_wait_file#,
       s.row_wait_block#,
       s.row_wait_row#,
       DECODE(l.type,
           'TX', 'TX(事务锁)',
           'TM', 'TM(表锁)',
           'UL', 'UL(用户锁)',
           l.type) AS lock_type,
       DECODE(l.lmode,
           0, 'NONE', 1, 'NULL', 2, 'ROW-S(SS)',
           3, 'ROW-X(SX)', 4, 'SHARE(S)', 5, 'S/ROW-X(SSX)', 6, 'EXCLUSIVE(X)',
           TO_CHAR(l.lmode)) AS lock_held,
       DECODE(l.request,
           0, 'NONE', 1, 'NULL', 2, 'ROW-S(SS)',
           3, 'ROW-X(SX)', 4, 'SHARE(S)', 5, 'S/ROW-X(SSX)', 6, 'EXCLUSIVE(X)',
           TO_CHAR(l.request)) AS lock_requested,
       l.ctime AS lock_hold_sec
FROM v$session s
LEFT JOIN v$lock l ON s.sid = l.sid AND l.request > 0
WHERE s.sid IN (SELECT DISTINCT blocking_session FROM v$session WHERE blocking_session IS NOT NULL)
   OR s.blocking_session IS NOT NULL
START WITH s.blocking_session IS NULL
  AND s.sid IN (SELECT DISTINCT holding_session FROM dba_waiters)
CONNECT BY PRIOR s.sid = s.blocking_session
ORDER SIBLINGS BY s.sid;
```

### 5.2 阻塞会话与等待 SQL 关联

```sql
-- 阻塞者与被阻塞者 + SQL 详情
SELECT w.waiting_session AS waiter_sid,
       w.holding_session AS holder_sid,
       w.lock_type,
       DECODE(w.mode_held,
           'None',           'NONE',
           'Null',           'NULL',
           'Row-S (SS)',     'ROW-S(SS)',
           'Row-X (SX)',     'ROW-X(SX)',
           'Share',          'SHARE(S)',
           'S/Row-X (SSX)',  'S/ROW-X(SSX)',
           'Exclusive',      'EXCLUSIVE(X)',
           w.mode_held) AS mode_held,
       DECODE(w.mode_requested,
           'None',           'NONE',
           'Null',           'NULL',
           'Row-S (SS)',     'ROW-S(SS)',
           'Row-X (SX)',     'ROW-X(SX)',
           'Share',          'SHARE(S)',
           'S/Row-X (SSX)',  'S/ROW-X(SSX)',
           'Exclusive',      'EXCLUSIVE(X)',
           w.mode_requested) AS mode_requested,
       ws.username AS waiter_user,
       ws.machine AS waiter_machine,
       ws.program AS waiter_program,
       ws.event AS waiter_event,
       ws.seconds_in_wait,
       ws.sql_id AS waiter_sql_id,
       SUBSTR(wsql.sql_text, 1, 200) AS waiter_sql,
       hs.username AS holder_user,
       hs.machine AS holder_machine,
       hs.program AS holder_program,
       hs.status AS holder_status,
       hs.sql_id AS holder_sql_id,
       SUBSTR(hsql.sql_text, 1, 200) AS holder_sql
FROM dba_waiters w
JOIN v$session ws ON w.waiting_session = ws.sid
JOIN v$session hs ON w.holding_session = hs.sid
LEFT JOIN v$sql wsql ON ws.sql_id = wsql.sql_id
LEFT JOIN v$sql hsql ON hs.sql_id = hsql.sql_id
ORDER BY ws.seconds_in_wait DESC;
```

### 5.3 被锁对象详情

```sql
-- 当前被锁住的对象
SELECT lo.object_id,
       o.owner,
       o.object_name,
       o.object_type,
       o.subobject_name,
       lo.session_id,
       s.username,
       s.osuser,
       s.machine,
       s.program,
       DECODE(lo.locked_mode,
           0, 'NONE', 1, 'NULL', 2, 'ROW-S(SS)',
           3, 'ROW-X(SX)', 4, 'SHARE(S)', 5, 'S/ROW-X(SSX)', 6, 'EXCLUSIVE(X)',
           TO_CHAR(lo.locked_mode)) AS locked_mode,
       ROUND(SYSDATE - s.logon_time, 2) AS logon_hours
FROM v$locked_object lo
JOIN dba_objects o ON lo.object_id = o.object_id
JOIN v$session s ON lo.session_id = s.sid
WHERE o.owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
ORDER BY lo.session_id;
```

### 5.4 enqueue 锁类型争用分析

```sql
-- enqueue 锁类型等待统计（自实例启动以来累计）
SELECT eq_type,
       eq_name,
       total_req# AS total_requests,
       total_wait# AS total_waits,
       succ_req# AS successful_requests,
       failed_req# AS failed_requests,
       cum_wait_time AS cum_wait_ms,
       ROUND(cum_wait_time / GREATEST(total_wait#, 1), 2) AS avg_wait_ms
FROM v$enqueue_stat
WHERE total_wait# > 0
  AND eq_type IN ('TX', 'TM', 'UL', 'SQ', 'HW', 'WL', 'FB', 'TA', 'TT', 'ST', 'SS', 'CF', 'CI', 'CU', 'HW')
ORDER BY cum_wait_time DESC;

-- AWR 历史 enqueue 锁等待统计（按快照差值）
SELECT e.eq_type,
       e.eq_type || ' - ' ||
       CASE e.eq_type
           WHEN 'TX' THEN '事务锁(行级)'
           WHEN 'TM' THEN 'DML 表锁'
           WHEN 'UL' THEN '用户锁'
           WHEN 'SQ' THEN '序列锁'
           WHEN 'HW' THEN 'HWM 锁'
           ELSE '其他'
       END AS lock_desc,
       (e.total_wait# - b.total_wait#) AS delta_waits,
       ROUND((e.cum_wait_time - b.cum_wait_time) / GREATEST((e.total_wait# - b.total_wait#), 1), 2) AS avg_wait_ms
FROM dba_hist_enqueue_stat e
JOIN dba_hist_enqueue_stat b
  ON e.eq_type = b.eq_type
 AND b.snap_id = &snap_id_begin
WHERE e.snap_id = &snap_id_end
  AND (e.total_wait# - b.total_wait#) > 0
ORDER BY (e.cum_wait_time - b.cum_wait_time) DESC;
```

### 5.5 热块冲突与 ITL 等待

```sql
-- 段级 ITL 等待统计
SELECT owner,
       object_name,
       subobject_name,
       value AS itl_waits
FROM v$segment_statistics
WHERE statistic_name = 'ITL waits'
  AND value > 0
ORDER BY value DESC;

-- 段级缓冲忙等待（Buffer Busy Waits）
SELECT owner,
       object_name,
       subobject_name,
       value AS buffer_busy_waits
FROM v$segment_statistics
WHERE statistic_name = 'buffer busy waits'
  AND value > 0
ORDER BY value DESC;

-- 段级行锁等待
SELECT owner,
       object_name,
       subobject_name,
       value AS row_lock_waits
FROM v$segment_statistics
WHERE statistic_name = 'row lock waits'
  AND value > 0
ORDER BY value DESC;
```

### 5.6 锁诊断解读

| 状态 | 判断标准 | 解读 |
|------|---------|------|
| 锁正常 | blocked_sessions = 0, enqueue avg_wait < 10ms | 锁争用处于正常水平 |
| 锁中等 | blocked_sessions 1~10, TX 锁 avg_wait 10~50ms | 偶发锁等待，需关注事务设计 |
| 锁瓶颈 | blocked_sessions > 10, 锁等待链深度 > 3 | 严重锁争用，存在死锁风险 |
| TM 锁异常 | TM 锁等待占比高 | 外键索引缺失 / DDL 冲突 |
| ITL 不足 | ITL waits > 0 | 需增大 INITRANS |
| 热块冲突 | buffer_busy_waits 集中在少数段 | 需优化热块 SQL 或考虑分区 |

---

## 六、AWR 历史综合诊断（只读）

### 6.1 快照范围确认

```sql
-- 查看可用 AWR 快照范围
SELECT snap_id,
       TO_CHAR(begin_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS begin_time,
       TO_CHAR(end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS end_time,
       ROUND((CAST(end_interval_time AS DATE) - CAST(begin_interval_time AS DATE)) * 24 * 60, 1) AS duration_min
FROM dba_hist_snapshot
WHERE begin_interval_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
  AND instance_number = (SELECT instance_number FROM v$instance)
ORDER BY snap_id DESC;
```

### 6.2 AWR 负载概要（CPU + IO）

```sql
-- 负载概要：DB Time、CPU、Redo、读写、解析、事务
SELECT ROUND(SUM(e.value - b.value) / 1000000, 2) AS db_time_sec,
       ROUND(SUM(CASE WHEN e.stat_name = 'DB CPU' THEN e.value - b.value ELSE 0 END) / 1000000, 2) AS db_cpu_sec,
       ROUND(SUM(CASE WHEN e.stat_name = 'redo size' THEN e.value - b.value ELSE 0 END) / 1024 / 1024, 2) AS redo_size_mb,
       ROUND(SUM(CASE WHEN e.stat_name = 'physical read total bytes' THEN e.value - b.value ELSE 0 END) / 1024 / 1024, 2) AS physical_read_mb,
       ROUND(SUM(CASE WHEN e.stat_name = 'physical write total bytes' THEN e.value - b.value ELSE 0 END) / 1024 / 1024, 2) AS physical_write_mb,
       SUM(CASE WHEN e.stat_name = 'execute count' THEN e.value - b.value ELSE 0 END) AS executes,
       SUM(CASE WHEN e.stat_name = 'user commits' THEN e.value - b.value ELSE 0 END) AS user_commits,
       SUM(CASE WHEN e.stat_name = 'user rollbacks' THEN e.value - b.value ELSE 0 END) AS user_rollbacks
FROM dba_hist_sys_time_model e
JOIN dba_hist_sys_time_model b
  ON e.stat_name = b.stat_name
 AND b.snap_id = &snap_id_begin
WHERE e.snap_id = &snap_id_end
  AND e.stat_name IN (
    'DB time', 'DB CPU', 'redo size', 'physical read total bytes',
    'physical write total bytes', 'execute count', 'user commits', 'user rollbacks'
  );
```

### 6.3 锁等待历史趋势（ASH 采样）

```sql
-- 从 ASH 获取锁等待事件历史趋势
SELECT TO_CHAR(sample_time, 'YYYY-MM-DD HH24:MI') AS sample_minute,
       COUNT(*) AS lock_wait_samples,
       COUNT(DISTINCT session_id) AS blocked_sessions,
       COUNT(DISTINCT blocking_session) AS blocking_sessions
FROM dba_hist_active_sess_history
WHERE sample_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
  AND event IN (
    'enq: TX - row lock contention',
    'enq: TX - index contention',
    'enq: TX - allocate ITL entry',
    'enq: TM - contention',
    'enq: UL - contention',
    'buffer busy waits',
    'latch: cache buffers chains'
  )
GROUP BY TO_CHAR(sample_time, 'YYYY-MM-DD HH24:MI')
ORDER BY 1 DESC;

-- 锁等待涉及的 TOP 对象
SELECT o.owner,
       o.object_name,
       o.object_type,
       COUNT(*) AS lock_wait_samples
FROM dba_hist_active_sess_history ash
JOIN dba_objects o ON ash.current_obj# = o.object_id
WHERE ash.sample_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
  AND ash.event IN (
    'enq: TX - row lock contention',
    'enq: TX - index contention',
    'enq: TM - contention',
    'buffer busy waits'
  )
  AND ash.current_obj# > 0
GROUP BY o.owner, o.object_name, o.object_type
ORDER BY lock_wait_samples DESC;
```

---

## 七、锁等待与 CPU/IO 关联分析（只读）

```sql
-- 锁等待会话的 CPU 消耗（被阻塞时的 CPU 浪费）
SELECT s.sid,
       s.username,
       s.event,
       s.seconds_in_wait,
       s.blocking_session,
       s.sql_id,
       ROUND(ss.value / 100, 2) AS cpu_used_sec
FROM v$session s
JOIN v$sesstat ss ON s.sid = ss.sid
JOIN v$statname sn ON ss.statistic# = sn.statistic#
WHERE s.blocking_session IS NOT NULL
  AND sn.name = 'CPU used by this session'
  AND ss.value > 0
ORDER BY cpu_used_sec DESC;

-- IO 等待与锁等待并发会话数
SELECT event,
       COUNT(*) AS session_count,
       ROUND(AVG(seconds_in_wait), 1) AS avg_wait_sec,
       MAX(seconds_in_wait) AS max_wait_sec
FROM v$session
WHERE wait_class IN ('User I/O', 'Concurrency', 'Application')
  AND status = 'ACTIVE'
  AND type != 'BACKGROUND'
GROUP BY event
ORDER BY session_count DESC;
```

---

## 八、优化方向参考（只诊断，不执行）

### CPU 优化方向

| 问题 | 现象 | 建议方向 |
|------|------|---------|
| SQL CPU 高 | 少数 SQL 占总 CPU > 20% | 检查执行计划、优化索引、SQL 改写 |
| 硬解析 | hard parse elapsed time 占比 > 5% | 使用绑定变量、增大 shared_pool |
| 闩锁争用 | latch: cache buffers chains / shared pool 占比高 | 热块优化、增大 shared_pool |
| OS CPU 满载 | OS CPU Idle < 5% | 评估扩容或降低 DB 负载 |

### IO 优化方向

| 问题 | 现象 | 建议方向 |
|------|------|---------|
| 单块读慢 | db file sequential read avg_wait > 10ms | 检查存储 IO 性能、优化索引 |
| 全表扫描多 | db file scattered read 占比高 | 检查缺失索引、优化 SQL 谓词 |
| 日志写慢 | log file parallel write avg_wait > 5ms | 优化 redo 日志磁盘 IO、增大日志组 |
| 排序溢出 | disk_sort_pct > 5% | 增大 PGA_AGGREGATE_TARGET |
| Temp 紧张 | Temp used_pct > 80% | 增大 Temp 表空间、优化大排序 SQL |
| 热文件 | 单个文件 IO 占比 > 30% | 数据文件分散部署、条带化 |

### 锁优化方向

| 问题 | 现象 | 建议方向 |
|------|------|---------|
| TX 行锁 | enq: TX - row lock contention 占比高 | 缩短事务、统一加锁顺序 |
| TM 表锁 | enq: TM - contention 占比高 | 外键列补索引、避免 DDL 并发 |
| ITL 不足 | ITL waits > 0 | 增大 INITRANS |
| 热块冲突 | buffer busy waits 集中在少数段 | Hash 分区、反转键索引 |
| 序列锁 | enq: SQ - contention | 增大序列 CACHE、使用 NOORDER |

---

## 异常处理
- 单条查询失败不影响整体，标记该维度异常后继续其余查询。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- AWR 快照不存在时，回退到 v$ 动态视图实时查询。
- 部分查询（如 v$osstat）在权限不足时可能返回空，标记"权限不足，跳过 OS 统计"。
- 本技能仅做只读诊断，不执行任何 DDL/DML，单次执行耗时 ≤10s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. **宏观诊断概览**：OS CPU 负载 + DB CPU 占比 + IO 等待类占比 + 实时锁等待会话数
  2. **CPU 诊断**：时间模型分布 + TOP CPU SQL + CPU 相关等待事件
  3. **IO 诊断**：IO 等待事件 TOP N + 表空间/数据文件 IO 热点 + Temp 使用与排序溢出率
  4. **锁诊断**：当前锁等待链 + 阻塞者/被阻塞者 SQL + enqueue 锁类型争用 + 热块/ITL 等待
  5. **AWR 历史趋势**：负载概要 + 锁等待历史变化
  6. **综合诊断结论**：三维度瓶颈排序（主瓶颈 > 次瓶颈）+ 关联分析 + 优化方向建议