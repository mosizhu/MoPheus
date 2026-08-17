---
name: "db-oracle-monitor-anomaly"
description: "Oracle 历史指标异常检测技能。核心能力：(1) CPU 异常检测：基于 AWR 历史快照（DBA_HIST_SYSMETRIC_SUMMARY），通过 Z-Score / 移动平均偏离度检测 Host CPU Utilization、Database CPU Time Ratio 等指标的异常点；(2) IO 异常检测：分析 AWR 历史 IO 等待事件（db file sequential/scattered read、log file parallel write 等）的 avg_wait_ms 波动，识别 IO 延迟突增异常；(3) 等待事件异常检测：监测系统级等待事件累计等待时间突增，定位异常等待类（User I/O / System I/O / Concurrency / Configuration 等）；(4) 会话数异常检测：检测历史活跃会话数、总会话数的突增/突降异常；(5) SQL 性能劣化检测：基于 AWR SQL 统计（DBA_HIST_SQLSTAT），检测 SQL 平均执行时间、buffer gets 等指标的突变劣化。适用场景：历史性能异常回溯分析、突增/突降根因定位、容量规划基线偏离检测、周期性性能巡检。功能限制：仅做只读查询与统计分析，不 KILL 会话、不修改参数、不执行 DDL/DML。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "anomaly_scope"
    type: "string"
    required: false
    default: "all"
    desc: "异常检测范围：all（全部）/ cpu（仅 CPU）/ io（仅 IO）/ wait_event（仅等待事件）/ session（仅会话数）/ sql（仅 SQL 性能劣化）"
  - name: "time_range_hours"
    type: "integer"
    required: false
    default: 168
    desc: "历史数据回溯时间范围（小时），默认 168（最近 7 天）"
  - name: "anomaly_threshold"
    type: "number"
    required: false
    default: 2.0
    desc: "异常判定 Z-Score 阈值，默认 2.0（即偏离均值 2 个标准差以上视为异常），值越小越敏感"
  - name: "top_n"
    type: "integer"
    required: false
    default: 20
    desc: "返回 TOP N 条异常结果，默认 20"
  - name: "snap_id_begin"
    type: "integer"
    required: false
    default: 0
    desc: "AWR 历史查询起始快照 ID（为 0 则自动按 time_range_hours 选择）"
  - name: "snap_id_end"
    type: "integer"
    required: false
    default: 0
    desc: "AWR 历史查询结束快照 ID（为 0 则自动选择最近快照）"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 历史指标异常检测

本技能为只读分析技能，基于 AWR 历史快照（DBA_HIST_SYSMETRIC_SUMMARY、DBA_HIST_SYSMETRIC_HISTORY、DBA_HIST_SYSTEM_EVENT、DBA_HIST_SQLSTAT 等），使用统计学方法（Z-Score / 移动平均偏离度）对 Oracle 历史性能指标进行异常点检测，识别 CPU、IO、等待事件、会话数、SQL 性能等维度的突增/突降异常，产出结构化异常报告并给出排查建议（不执行任何变更）。

---

## 核心能力

### CPU 异常检测
- 基于 DBA_HIST_SYSMETRIC_SUMMARY 分析 Host CPU Utilization、Database CPU Time Ratio 的历史趋势
- 使用 Z-Score / 移动平均偏离度检测 CPU 使用率突增/突降异常点
- 关联异常时间点的 TOP SQL 与等待事件，辅助根因定位

### IO 异常检测
- 基于 DBA_HIST_SYSTEM_EVENT 分析 IO 相关等待事件的 avg_wait_ms 波动
- 检测 db file sequential read、db file scattered read、log file parallel write 等 IO 延迟突增
- 关联异常时间点的表空间 IO 分布，定位 IO 热点

### 等待事件异常检测
- 基于 DBA_HIST_SYSTEM_EVENT 按等待类（User I/O / System I/O / Concurrency / Configuration / Cluster 等）聚合等待时间
- 检测各等待类累计等待时间的突增异常
- 识别异常等待类中的 TOP 等待事件

### 会话数异常检测
- 基于 DBA_HIST_SYSMETRIC_SUMMARY 分析活跃会话数、总会话数的历史趋势
- 检测连接风暴（突增）、连接泄漏（持续高位）、连接断开（突降）异常
- 关联异常时间点的会话来源分布

### SQL 性能劣化检测
- 基于 DBA_HIST_SQLSTAT 按快照间隔计算 SQL 的平均执行时间、buffer gets、disk reads 等指标
- 对比历史基线，检测单条 SQL 的执行计划劣化/性能突变
- 输出劣化 SQL 列表及劣化程度排名

## 适用场景
- 历史性能异常回溯分析（"昨天下午 3 点数据库为什么慢"）
- CPU/IO/连接数突增突降的根因定位
- 容量规划基线偏离检测
- 周期性性能巡检，自动发现异常时间点
- SQL 执行计划劣化的历史检测
- 大促/变更前后的性能对比异常检测

## 功能限制 / 安全边界
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改实例参数（不执行 ALTER SYSTEM SET）
- 不调整表/索引存储参数（不执行 ALTER TABLE/INDEX）
- 不执行 SQL Profile/SPM 操作
- 不调用其它 Skill、不自动修复、仅按需手动触发
- 单次执行耗时 ≤15s（大时间范围回溯时可适当放宽），无第三方依赖、无外部资源引用

---

## 一、推理框架：异常检测链

```
用户请求历史指标异常检测（指定时间范围 + 指标范围）
    |
    v
[1] 参数解析：确定 anomaly_scope（all/cpu/io/wait_event/session/sql）
    | 为空 → 全量检测五个维度
    | 指定类型 → 仅检测对应维度
    v
[2] 快照范围确认
    | 查询 DBA_HIST_SNAPSHOT 确定可用快照范围
    | 若 snap_id_begin/end 为 0，按 time_range_hours 自动选择
    v
[3] CPU 异常检测
    | 从 DBA_HIST_SYSMETRIC_SUMMARY 提取 CPU 指标序列
    | 计算历史均值 μ、标准差 σ
    | 标记 |value - μ| > anomaly_threshold * σ 的时间点为异常
    | 输出异常时间点 + 偏离度 + 关联快照 ID
    v
[4] IO 异常检测
    | 从 DBA_HIST_SYSTEM_EVENT 按快照提取 IO 等待事件
    | 计算各事件 avg_wait_ms 的 Z-Score
    | 标记 IO 延迟突增的异常快照
    v
[5] 等待事件异常检测
    | 按等待类聚合 DBA_HIST_SYSTEM_EVENT 的等待时间
    | 检测各等待类累计等待时间的突增异常
    | 深入异常等待类，输出 TOP 等待事件
    v
[6] 会话数异常检测
    | 从 DBA_HIST_SYSMETRIC_SUMMARY 提取会话数指标
    | 检测活跃会话数、总会话数的突增/突降异常
    v
[7] SQL 性能劣化检测
    | 从 DBA_HIST_SQLSTAT 按快照间隔计算 SQL 指标
    | 对比各快照的 avg_elapsed_sec、avg_buffer_gets
    | 检测单条 SQL 性能突变（劣化 > 2x 或 > 3σ）
    v
[8] 综合异常报告
    | 按时间线汇总所有维度异常
    | 关联分析（同一时间点多维度异常 → 根因推断）
    | 异常严重程度排序与排查建议
```

---

## 二、快照范围确认（只读）

```sql
-- 查看可用 AWR 快照范围
SELECT snap_id,
       TO_CHAR(begin_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS begin_time,
       TO_CHAR(end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS end_time,
       ROUND((CAST(end_interval_time AS DATE) - CAST(begin_interval_time AS DATE)) * 24 * 60, 1) AS duration_min,
       instance_number,
       startup_time
FROM dba_hist_snapshot
WHERE begin_interval_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
  AND instance_number = (SELECT instance_number FROM v$instance)
ORDER BY snap_id;

-- 确认快照总数
SELECT COUNT(*) AS total_snapshots,
       MIN(snap_id) AS min_snap_id,
       MAX(snap_id) AS max_snap_id,
       MIN(begin_interval_time) AS earliest_time,
       MAX(end_interval_time) AS latest_time
FROM dba_hist_snapshot
WHERE begin_interval_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
  AND instance_number = (SELECT instance_number FROM v$instance);
```

---

## 三、CPU 异常检测（只读）

### 3.1 CPU 指标序列采集

```sql
-- 从 DBA_HIST_SYSMETRIC_SUMMARY 提取 CPU 指标历史序列
SELECT s.snap_id,
       TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
       MAX(CASE WHEN m.metric_name = 'Host CPU Utilization (%)' THEN m.average END) AS host_cpu_avg,
       MAX(CASE WHEN m.metric_name = 'Host CPU Utilization (%)' THEN m.maxval END) AS host_cpu_max,
       MAX(CASE WHEN m.metric_name = 'Database CPU Time Ratio' THEN m.average END) AS db_cpu_ratio_avg,
       MAX(CASE WHEN m.metric_name = 'Database CPU Time Ratio' THEN m.maxval END) AS db_cpu_ratio_max,
       MAX(CASE WHEN m.metric_name = 'OS Load' THEN m.average END) AS os_load_avg,
       MAX(CASE WHEN m.metric_name = 'OS Load' THEN m.maxval END) AS os_load_max
FROM dba_hist_snapshot s
JOIN dba_hist_sysmetric_summary m
  ON s.snap_id = m.snap_id
 AND s.instance_number = m.instance_number
WHERE s.begin_interval_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
  AND s.instance_number = (SELECT instance_number FROM v$instance)
  AND m.metric_name IN (
    'Host CPU Utilization (%)',
    'Database CPU Time Ratio',
    'OS Load'
  )
GROUP BY s.snap_id, s.end_interval_time
ORDER BY s.snap_id;
```

### 3.2 CPU 异常判定（Z-Score 方法）

> 在 SQL 层面无法直接完成 Z-Score 计算时，采用两步法：
> 1. 先采集全量序列到应用层
> 2. 在应用层计算均值 μ 和标准差 σ，标记异常点

```sql
-- 获取 CPU 指标序列的统计摘要（均值 + 标准差）
SELECT metric_name,
       ROUND(AVG(average), 2) AS mean_value,
       ROUND(STDDEV(average), 2) AS stddev_value,
       ROUND(MIN(average), 2) AS min_value,
       ROUND(MAX(average), 2) AS max_value,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY average), 2) AS median_value,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY average), 2) AS p95_value,
       COUNT(*) AS sample_count
FROM dba_hist_sysmetric_summary
WHERE snap_id BETWEEN &snap_id_begin AND &snap_id_end
  AND metric_name IN (
    'Host CPU Utilization (%)',
    'Database CPU Time Ratio',
    'OS Load'
  )
  AND instance_number = (SELECT instance_number FROM v$instance)
GROUP BY metric_name;
```

### 3.3 CPU 异常点输出

```sql
-- 基于 Z-Score > threshold 标记 CPU 异常快照
WITH cpu_stats AS (
    SELECT metric_name,
           AVG(average) AS mean_val,
           STDDEV(average) AS stddev_val
    FROM dba_hist_sysmetric_summary
    WHERE snap_id BETWEEN &snap_id_begin AND &snap_id_end
      AND metric_name IN (
        'Host CPU Utilization (%)',
        'Database CPU Time Ratio',
        'OS Load'
      )
      AND instance_number = (SELECT instance_number FROM v$instance)
    GROUP BY metric_name
),
cpu_series AS (
    SELECT s.snap_id,
           TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
           m.metric_name,
           m.average AS metric_value,
           cs.mean_val,
           cs.stddev_val,
           CASE WHEN cs.stddev_val > 0
                THEN ROUND(ABS(m.average - cs.mean_val) / cs.stddev_val, 2)
                ELSE 0
           END AS z_score
    FROM dba_hist_snapshot s
    JOIN dba_hist_sysmetric_summary m
      ON s.snap_id = m.snap_id
     AND s.instance_number = m.instance_number
    JOIN cpu_stats cs ON m.metric_name = cs.metric_name
    WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
      AND s.instance_number = (SELECT instance_number FROM v$instance)
      AND m.metric_name IN (
        'Host CPU Utilization (%)',
        'Database CPU Time Ratio',
        'OS Load'
      )
)
SELECT *
FROM (
    SELECT snap_id,
           snapshot_time,
           metric_name,
           metric_value,
           mean_val,
           stddev_val,
           z_score,
           CASE WHEN metric_value > mean_val THEN 'HIGH' ELSE 'LOW' END AS anomaly_direction,
           CASE WHEN z_score >= 3.0 THEN '严重'
                WHEN z_score >= 2.0 THEN '警告'
                ELSE '正常'
           END AS anomaly_level
    FROM cpu_series
    WHERE z_score >= &anomaly_threshold
    ORDER BY z_score DESC
)
WHERE ROWNUM <= &top_n;
```

### 3.4 CPU 异常关联分析

```sql
-- 对异常快照关联 TOP SQL（按 CPU 时间）
SELECT s.snap_id,
       TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
       sql.sql_id,
       SUBSTR(st.sql_text, 1, 200) AS sql_text,
       ROUND(sql.cpu_time_delta / 1000000, 2) AS cpu_sec,
       sql.executions_delta AS executions,
       ROUND(sql.cpu_time_delta / GREATEST(sql.executions_delta, 1) / 1000000, 4) AS avg_cpu_sec
FROM dba_hist_snapshot s
JOIN dba_hist_sqlstat sql
  ON s.snap_id = sql.snap_id
 AND s.instance_number = sql.instance_number
JOIN dba_hist_sqltext st
  ON sql.sql_id = st.sql_id
WHERE s.snap_id IN (&anomaly_snap_ids)
  AND sql.cpu_time_delta > 0
ORDER BY sql.cpu_time_delta DESC;
```

### 3.5 CPU 异常判定基线

| 指标 | 正常 Z-Score | 警告 Z-Score | 严重 Z-Score |
|------|------------|-------------|-------------|
| Host CPU Utilization | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| Database CPU Time Ratio | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| OS Load | < 2.0 | 2.0 ~ 3.0 | > 3.0 |

---

## 四、IO 异常检测（只读）

### 4.1 IO 等待事件序列采集

```sql
-- 从 DBA_HIST_SYSTEM_EVENT 提取 IO 等待事件历史序列
SELECT s.snap_id,
       TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
       e.event_name,
       e.wait_class,
       (e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) / 1000 AS delta_wait_ms,
       (e.total_waits - COALESCE(prev.total_waits, 0)) AS delta_waits,
       CASE WHEN (e.total_waits - COALESCE(prev.total_waits, 0)) > 0
            THEN ROUND((e.time_waited_micro - COALESCE(prev.time_waited_micro, 0))
                       / (e.total_waits - COALESCE(prev.total_waits, 0)) / 1000, 2)
            ELSE 0
       END AS avg_wait_ms
FROM dba_hist_snapshot s
JOIN dba_hist_system_event e
  ON s.snap_id = e.snap_id
 AND s.instance_number = e.instance_number
LEFT JOIN dba_hist_system_event prev
  ON e.event_name = prev.event_name
 AND e.instance_number = prev.instance_number
 AND prev.snap_id = s.snap_id - 1
WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
  AND s.instance_number = (SELECT instance_number FROM v$instance)
  AND e.wait_class IN ('User I/O', 'System I/O')
  AND e.event_name IN (
    'db file sequential read',
    'db file scattered read',
    'log file parallel write',
    'direct path read',
    'direct path write',
    'log file sync',
    'log file sequential read',
    'control file parallel write',
    'db file parallel read',
    'db file parallel write'
  )
ORDER BY s.snap_id, delta_wait_ms DESC;
```

### 4.2 IO 异常判定

```sql
-- 获取 IO 等待事件 avg_wait_ms 的统计摘要
WITH io_delta AS (
    SELECT s.snap_id,
           e.event_name,
           (e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) / 1000 AS delta_wait_ms,
           (e.total_waits - COALESCE(prev.total_waits, 0)) AS delta_waits,
           CASE WHEN (e.total_waits - COALESCE(prev.total_waits, 0)) > 0
                THEN ROUND((e.time_waited_micro - COALESCE(prev.time_waited_micro, 0))
                           / (e.total_waits - COALESCE(prev.total_waits, 0)) / 1000, 2)
                ELSE 0
           END AS avg_wait_ms
    FROM dba_hist_snapshot s
    JOIN dba_hist_system_event e
      ON s.snap_id = e.snap_id
     AND s.instance_number = e.instance_number
    LEFT JOIN dba_hist_system_event prev
      ON e.event_name = prev.event_name
     AND e.instance_number = prev.instance_number
     AND prev.snap_id = s.snap_id - 1
    WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
      AND s.instance_number = (SELECT instance_number FROM v$instance)
      AND e.wait_class IN ('User I/O', 'System I/O')
      AND e.event_name IN (
        'db file sequential read',
        'db file scattered read',
        'log file parallel write',
        'direct path read',
        'direct path write',
        'log file sync'
      )
)
SELECT event_name,
       ROUND(AVG(avg_wait_ms), 2) AS mean_avg_wait_ms,
       ROUND(STDDEV(avg_wait_ms), 2) AS stddev_avg_wait_ms,
       ROUND(MIN(avg_wait_ms), 2) AS min_avg_wait_ms,
       ROUND(MAX(avg_wait_ms), 2) AS max_avg_wait_ms,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avg_wait_ms), 2) AS p95_avg_wait_ms,
       COUNT(*) AS sample_count
FROM io_delta
WHERE avg_wait_ms > 0
GROUP BY event_name
ORDER BY mean_avg_wait_ms DESC;
```

### 4.3 IO 异常点输出

```sql
-- 基于 Z-Score 标记 IO 延迟异常快照
WITH io_delta AS (
    SELECT s.snap_id,
           TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
           e.event_name,
           (e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) / 1000 AS delta_wait_ms,
           (e.total_waits - COALESCE(prev.total_waits, 0)) AS delta_waits,
           CASE WHEN (e.total_waits - COALESCE(prev.total_waits, 0)) > 0
                THEN ROUND((e.time_waited_micro - COALESCE(prev.time_waited_micro, 0))
                           / (e.total_waits - COALESCE(prev.total_waits, 0)) / 1000, 2)
                ELSE 0
           END AS avg_wait_ms
    FROM dba_hist_snapshot s
    JOIN dba_hist_system_event e
      ON s.snap_id = e.snap_id
     AND s.instance_number = e.instance_number
    LEFT JOIN dba_hist_system_event prev
      ON e.event_name = prev.event_name
     AND e.instance_number = prev.instance_number
     AND prev.snap_id = s.snap_id - 1
    WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
      AND s.instance_number = (SELECT instance_number FROM v$instance)
      AND e.wait_class IN ('User I/O', 'System I/O')
),
io_stats AS (
    SELECT event_name,
           AVG(avg_wait_ms) AS mean_val,
           STDDEV(avg_wait_ms) AS stddev_val
    FROM io_delta
    WHERE avg_wait_ms > 0
    GROUP BY event_name
)
SELECT *
FROM (
    SELECT d.snap_id,
           d.snapshot_time,
           d.event_name,
           d.avg_wait_ms,
           d.delta_waits,
           s.mean_val,
           s.stddev_val,
           ROUND(ABS(d.avg_wait_ms - s.mean_val) / GREATEST(s.stddev_val, 0.01), 2) AS z_score,
           CASE WHEN d.avg_wait_ms > s.mean_val THEN 'HIGH' ELSE 'LOW' END AS anomaly_direction,
           CASE WHEN ABS(d.avg_wait_ms - s.mean_val) / GREATEST(s.stddev_val, 0.01) >= 3.0 THEN '严重'
                WHEN ABS(d.avg_wait_ms - s.mean_val) / GREATEST(s.stddev_val, 0.01) >= 2.0 THEN '警告'
                ELSE '正常'
           END AS anomaly_level
    FROM io_delta d
    JOIN io_stats s ON d.event_name = s.event_name
    WHERE d.avg_wait_ms > 0
      AND ABS(d.avg_wait_ms - s.mean_val) / GREATEST(s.stddev_val, 0.01) >= &anomaly_threshold
    ORDER BY z_score DESC
)
WHERE ROWNUM <= &top_n;
```

### 4.4 IO 异常判定基线

| 指标 | 正常 Z-Score | 警告 Z-Score | 严重 Z-Score |
|------|------------|-------------|-------------|
| db file sequential read avg_wait_ms | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| db file scattered read avg_wait_ms | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| log file parallel write avg_wait_ms | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| log file sync avg_wait_ms | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| direct path read/write avg_wait_ms | < 2.0 | 2.0 ~ 3.0 | > 3.0 |

---

## 五、等待事件异常检测（只读）

### 5.1 等待类聚合序列

```sql
-- 按等待类聚合 DBA_HIST_SYSTEM_EVENT 的等待时间增量
SELECT s.snap_id,
       TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
       e.wait_class,
       ROUND(SUM(e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) / 1000000, 2) AS delta_wait_sec
FROM dba_hist_snapshot s
JOIN dba_hist_system_event e
  ON s.snap_id = e.snap_id
 AND s.instance_number = e.instance_number
LEFT JOIN dba_hist_system_event prev
  ON e.event_name = prev.event_name
 AND e.instance_number = prev.instance_number
 AND prev.snap_id = s.snap_id - 1
WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
  AND s.instance_number = (SELECT instance_number FROM v$instance)
  AND e.wait_class != 'Idle'
  AND (e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) > 0
GROUP BY s.snap_id, s.end_interval_time, e.wait_class
ORDER BY s.snap_id, delta_wait_sec DESC;
```

### 5.2 等待类异常判定

```sql
-- 等待类 Z-Score 异常检测
WITH wait_class_delta AS (
    SELECT s.snap_id,
           TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
           e.wait_class,
           ROUND(SUM(e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) / 1000000, 2) AS delta_wait_sec
    FROM dba_hist_snapshot s
    JOIN dba_hist_system_event e
      ON s.snap_id = e.snap_id
     AND s.instance_number = e.instance_number
    LEFT JOIN dba_hist_system_event prev
      ON e.event_name = prev.event_name
     AND e.instance_number = prev.instance_number
     AND prev.snap_id = s.snap_id - 1
    WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
      AND s.instance_number = (SELECT instance_number FROM v$instance)
      AND e.wait_class != 'Idle'
      AND (e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) > 0
    GROUP BY s.snap_id, s.end_interval_time, e.wait_class
),
wc_stats AS (
    SELECT wait_class,
           AVG(delta_wait_sec) AS mean_val,
           STDDEV(delta_wait_sec) AS stddev_val
    FROM wait_class_delta
    GROUP BY wait_class
)
SELECT *
FROM (
    SELECT d.snap_id,
           d.snapshot_time,
           d.wait_class,
           d.delta_wait_sec,
           s.mean_val,
           s.stddev_val,
           ROUND((d.delta_wait_sec - s.mean_val) / GREATEST(s.stddev_val, 0.01), 2) AS z_score,
           CASE WHEN (d.delta_wait_sec - s.mean_val) / GREATEST(s.stddev_val, 0.01) >= 3.0 THEN '严重'
                WHEN (d.delta_wait_sec - s.mean_val) / GREATEST(s.stddev_val, 0.01) >= 2.0 THEN '警告'
                ELSE '正常'
           END AS anomaly_level
    FROM wait_class_delta d
    JOIN wc_stats s ON d.wait_class = s.wait_class
    WHERE (d.delta_wait_sec - s.mean_val) / GREATEST(s.stddev_val, 0.01) >= &anomaly_threshold
    ORDER BY z_score DESC
)
WHERE ROWNUM <= &top_n;
```

### 5.3 异常等待类深入分析

```sql
-- 对异常快照的等待类，深入查看 TOP 等待事件
SELECT s.snap_id,
       TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
       e.event_name,
       e.wait_class,
       ROUND((e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) / 1000000, 2) AS delta_wait_sec,
       (e.total_waits - COALESCE(prev.total_waits, 0)) AS delta_waits,
       CASE WHEN (e.total_waits - COALESCE(prev.total_waits, 0)) > 0
            THEN ROUND((e.time_waited_micro - COALESCE(prev.time_waited_micro, 0))
                       / (e.total_waits - COALESCE(prev.total_waits, 0)) / 1000, 2)
            ELSE 0
       END AS avg_wait_ms
FROM dba_hist_snapshot s
JOIN dba_hist_system_event e
  ON s.snap_id = e.snap_id
 AND s.instance_number = e.instance_number
LEFT JOIN dba_hist_system_event prev
  ON e.event_name = prev.event_name
 AND e.instance_number = prev.instance_number
 AND prev.snap_id = s.snap_id - 1
WHERE s.snap_id IN (&anomaly_snap_ids)
  AND e.wait_class IN (&anomaly_wait_classes)
  AND (e.time_waited_micro - COALESCE(prev.time_waited_micro, 0)) > 0
ORDER BY delta_wait_sec DESC;
```

### 5.4 等待事件异常判定基线

| 指标 | 正常 Z-Score | 警告 Z-Score | 严重 Z-Score |
|------|------------|-------------|-------------|
| User I/O 等待时间 | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| System I/O 等待时间 | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| Concurrency 等待时间 | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| Configuration 等待时间 | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| Cluster 等待时间 | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| Application 等待时间 | < 2.0 | 2.0 ~ 3.0 | > 3.0 |

---

## 六、会话数异常检测（只读）

### 6.1 会话数序列采集

```sql
-- 从 DBA_HIST_SYSMETRIC_SUMMARY 提取会话数指标历史序列
SELECT s.snap_id,
       TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
       MAX(CASE WHEN m.metric_name = 'Current Logons Count' THEN m.average END) AS current_logons,
       MAX(CASE WHEN m.metric_name = 'Current Logons Count' THEN m.maxval END) AS current_logons_max,
       MAX(CASE WHEN m.metric_name = 'Session Count' THEN m.average END) AS session_count,
       MAX(CASE WHEN m.metric_name = 'Session Count' THEN m.maxval END) AS session_count_max,
       MAX(CASE WHEN m.metric_name = 'User Transaction Count' THEN m.average END) AS user_transaction_count
FROM dba_hist_snapshot s
JOIN dba_hist_sysmetric_summary m
  ON s.snap_id = m.snap_id
 AND s.instance_number = m.instance_number
WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
  AND s.instance_number = (SELECT instance_number FROM v$instance)
  AND m.metric_name IN (
    'Current Logons Count',
    'Session Count',
    'User Transaction Count'
  )
GROUP BY s.snap_id, s.end_interval_time
ORDER BY s.snap_id;
```

### 6.2 会话数异常判定

```sql
-- 会话数 Z-Score 异常检测
WITH session_series AS (
    SELECT s.snap_id,
           TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
           MAX(CASE WHEN m.metric_name = 'Session Count' THEN m.average END) AS session_count,
           MAX(CASE WHEN m.metric_name = 'Current Logons Count' THEN m.average END) AS current_logons
    FROM dba_hist_snapshot s
    JOIN dba_hist_sysmetric_summary m
      ON s.snap_id = m.snap_id
     AND s.instance_number = m.instance_number
    WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
      AND s.instance_number = (SELECT instance_number FROM v$instance)
      AND m.metric_name IN ('Session Count', 'Current Logons Count')
    GROUP BY s.snap_id, s.end_interval_time
),
session_stats AS (
    SELECT AVG(session_count) AS mean_session,
           STDDEV(session_count) AS stddev_session,
           AVG(current_logons) AS mean_logons,
           STDDEV(current_logons) AS stddev_logons
    FROM session_series
)
SELECT *
FROM (
    SELECT ss.snap_id,
           ss.snapshot_time,
           'Session Count' AS metric_name,
           ss.session_count AS metric_value,
           st.mean_session AS mean_val,
           st.stddev_session AS stddev_val,
           ROUND(ABS(ss.session_count - st.mean_session) / GREATEST(st.stddev_session, 0.01), 2) AS z_score,
           CASE WHEN ss.session_count > st.mean_session THEN 'HIGH' ELSE 'LOW' END AS anomaly_direction,
           CASE WHEN ABS(ss.session_count - st.mean_session) / GREATEST(st.stddev_session, 0.01) >= 3.0 THEN '严重'
                WHEN ABS(ss.session_count - st.mean_session) / GREATEST(st.stddev_session, 0.01) >= 2.0 THEN '警告'
                ELSE '正常'
           END AS anomaly_level
    FROM session_series ss, session_stats st
    WHERE ABS(ss.session_count - st.mean_session) / GREATEST(st.stddev_session, 0.01) >= &anomaly_threshold
    UNION ALL
    SELECT ss.snap_id,
           ss.snapshot_time,
           'Current Logons' AS metric_name,
           ss.current_logons AS metric_value,
           st.mean_logons AS mean_val,
           st.stddev_logons AS stddev_val,
           ROUND(ABS(ss.current_logons - st.mean_logons) / GREATEST(st.stddev_logons, 0.01), 2) AS z_score,
           CASE WHEN ss.current_logons > st.mean_logons THEN 'HIGH' ELSE 'LOW' END AS anomaly_direction,
           CASE WHEN ABS(ss.current_logons - st.mean_logons) / GREATEST(st.stddev_logons, 0.01) >= 3.0 THEN '严重'
                WHEN ABS(ss.current_logons - st.mean_logons) / GREATEST(st.stddev_logons, 0.01) >= 2.0 THEN '警告'
                ELSE '正常'
           END AS anomaly_level
    FROM session_series ss, session_stats st
    WHERE ABS(ss.current_logons - st.mean_logons) / GREATEST(st.stddev_logons, 0.01) >= &anomaly_threshold
    ORDER BY z_score DESC
)
WHERE ROWNUM <= &top_n;
```

### 6.3 会话数异常判定基线

| 指标 | 正常 Z-Score | 警告 Z-Score | 严重 Z-Score |
|------|------------|-------------|-------------|
| Session Count | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| Current Logons Count | < 2.0 | 2.0 ~ 3.0 | > 3.0 |

---

## 七、SQL 性能劣化检测（只读）

### 7.1 SQL 指标序列采集

```sql
-- 从 DBA_HIST_SQLSTAT 提取高频 SQL 的性能指标序列
SELECT s.snap_id,
       TO_CHAR(s.end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS snapshot_time,
       sql.sql_id,
       SUBSTR(st.sql_text, 1, 200) AS sql_text,
       sql.executions_delta AS executions,
       ROUND(sql.elapsed_time_delta / 1000000, 2) AS elapsed_sec,
       ROUND(sql.cpu_time_delta / 1000000, 2) AS cpu_sec,
       ROUND(sql.elapsed_time_delta / GREATEST(sql.executions_delta, 1) / 1000000, 4) AS avg_elapsed_sec,
       ROUND(sql.buffer_gets_delta / GREATEST(sql.executions_delta, 1), 2) AS avg_buffer_gets,
       ROUND(sql.disk_reads_delta / GREATEST(sql.executions_delta, 1), 2) AS avg_disk_reads,
       sql.rows_processed_delta AS rows_processed
FROM dba_hist_snapshot s
JOIN dba_hist_sqlstat sql
  ON s.snap_id = sql.snap_id
 AND s.instance_number = sql.instance_number
JOIN dba_hist_sqltext st
  ON sql.sql_id = st.sql_id
WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
  AND s.instance_number = (SELECT instance_number FROM v$instance)
  AND sql.executions_delta > 0
  AND sql.elapsed_time_delta > 0
  AND sql.sql_id IN (
    -- 筛选出在时间范围内总执行次数 TOP N 的 SQL
    SELECT sql_id FROM (
        SELECT sql_id,
               SUM(executions_delta) AS total_execs
        FROM dba_hist_sqlstat
        WHERE snap_id BETWEEN &snap_id_begin AND &snap_id_end
          AND executions_delta > 0
        GROUP BY sql_id
        ORDER BY total_execs DESC
    ) WHERE ROWNUM <= 100
  )
ORDER BY s.snap_id, sql.sql_id;
```

### 7.2 SQL 劣化异常判定

```sql
-- 检测 SQL 平均执行时间在各快照间的突变劣化
WITH sql_series AS (
    SELECT s.snap_id,
           sql.sql_id,
           ROUND(sql.elapsed_time_delta / GREATEST(sql.executions_delta, 1) / 1000000, 4) AS avg_elapsed_sec,
           ROUND(sql.buffer_gets_delta / GREATEST(sql.executions_delta, 1), 2) AS avg_buffer_gets,
           sql.executions_delta AS executions
    FROM dba_hist_snapshot s
    JOIN dba_hist_sqlstat sql
      ON s.snap_id = sql.snap_id
     AND s.instance_number = sql.instance_number
    WHERE s.snap_id BETWEEN &snap_id_begin AND &snap_id_end
      AND s.instance_number = (SELECT instance_number FROM v$instance)
      AND sql.executions_delta > 0
      AND sql.elapsed_time_delta > 0
),
sql_stats AS (
    SELECT sql_id,
           AVG(avg_elapsed_sec) AS mean_elapsed,
           STDDEV(avg_elapsed_sec) AS stddev_elapsed,
           AVG(avg_buffer_gets) AS mean_bg,
           STDDEV(avg_buffer_gets) AS stddev_bg,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_elapsed_sec) AS median_elapsed,
           PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avg_elapsed_sec) AS p95_elapsed,
           MIN(avg_elapsed_sec) AS min_elapsed,
           MAX(avg_elapsed_sec) AS max_elapsed,
           COUNT(*) AS snap_count
    FROM sql_series
    GROUP BY sql_id
    HAVING COUNT(*) >= 5  -- 至少 5 个快照的数据才做检测
)
SELECT *
FROM (
    SELECT ss.snap_id,
           ss.sql_id,
           ss.avg_elapsed_sec,
           ss.avg_buffer_gets,
           ss.executions,
           st.mean_elapsed,
           st.stddev_elapsed,
           st.median_elapsed,
           st.p95_elapsed,
           ROUND((ss.avg_elapsed_sec - st.mean_elapsed) / GREATEST(st.stddev_elapsed, 0.0001), 2) AS elapsed_z_score,
           CASE WHEN st.mean_elapsed > 0
                THEN ROUND(ss.avg_elapsed_sec / st.mean_elapsed, 2)
                ELSE 0
           END AS elapsed_ratio,
           CASE WHEN (ss.avg_elapsed_sec - st.mean_elapsed) / GREATEST(st.stddev_elapsed, 0.0001) >= 3.0
                     AND ss.avg_elapsed_sec > st.mean_elapsed THEN '严重劣化'
                WHEN (ss.avg_elapsed_sec - st.mean_elapsed) / GREATEST(st.stddev_elapsed, 0.0001) >= 2.0
                     AND ss.avg_elapsed_sec > st.mean_elapsed THEN '警告劣化'
                WHEN ss.avg_elapsed_sec > st.p95_elapsed * 2 THEN '突变劣化'
                ELSE '正常'
           END AS anomaly_level
    FROM sql_series ss
    JOIN sql_stats st ON ss.sql_id = st.sql_id
    WHERE ss.avg_elapsed_sec > st.mean_elapsed  -- 只看劣化，不看优化
      AND (
        (ss.avg_elapsed_sec - st.mean_elapsed) / GREATEST(st.stddev_elapsed, 0.0001) >= &anomaly_threshold
        OR ss.avg_elapsed_sec > st.p95_elapsed * 2
      )
    ORDER BY elapsed_z_score DESC
)
WHERE ROWNUM <= &top_n;
```

### 7.3 SQL 劣化关联分析

```sql
-- 对劣化 SQL，查看相邻快照的执行计划是否变化
SELECT sql_id,
       snap_id,
       plan_hash_value,
       optimizer_cost,
       optimizer_env_hash_value
FROM dba_hist_sqlstat
WHERE sql_id IN (&degraded_sql_ids)
  AND snap_id BETWEEN &snap_id_begin AND &snap_id_end
ORDER BY sql_id, snap_id;
```

### 7.4 SQL 劣化判定基线

| 指标 | 正常 | 警告劣化 | 严重劣化 |
|------|------|---------|---------|
| avg_elapsed_sec Z-Score | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| elapsed_ratio vs 均值 | < 2x | 2x ~ 5x | > 5x |
| vs p95_elapsed | < p95 | p95 ~ 2x p95 | > 2x p95 |
| avg_buffer_gets Z-Score | < 2.0 | 2.0 ~ 3.0 | > 3.0 |
| 执行计划 hash 变化 | 不变 | — | 变化 + 劣化 = 执行计划变更导致 |

---

## 八、综合异常报告

### 8.1 异常快照汇总

```sql
-- 汇总所有维度在指定时间范围内的异常快照（按时间线）
-- 此查询在应用层组装各维度检测结果后，按时间线合并展示
-- 各维度异常需从上述独立查询结果中汇总
```

> 在应用层汇总步骤 3-7 的异常检测结果，按 snapshot_time 合并，产出综合异常时间线。

### 8.2 多维关联分析

| 异常组合 | 可能根因 | 排查方向 |
|---------|---------|---------|
| CPU HIGH + IO HIGH + User I/O HIGH | 存储 IO 瓶颈导致 CPU 等待 | 检查存储 IO 性能、优化 IO 密集型 SQL |
| CPU HIGH + SQL 劣化 | 执行计划变化导致 CPU 消耗增加 | 对比 SQL 执行计划变化、检查统计信息 |
| Session COUNT HIGH + CPU HIGH | 连接风暴导致 CPU 压力 | 检查应用连接池配置、排查连接泄漏 |
| Concurrency HIGH + Session HIGH | 锁争用导致并发等待 | 检查锁等待链、排查热块 SQL |
| IO HIGH + log file sync HIGH | 日志写入瓶颈 | 检查 redo 日志磁盘性能、优化提交频率 |
| SQL 劣化 + plan_hash_value 变化 | 执行计划突变 | 对比执行计划差异、检查统计信息是否过期 |
| 多维度同时异常 | 系统级瓶颈 | 按 CPU > IO > 锁 > SQL 优先级排查 |

---

## 异常处理
- 单条查询失败不影响整体，标记该维度异常后继续其余查询。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- AWR 快照不存在时，提示"指定时间范围内无可用 AWR 快照，请调整 time_range_hours 参数"。
- 部分查询（如 DBA_HIST_SQLSTAT）在数据量过大时可能超时，建议缩小时间范围或减少 top_n。
- 当某个维度样本数不足（< 5 个快照）时，该维度不参与 Z-Score 检测，标记"样本不足，跳过异常检测"。
- 本技能仅做只读查询与统计分析，不执行任何 DDL/DML，单次执行耗时 ≤15s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. **快照范围概览**：可用快照总数、时间跨度、快照间隔
  2. **CPU 异常检测**：异常时间点 + 指标值 + Z-Score + 偏离方向 + 严重级别 + 关联 TOP SQL
  3. **IO 异常检测**：异常时间点 + 等待事件 + avg_wait_ms + Z-Score + 严重级别
  4. **等待事件异常检测**：异常时间点 + 等待类 + delta_wait_sec + Z-Score + 深入 TOP 等待事件
  5. **会话数异常检测**：异常时间点 + 会话数/登录数 + Z-Score + 偏离方向 + 严重级别
  6. **SQL 性能劣化检测**：异常时间点 + SQL_ID + avg_elapsed_sec + Z-Score + 劣化倍数 + 严重级别 + 执行计划变化
  7. **综合异常时间线**：按时间线汇总所有维度异常 + 多维关联分析 + 根因推断 + 排查建议