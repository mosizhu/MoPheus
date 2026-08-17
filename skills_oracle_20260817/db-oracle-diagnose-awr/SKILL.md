---
name: "db-oracle-diagnose-awr"
description: "Oracle AWR 报告分析技能。核心能力：解析 AWR 报告负载概要（Load Profile）、定位 TOP 等待事件（按等待类分类与根因解读）、识别热点 SQL（按 Elapsed Time / CPU / Buffer Gets / Disk Reads / Executions 多维度排序）、时间模型分解（DB Time 分布）、实例效率命中率评估、等待事件与热点 SQL 关联分析。适用场景：AWR 报告自动解读、数据库性能瓶颈定位、等待事件根因分析、热点 SQL 与资源消耗关联诊断、RAC 全局等待事件分析。功能限制：本技能仅做只读诊断与参考，不执行 SQL Profile/SPM 绑定、不收集统计信息、不修改 SQL 文本、不调整实例参数；索引建议请用对应索引设计类技能，统计信息刷新请用统计信息维护类技能。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "snap_id_begin"
    type: "integer"
    required: false
    default: 0
    desc: "AWR 起始快照 ID（为 0 则自动选择最近一对快照）"
  - name: "snap_id_end"
    type: "integer"
    required: false
    default: 0
    desc: "AWR 结束快照 ID（为 0 则自动选择最近一对快照）"
  - name: "top_n"
    type: "integer"
    required: false
    default: 10
    desc: "返回 TOP N 条等待事件 / 热点 SQL，默认 10"
  - name: "time_range_hours"
    type: "integer"
    required: false
    default: 24
    desc: "自动选择快照时的时间范围（小时），默认最近 24 小时"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle AWR 报告分析：等待事件与热点 SQL 定位

本技能为只读诊断技能，从 AWR 历史快照（DBA_HIST_*）与 v$ 动态视图解析 Oracle 数据库性能数据，定位 TOP 等待事件与热点 SQL，并给出优化方向建议（不执行任何变更）。

---

## 核心能力
- AWR 负载概要解读（DB Time、Redo、逻辑读/物理读、解析、事务等核心指标）
- TOP 等待事件按等待类分类与根因解读（User I/O、System I/O、Concurrency、Cluster、Commit、Network、Configuration 等）
- 热点 SQL 多维排序定位（Elapsed Time / CPU / Buffer Gets / Disk Reads / Executions）
- 时间模型分解（DB Time 在各维度的分布比例）
- 实例效率命中率评估（Buffer Hit%、Library Cache Hit%、等）
- 等待事件与热点 SQL 关联分析

## 适用场景
- Oracle 数据库性能突然变慢，需快速定位瓶颈
- AWR 报告自动解读与关键指标提取
- 等待事件根因分析（如 enq: TX - row lock contention、log file sync 等）
- 热点 SQL 与资源消耗关联诊断
- RAC 环境全局等待事件分析
- 定期性能巡检与趋势对比

## 功能限制 / 安全边界
- 不执行 SQL Profile 创建/绑定（DBMS_SQLTUNE）
- 不执行 SPM（SQL Plan Management）基线操作
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）
- 不修改 SQL 文本、不调整实例参数
- 不生成 AWR 报告快照（不执行 DBMS_WORKLOAD_REPOSITORY.CREATE_SNAPSHOT）
- 不调用其它 Skill、不自动修复、仅按需手动触发

---

## 一、推理框架：AWR 性能诊断链

```
用户报告数据库性能问题 / 提交 AWR 报告
    |
    v
[1] 确认快照范围与负载概要
    | 快照时间范围、DB Time、Elapsed Time、DB CPU
    | Redo size、Logical/Physical reads、Executes、Transactions
    v
[2] 等待事件 TOP N 分析
    | 按等待类分类（User I/O、System I/O、Concurrency、Cluster 等）
    | 识别 Top 等待事件及其占比
    | 解读等待事件根因与关联资源
    v
[3] 时间模型分解
    | DB Time 拆分：sql execute、parse、PL/SQL、RMAN、connection management 等
    | 定位 DB Time 主要消耗维度
    v
[4] 热点 SQL 定位
    | 按 Elapsed Time / CPU / Buffer Gets / Disk Reads / Executions 多维排序
    | 关联等待事件：该 SQL 主要在等什么
    v
[5] 实例效率与命中率
    | Buffer Hit%、Library Cache Hit%、等
    | 识别异常指标
    v
[6] 综合诊断结论与优化建议（参考，不执行）
```

---

## 二、快照范围确认与负载概要（只读）

```sql
-- 查看可用 AWR 快照范围
SELECT snap_id,
       TO_CHAR(begin_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS begin_time,
       TO_CHAR(end_interval_time, 'YYYY-MM-DD HH24:MI:SS') AS end_time,
       ROUND((CAST(end_interval_time AS DATE) - CAST(begin_interval_time AS DATE)) * 24 * 60, 1) AS duration_min
FROM dba_hist_snapshot
WHERE begin_interval_time >= SYSDATE - NUMTODSINTERVAL(24, 'HOUR')
  AND instance_number = (SELECT instance_number FROM v$instance)
ORDER BY snap_id DESC;

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

---

## 三、等待事件 TOP N 分析（按等待类分类，只读）

### 3.1 全局等待事件 TOP N（按等待时间）

```sql
-- 按等待时间排序的 TOP N 等待事件
SELECT *
FROM (
    SELECT event_name,
           wait_class,
           ROUND(SUM(time_waited_micro_fg) / 1000000, 2) AS total_wait_sec,
           SUM(total_waits_fg) AS total_waits,
           ROUND(SUM(time_waited_micro_fg) / GREATEST(SUM(total_waits_fg), 1) / 1000, 2) AS avg_wait_ms,
           ROUND(SUM(time_waited_micro_fg) * 100.0 / SUM(SUM(time_waited_micro_fg)) OVER (), 2) AS pct_of_total
    FROM dba_hist_system_event
    WHERE snap_id = &snap_id_end
      AND wait_class != 'Idle'
      AND time_waited_micro_fg > 0
    GROUP BY event_name, wait_class
    ORDER BY total_wait_sec DESC
)
WHERE ROWNUM <= 10;

-- 按等待类聚合
SELECT wait_class,
       ROUND(SUM(time_waited_micro_fg) / 1000000, 2) AS total_wait_sec,
       ROUND(SUM(time_waited_micro_fg) * 100.0 / SUM(SUM(time_waited_micro_fg)) OVER (), 2) AS pct_of_total
FROM dba_hist_system_event
WHERE snap_id = &snap_id_end
  AND wait_class != 'Idle'
  AND time_waited_micro_fg > 0
GROUP BY wait_class
ORDER BY total_wait_sec DESC;
```

### 3.2 等待事件增量计算（跨快照差值）

```sql
-- 基于快照差值的等待事件 TOP N（更精准）
SELECT *
FROM (
    SELECT e.event_name,
           e.wait_class,
           ROUND((e.time_waited_micro_fg - b.time_waited_micro_fg) / 1000000, 2) AS delta_wait_sec,
           (e.total_waits_fg - b.total_waits_fg) AS delta_waits,
           ROUND((e.time_waited_micro_fg - b.time_waited_micro_fg) / GREATEST((e.total_waits_fg - b.total_waits_fg), 1) / 1000, 2) AS avg_wait_ms
    FROM dba_hist_system_event e
    JOIN dba_hist_system_event b
      ON e.event_name = b.event_name
     AND e.wait_class = b.wait_class
     AND b.snap_id = &snap_id_begin
    WHERE e.snap_id = &snap_id_end
      AND e.wait_class != 'Idle'
      AND (e.time_waited_micro_fg - b.time_waited_micro_fg) > 0
    ORDER BY delta_wait_sec DESC
)
WHERE ROWNUM <= 10;
```

### 3.3 关键等待事件解读

| 等待事件 | 等待类 | 常见原因 | 排查方向 |
|---------|--------|---------|---------|
| db file sequential read | User I/O | 单块读（索引扫描） | 检查 SQL 执行计划、索引效率、I/O 子系统 |
| db file scattered read | User I/O | 多块读（全表扫描/快速全索引扫描） | 检查全表扫描 SQL、I/O 吞吐 |
| log file sync | Commit | 提交等待 LGWR 写日志 | 检查提交频率、日志组大小、磁盘 I/O |
| log file parallel write | System I/O | LGWR 写 redo 日志 | 检查 redo 日志磁盘 I/O 性能 |
| enq: TX - row lock contention | Application | 行级锁冲突 | 定位锁等待链、优化事务逻辑 |
| buffer busy waits | Concurrency | 缓冲块争用 | 检查热块 SQL、考虑 Hash 分区或反转键索引 |
| latch: cache buffers chains | Concurrency | 缓冲链闩锁争用 | 热块 SQL、高并发访问 |
| direct path read | User I/O | 直接路径读（全表扫描/并行查询） | 检查并行度、SGA 大小 |
| enq: TM - contention | Application | 表级锁冲突 | 检查外键索引、DDL 操作 |
| read by other session | User I/O | 多会话同时读同一块 | 检查热块 SQL、优化 I/O |
| gc cr block busy | Cluster | RAC 全局缓存块争用 | 检查 RAC 热块、应用分区 |
| gc buffer busy acquire | Cluster | RAC 缓冲区获取等待 | 优化 RAC 热块、减少跨节点访问 |

---

## 四、时间模型分解（DB Time 分布，只读）

```sql
-- 时间模型增量分解（DB Time 占比）
SELECT e.stat_name,
       ROUND((e.value - b.value) / 1000000, 2) AS delta_sec,
       ROUND((e.value - b.value) * 100.0 / SUM(e.value - b.value) OVER (), 2) AS pct_of_db_time
FROM dba_hist_sys_time_model e
JOIN dba_hist_sys_time_model b
  ON e.stat_name = b.stat_name
 AND b.snap_id = &snap_id_begin
WHERE e.snap_id = &snap_id_end
  AND e.stat_name IN (
    'DB time', 'DB CPU',
    'sql execute elapsed time', 'parse time elapsed',
    'PL/SQL execution elapsed time', 'Java execution elapsed time',
    'RMAN cpu time (backup/restore)',
    'connection management call elapsed time',
    'hard parse elapsed time', 'failed parse elapsed time',
    'inbound PL/SQL rpc elapsed time',
    'sequence load elapsed time'
  )
ORDER BY (e.value - b.value) DESC;
```

---

## 五、热点 SQL 定位（多维度，只读）

### 5.1 按总耗时 TOP N

```sql
-- 热点 SQL：按总耗时排序
SELECT *
FROM (
    SELECT s.sql_id,
           SUBSTR(t.sql_text, 1, 200) AS sql_text,
           ROUND(SUM(s.elapsed_time_delta) / 1000000, 2) AS total_elapsed_sec,
           ROUND(SUM(s.cpu_time_delta) / 1000000, 2) AS total_cpu_sec,
           ROUND(SUM(s.elapsed_time_delta) / GREATEST(SUM(s.executions_delta), 1) / 1000000, 4) AS avg_elapsed_sec,
           SUM(s.executions_delta) AS executions,
           SUM(s.buffer_gets_delta) AS buffer_gets,
           SUM(s.disk_reads_delta) AS disk_reads,
           SUM(s.rows_processed_delta) AS rows_processed,
           ROUND(SUM(s.elapsed_time_delta) * 100.0 / SUM(SUM(s.elapsed_time_delta)) OVER (), 2) AS pct_of_total
    FROM dba_hist_sqlstat s
    JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
    WHERE s.snap_id = &snap_id_end
    GROUP BY s.sql_id, t.sql_text
    ORDER BY total_elapsed_sec DESC
)
WHERE ROWNUM <= 10;
```

### 5.2 按 Buffer Gets（逻辑读）TOP N

```sql
-- 热点 SQL：按逻辑读排序
SELECT *
FROM (
    SELECT s.sql_id,
           SUBSTR(t.sql_text, 1, 200) AS sql_text,
           SUM(s.buffer_gets_delta) AS buffer_gets,
           SUM(s.disk_reads_delta) AS disk_reads,
           SUM(s.executions_delta) AS executions,
           ROUND(SUM(s.buffer_gets_delta) / GREATEST(SUM(s.executions_delta), 1), 0) AS avg_buffer_gets,
           ROUND(SUM(s.elapsed_time_delta) / 1000000, 2) AS total_elapsed_sec
    FROM dba_hist_sqlstat s
    JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
    WHERE s.snap_id = &snap_id_end
    GROUP BY s.sql_id, t.sql_text
    ORDER BY buffer_gets DESC
)
WHERE ROWNUM <= 10;
```

### 5.3 按 Disk Reads（物理读）TOP N

```sql
-- 热点 SQL：按物理读排序
SELECT *
FROM (
    SELECT s.sql_id,
           SUBSTR(t.sql_text, 1, 200) AS sql_text,
           SUM(s.disk_reads_delta) AS disk_reads,
           SUM(s.buffer_gets_delta) AS buffer_gets,
           SUM(s.executions_delta) AS executions,
           ROUND(SUM(s.disk_reads_delta) / GREATEST(SUM(s.executions_delta), 1), 0) AS avg_disk_reads,
           ROUND(SUM(s.elapsed_time_delta) / 1000000, 2) AS total_elapsed_sec
    FROM dba_hist_sqlstat s
    JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
    WHERE s.snap_id = &snap_id_end
      AND s.disk_reads_delta > 0
    GROUP BY s.sql_id, t.sql_text
    ORDER BY disk_reads DESC
)
WHERE ROWNUM <= 10;
```

### 5.4 按执行次数 TOP N

```sql
-- 热点 SQL：按执行次数排序
SELECT *
FROM (
    SELECT s.sql_id,
           SUBSTR(t.sql_text, 1, 200) AS sql_text,
           SUM(s.executions_delta) AS executions,
           ROUND(SUM(s.elapsed_time_delta) / 1000000, 2) AS total_elapsed_sec,
           ROUND(SUM(s.elapsed_time_delta) / GREATEST(SUM(s.executions_delta), 1) / 1000000, 4) AS avg_elapsed_sec,
           SUM(s.buffer_gets_delta) AS buffer_gets
    FROM dba_hist_sqlstat s
    JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
    WHERE s.snap_id = &snap_id_end
    GROUP BY s.sql_id, t.sql_text
    ORDER BY executions DESC
)
WHERE ROWNUM <= 10;
```

---

## 六、等待事件与热点 SQL 关联分析（只读）

```sql
-- 查看热点 SQL 在 AWR 中的等待事件分布
SELECT sql_id,
       session_state,
       event,
       COUNT(*) AS sample_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY sql_id), 2) AS pct
FROM dba_hist_active_sess_history
WHERE sql_id IN (
    SELECT sql_id
    FROM (
        SELECT sql_id
        FROM dba_hist_sqlstat
        WHERE snap_id = &snap_id_end
        GROUP BY sql_id
        ORDER BY SUM(elapsed_time_delta) DESC
    )
    WHERE ROWNUM <= 5
)
  AND snap_id BETWEEN &snap_id_begin AND &snap_id_end
GROUP BY sql_id, session_state, event
ORDER BY COUNT(*) DESC;

-- 按等待事件反查关联 SQL
SELECT event,
       sql_id,
       COUNT(*) AS samples,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY event), 2) AS pct
FROM dba_hist_active_sess_history
WHERE snap_id BETWEEN &snap_id_begin AND &snap_id_end
  AND event IN (
    SELECT event_name
    FROM (
        SELECT event_name
        FROM dba_hist_system_event
        WHERE snap_id = &snap_id_end
          AND wait_class != 'Idle'
        ORDER BY time_waited_micro_fg DESC
    )
    WHERE ROWNUM <= 5
  )
  AND sql_id IS NOT NULL
GROUP BY event, sql_id
ORDER BY event, samples DESC;
```

---

## 七、实例效率命中率评估（只读）

```sql
-- 实例效率指标（Buffer Hit%、Library Cache Hit% 等）
SELECT e.stat_name,
       ROUND((e.value - b.value) / GREATEST(e.value, 1), 0) AS delta_value,
       CASE
         WHEN e.stat_name LIKE '%hit%' THEN
           ROUND((e.value - b.value) * 100.0 / GREATEST(e.value, 1), 2) || ' %'
         ELSE
           TO_CHAR(ROUND((e.value - b.value), 0))
       END AS metric_value
FROM dba_hist_sysstat e
JOIN dba_hist_sysstat b
  ON e.stat_name = b.stat_name
 AND b.snap_id = &snap_id_begin
WHERE e.snap_id = &snap_id_end
  AND e.stat_name IN (
    'buffer cache hit ratio',
    'library cache hit ratio',
    'cursor cache hit ratio',
    'row cache hit ratio',
    'execute without parse ratio',
    'soft parse ratio',
    'memory sorts ratio',
    'parse count (hard)',
    'parse count (total)'
  )
ORDER BY e.stat_name;
```

| 命中率指标 | 健康阈值 | 低于阈值排查方向 |
|-----------|---------|----------------|
| Buffer Cache Hit Ratio | > 95% | 增大 SGA / 检查全表扫描 |
| Library Cache Hit Ratio | > 95% | 检查硬解析、未使用绑定变量 |
| Cursor Cache Hit Ratio | > 95% | 检查游标共享、SESSION_CACHED_CURSORS |
| Row Cache Hit Ratio | > 90% | 检查 DDL 频率、共享池大小 |
| Soft Parse Ratio | > 95% | 检查绑定变量使用、CURSOR_SHARING |

---

## 八、RAC 全局等待事件分析（RAC 环境，只读）

```sql
-- RAC 全局等待事件 TOP N
SELECT *
FROM (
    SELECT event_name,
           ROUND(SUM(time_waited_micro) / 1000000, 2) AS total_wait_sec,
           SUM(total_waits) AS total_waits,
           ROUND(AVG(time_waited_micro / GREATEST(total_waits, 1) / 1000), 2) AS avg_wait_ms
    FROM gv$system_event
    WHERE wait_class != 'Idle'
      AND event_name LIKE 'gc%'
    GROUP BY event_name
    ORDER BY total_wait_sec DESC
)
WHERE ROWNUM <= 10;

-- RAC 全局缓存传输统计
SELECT *
FROM (
    SELECT name,
           value
    FROM v$sysstat
    WHERE name LIKE 'gc%'
      AND value > 0
    ORDER BY value DESC
)
WHERE ROWNUM <= 20;
```

---

## 九、优化方向参考（只诊断，不执行）

| 问题 | 现象 | 建议方向 |
|------|------|---------|
| I/O 瓶颈 | db file sequential/scattered read 占比高 | 优化热点 SQL 索引、增加 Buffer Cache、检查存储 I/O |
| 提交瓶颈 | log file sync 占比高 | 减少提交频率、增大日志组、优化磁盘 I/O |
| 行锁冲突 | enq: TX - row lock contention 占比高 | 缩短事务、优化事务逻辑、检查锁等待链 |
| 缓冲争用 | buffer busy waits / latch: cache buffers chains | 优化热块 SQL、考虑 Hash 分区或反转键索引 |
| 硬解析 | Library Cache Hit < 95% | 使用绑定变量、增大共享池 |
| 全表扫描 | Buffer Cache Hit < 95% + 高物理读 | 检查缺失索引、优化 SQL |
| RAC 热块 | gc cr block busy / gc buffer busy | 应用分区、减少跨节点访问 |
| 大量执行 | 执行次数高 + 平均耗时低 | 检查是否可批量执行、减少网络往返 |

---

## 异常处理
- 单条查询失败不影响整体，标记该维度异常后继续其余查询。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- AWR 快照不存在时，回退提示用户先通过 `SELECT * FROM dba_hist_snapshot` 确认可用快照范围。
- RAC 相关查询在单实例环境返回空结果属正常，标记"非 RAC 环境"。
- 本技能仅做只读诊断，不执行任何 DDL/DML，单次执行耗时 ≤10s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. 快照信息（时间范围、DB Time、Elapsed Time）
  2. 负载概要（Redo、逻辑读/物理读、执行/事务数）
  3. TOP N 等待事件（按等待类分类 + 占比 + 根因解读）
  4. 时间模型分布（DB Time 分解）
  5. 热点 SQL 多维排名（Elapsed / CPU / Buffer Gets / Disk Reads / Executions）
  6. 等待事件与 SQL 关联（Top Wait 对应哪些 SQL）
  7. 实例效率命中率
  8. 综合诊断结论与优化建议