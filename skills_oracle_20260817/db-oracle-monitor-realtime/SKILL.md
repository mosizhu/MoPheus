---
name: "db-oracle-monitor-realtime"
description: "Oracle 实时指标监控技能（CPU / 连接数 / 慢查询数）。核心能力：(1) CPU 监控：OS 级 CPU 使用率、DB CPU 占比、CPU 等待事件、实例 CPU 使用率趋势；(2) 连接数监控：当前会话数与使用率、会话状态分布（ACTIVE/INACTIVE）、按用户/程序/机器的连接分布、长时间空闲会话检测；(3) 慢查询数监控：当前长时间运行 SQL 列表、历史慢查询统计（按 elapsed_time/cpu_time/executions 排序）、慢查询趋势分析。适用场景：数据库实时状态巡检、资源水位监控、慢查询排查、连接数异常预警。功能限制：仅做只读查询与展示，不 KILL 会话、不修改参数、不执行 DDL/DML。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "metric_type"
    type: "string"
    required: false
    default: ""
    desc: "指标类型：cpu / connection / slow_query（可选，为空则全量采集）"
  - name: "top_n"
    type: "integer"
    required: false
    default: 10
    desc: "返回 TOP N 条结果，默认 10"
  - name: "slow_threshold_sec"
    type: "integer"
    required: false
    default: 5
    desc: "慢查询判定阈值（秒），默认 5 秒"
  - name: "time_range_hours"
    type: "integer"
    required: false
    default: 1
    desc: "历史数据查询时间范围（小时），默认最近 1 小时"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 实时指标监控：CPU / 连接数 / 慢查询数

本技能为只读监控技能，从 v$ 动态视图、v$sysmetric 实时指标视图与 AWR 历史快照三个维度，对 Oracle 数据库进行 CPU、连接数、慢查询数的实时监控，产出结构化指标快照并给出阈值对照与建议（不执行任何变更）。

---

## 核心能力

### CPU 监控
- OS 级 CPU 使用率（Host CPU Utilization、OS Load、CPU 核数）
- DB CPU 占比与时间模型分解
- CPU 相关等待事件（resmgr、scheduler、latch 等）
- 实例 CPU 使用率趋势（v$sysmetric_history）

### 连接数监控
- 当前会话总数与使用率（sessions vs processes 上限）
- 会话状态分布（ACTIVE / INACTIVE / KILLED / CACHED）
- 按用户/程序/机器的连接来源分布
- 长时间空闲会话检测（INACTIVE 超过阈值）
- 连接数历史趋势

### 慢查询数监控
- 当前长时间运行 SQL（运行时间超过 slow_threshold_sec）
- 历史慢查询统计（按 elapsed_time / cpu_time 排序）
- 慢查询关联的等待事件与阻塞信息
- 慢查询趋势分析（ASH 历史采样）

## 适用场景
- 数据库实时状态巡检，快速了解 CPU/连接/慢查询水位
- 连接数异常突增排查（连接风暴/连接泄漏）
- 慢查询数量激增排查（应用变更/执行计划变化）
- 资源水位监控与容量评估
- 日常巡检快照采集

## 功能限制 / 安全边界
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改实例参数（不执行 ALTER SYSTEM SET）
- 不调整连接数上限（不修改 processes/sessions 参数）
- 不执行 SQL Profile/SPM 操作
- 不调用其它 Skill、不自动修复、仅按需手动触发
- 单次执行耗时 ≤10s，无第三方依赖、无外部资源引用

---

## 一、推理框架：实时监控诊断链

```
用户请求查看实时指标（CPU/连接数/慢查询）
    |
    v
[1] 参数解析：确定 metric_type（cpu/connection/slow_query/全量）
    | 为空 → 全量采集三个维度
    | 指定类型 → 仅采集对应维度
    v
[2] CPU 指标采集
    | OS CPU 使用率 + 核数 + Load
    | DB CPU 占比 + 时间模型
    | CPU 等待事件
    | 近期 CPU 趋势
    v
[3] 连接数指标采集
    | 当前会话数 vs 上限
    | 会话状态分布
    | 连接来源分布（用户/程序/机器）
    | 长空闲会话检测
    | 连接数趋势
    v
[4] 慢查询指标采集
    | 当前长时间运行 SQL
    | 历史慢查询 TOP N
    | 慢查询等待事件分布
    | 慢查询趋势
    v
[5] 综合展示与阈值对照
    | 结构化指标输出
    | 阈值对照（正常/警告/严重）
    | 异常指标标记与建议
```

---

## 二、CPU 监控（只读）

### 2.1 OS 级 CPU 使用率

```sql
-- CPU 核心数与 OS 统计
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
    'LOAD'
)
ORDER BY stat_name;

-- 主机 CPU 使用率（实时）
SELECT metric_name,
       value,
       metric_unit
FROM v$sysmetric
WHERE metric_name IN (
    'Host CPU Utilization (%)',
    'Database CPU Time Ratio',
    'OS Load'
)
  AND group_id = 2
ORDER BY metric_name;
```

### 2.2 DB CPU 与时间模型

```sql
-- DB CPU 时间模型分解
SELECT stat_name,
       ROUND(value / 1000000, 2) AS total_sec
FROM v$sys_time_model
WHERE stat_name IN (
    'DB time', 'DB CPU',
    'sql execute elapsed time', 'parse time elapsed',
    'hard parse elapsed time', 'PL/SQL execution elapsed time',
    'connection management call elapsed time'
)
ORDER BY value DESC;

-- 实例 CPU 使用率（累计）
SELECT name,
       value
FROM v$sysstat
WHERE name IN (
    'CPU used by this session',
    'parse time cpu',
    'recursive cpu usage'
)
ORDER BY name;
```

### 2.3 CPU 趋势（近期历史）

```sql
-- 近期 CPU 使用率趋势（v$sysmetric_history）
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
  AND begin_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
ORDER BY begin_time DESC;
```

### 2.4 CPU 指标基线

| 指标 | 正常范围 | 警告阈值 | 严重阈值 |
|------|---------|---------|---------|
| Host CPU Utilization | < 60% | 60%~85% | > 85% |
| Database CPU Time Ratio | < 50% | 50%~75% | > 75% |
| OS Load (每核) | < 1.0 | 1.0~2.0 | > 2.0 |
| Hard Parse 占比 | < 5% | 5%~10% | > 10% |

---

## 三、连接数监控（只读）

### 3.1 当前连接数与使用率

```sql
-- 当前会话数 vs 上限
SELECT 
    (SELECT COUNT(*) FROM v$session) AS current_sessions,
    (SELECT value FROM v$parameter WHERE name = 'sessions') AS sessions_limit,
    (SELECT value FROM v$parameter WHERE name = 'processes') AS processes_limit,
    ROUND((SELECT COUNT(*) FROM v$session) 
        / (SELECT value FROM v$parameter WHERE name = 'sessions') * 100, 2) AS sessions_usage_pct,
    ROUND((SELECT COUNT(*) FROM v$session WHERE status = 'ACTIVE') 
        / (SELECT value FROM v$parameter WHERE name = 'sessions') * 100, 2) AS active_sessions_pct
FROM dual;

-- 历史最大会话数
SELECT sessions_max,
       sessions_warning,
       sessions_current,
       sessions_limit_value
FROM v$license;
```

### 3.2 会话状态分布

```sql
-- 按状态分组统计
SELECT status,
       COUNT(*) AS session_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM v$session
GROUP BY status
ORDER BY session_count DESC;

-- 按会话类型分组
SELECT type,
       COUNT(*) AS session_count
FROM v$session
GROUP BY type
ORDER BY session_count DESC;
```

### 3.3 连接来源分布

```sql
-- 按用户名统计
SELECT username,
       COUNT(*) AS connection_count,
       COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) AS active_count
FROM v$session
WHERE username IS NOT NULL
GROUP BY username
ORDER BY connection_count DESC;

-- 按程序统计
SELECT program,
       COUNT(*) AS connection_count,
       COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) AS active_count
FROM v$session
WHERE program IS NOT NULL
GROUP BY program
ORDER BY connection_count DESC;

-- 按机器来源统计
SELECT machine,
       COUNT(*) AS connection_count,
       COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) AS active_count
FROM v$session
WHERE machine IS NOT NULL
GROUP BY machine
ORDER BY connection_count DESC;
```

### 3.4 长时间空闲会话检测

```sql
-- 空闲超过 30 分钟的 INACTIVE 会话
SELECT sid,
       serial#,
       username,
       machine,
       program,
       status,
       ROUND(last_call_et / 60, 1) AS idle_minutes,
       TO_CHAR(logon_time, 'YYYY-MM-DD HH24:MI:SS') AS logon_time,
       sql_id
FROM v$session
WHERE status = 'INACTIVE'
  AND username IS NOT NULL
  AND last_call_et > 1800
ORDER BY last_call_et DESC;
```

### 3.5 连接数指标基线

| 指标 | 正常范围 | 警告阈值 | 严重阈值 |
|------|---------|---------|---------|
| 会话使用率 | < 60% | 60%~80% | > 80% |
| ACTIVE 会话占比 | < 20% | 20%~40% | > 40% |
| 单用户连接数 | < 100 | 100~200 | > 200 |
| 空闲 > 30min 会话数 | < 10 | 10~50 | > 50 |

---

## 四、慢查询数监控（只读）

### 4.1 当前长时间运行 SQL

```sql
-- 当前运行时间超过阈值的 SQL
SELECT s.sid,
       s.serial#,
       s.username,
       s.program,
       s.machine,
       s.status,
       s.event,
       s.seconds_in_wait,
       s.last_call_et AS elapsed_sec,
       s.sql_id,
       s.sql_child_number,
       SUBSTR(q.sql_text, 1, 200) AS sql_text,
       s.blocking_session,
       s.row_wait_obj#
FROM v$session s
LEFT JOIN v$sql q ON s.sql_id = q.sql_id AND s.sql_child_number = q.child_number
WHERE s.status = 'ACTIVE'
  AND s.type != 'BACKGROUND'
  AND s.last_call_et > &slow_threshold_sec
  AND s.username IS NOT NULL
ORDER BY s.last_call_et DESC;
```

### 4.2 慢查询等待事件分布

```sql
-- 当前长时间运行 SQL 的等待事件分布
SELECT event,
       COUNT(*) AS session_count,
       ROUND(AVG(seconds_in_wait), 1) AS avg_wait_sec,
       MAX(seconds_in_wait) AS max_wait_sec
FROM v$session
WHERE status = 'ACTIVE'
  AND type != 'BACKGROUND'
  AND last_call_et > &slow_threshold_sec
  AND username IS NOT NULL
GROUP BY event
ORDER BY session_count DESC;
```

### 4.3 历史慢查询统计（即时采集）

```sql
-- 从 v$sqlstats 按 CPU 时间排序的慢查询
SELECT *
FROM (
    SELECT sql_id,
           SUBSTR(sql_text, 1, 200) AS sql_text,
           ROUND(elapsed_time / 1000000, 2) AS elapsed_sec,
           ROUND(cpu_time / 1000000, 2) AS cpu_sec,
           executions,
           ROUND(elapsed_time / GREATEST(executions, 1) / 1000000, 4) AS avg_elapsed_sec,
           buffer_gets,
           disk_reads,
           rows_processed,
           ROUND(elapsed_time * 100.0 / SUM(elapsed_time) OVER (), 2) AS elapsed_pct
    FROM v$sqlstats
    WHERE executions > 0
      AND elapsed_time / GREATEST(executions, 1) / 1000000 > &slow_threshold_sec
    ORDER BY elapsed_time DESC
)
WHERE ROWNUM <= &top_n;
```

### 4.4 慢查询趋势（ASH 历史采样）

```sql
-- 从 ASH 获取最近 N 小时的慢查询采样趋势
SELECT TO_CHAR(sample_time, 'YYYY-MM-DD HH24:MI') AS sample_minute,
       COUNT(*) AS slow_query_samples,
       COUNT(DISTINCT sql_id) AS distinct_sql_count,
       COUNT(DISTINCT session_id) AS distinct_session_count,
       ROUND(AVG(CAST(tm_delta_time AS NUMBER) / 1000000), 2) AS avg_elapsed_sec
FROM v$active_session_history
WHERE sample_time >= SYSDATE - NUMTODSINTERVAL(&time_range_hours, 'HOUR')
  AND tm_delta_time IS NOT NULL
  AND CAST(tm_delta_time AS NUMBER) / 1000000 > &slow_threshold_sec
  AND session_type != 'BACKGROUND'
GROUP BY TO_CHAR(sample_time, 'YYYY-MM-DD HH24:MI')
ORDER BY 1 DESC;
```

### 4.5 慢查询指标基线

| 指标 | 正常范围 | 警告阈值 | 严重阈值 |
|------|---------|---------|---------|
| 当前慢查询数 | < 5 | 5~20 | > 20 |
| 平均执行时间 | < 5s | 5s~30s | > 30s |
| 单 SQL 最大执行时间 | < 30s | 30s~300s | > 300s |
| 慢查询趋势 | 平稳 | 缓慢上升 | 急剧上升 |
| DB CPU 等待超 5s 的会话 | < 3 | 3~10 | > 10 |

---

## 五、异常处理
- 单条查询失败不影响整体，标记该维度异常后继续其余查询。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- 部分查询在权限不足时可能返回空，标记"权限不足，跳过该项"。
- 本技能仅做只读查询与展示，不执行任何 DDL/DML，单次执行耗时 ≤10s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. **实时指标概览**：CPU 使用率、连接数使用率、当前慢查询数 三项核心指标快速一览
  2. **CPU 维度**：OS CPU 使用率 + DB CPU 占比 + 时间模型 + 趋势
  3. **连接数维度**：当前会话数/上限 + 状态分布 + 来源分布 + 长空闲会话
  4. **慢查询维度**：当前长时间运行 SQL 列表 + 历史慢查询 TOP N + 趋势
  5. **阈值对照与建议**：各指标与基线的对照状态（正常/警告/严重）+ 异常标记