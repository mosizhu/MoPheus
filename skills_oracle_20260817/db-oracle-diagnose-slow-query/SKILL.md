---
name: "db-oracle-diagnose-slow-query"
description: "Oracle 慢查询诊断与 TOP N 慢 SQL 定位技能。核心能力：从 AWR 历史快照 / v$ 动态视图定位 TOP N 慢 SQL（按 elapsed time / CPU time / buffer gets / disk reads 排序）、获取执行计划（DBMS_XPLAN.DISPLAY_CURSOR / DISPLAY_AWR）、识别全表扫描与索引失效、统计信息新鲜度检查、SQL 执行频率与资源消耗趋势分析。适用场景：数据库响应变慢根因定位、AWR 报告辅助解读、TOP N 资源消耗 SQL 筛查、执行计划异常分析、统计信息过期排查。功能限制：本技能仅做只读诊断与参考，不执行 SQL Profile/SPM 绑定、不收集统计信息（DBMS_STATS）、不修改 SQL 文本、不调整优化器参数；索引建议请用对应索引设计类技能，统计信息刷新请用统计信息维护类技能。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "sql_id"
    type: "string"
    required: false
    default: ""
    desc: "指定 SQL_ID 进行单条深度分析（可选，为空则按 TOP N 筛查）"
  - name: "top_n"
    type: "integer"
    required: false
    default: 10
    desc: "返回 TOP N 条慢 SQL，默认 10"
  - name: "sort_metric"
    type: "string"
    required: false
    default: "elapsed"
    desc: "排序指标：elapsed（总耗时）/ cpu（CPU 时间）/ buffer_gets（逻辑读）/ disk_reads（物理读）/ executions（执行次数）"
  - name: "time_range_hours"
    type: "integer"
    required: false
    default: 24
    desc: "AWR 历史查询时间范围（小时），默认最近 24 小时"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 慢查询诊断与 TOP N 慢 SQL 定位

本技能为只读诊断技能，从 AWR 历史快照与 v$ 动态视图定位 TOP N 慢 SQL、解读执行计划、检测全表扫描与索引失效，并给出优化方向建议（不执行任何变更）。

---

## 核心能力
- 从 AWR 历史快照（DBA_HIST_SQLSTAT）与 v$ 动态视图筛查 TOP N 慢 SQL
- 对指定 SQL_ID 获取执行计划（DBMS_XPLAN）并深度解读
- 全表扫描检测、索引使用率与未使用索引查询
- 统计信息新鲜度检查（DBA_TAB_STATISTICS / DBA_IND_STATISTICS）
- SQL 执行频率与资源消耗趋势分析

## 适用场景
- 数据库响应变慢，需快速定位资源消耗 TOP N SQL
- AWR 报告辅助解读与补充分析
- 按 elapsed time / CPU / 逻辑读 / 物理读 多维度筛查问题 SQL
- 对指定 SQL_ID 做执行计划深度分析
- 排查统计信息过期导致的执行计划异常

## 功能限制 / 安全边界
- 不执行 SQL Profile 创建/绑定（DBMS_SQLTUNE）
- 不执行 SPM（SQL Plan Management）基线操作
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）
- 不修改 SQL 文本、不调整优化器参数（optimizer_index_cost_adj 等）
- 不调用其它 Skill、不自动修复、仅按需手动触发

---

## 一、推理框架：Oracle 慢查询诊断链

```
用户报告数据库响应慢 / CPU 高
    |
    v
[1] 定位慢 SQL 来源
    | v$sqlarea / v$sqlstats（实时）
    | DBA_HIST_SQLSTAT（历史 AWR 快照）
    v
[2] 获取执行计划
    | DBMS_XPLAN.DISPLAY_CURSOR(sql_id, cursor_child_no, 'ALLSTATS LAST')
    | DBMS_XPLAN.DISPLAY_AWR(sql_id)
    v
[3] 判断优化方向
    | TABLE ACCESS FULL → 全表扫描 → 检查索引/统计信息
    | INDEX FAST FULL SCAN → 索引全扫描 → 检查覆盖索引
    | NESTED LOOPS vs HASH JOIN → 连接方式是否合理
    | CARDINALITY 估算偏差大 → 统计信息过期
    v
[4] 给出优化建议（参考，不执行）
```

---

## 二、实时慢 SQL 定位（v$ 动态视图，只读）

```sql
-- 按总耗时排序 TOP N（当前共享池中）
SELECT *
FROM (
    SELECT sql_id,
           sql_text,
           elapsed_time,
           cpu_time,
           buffer_gets,
           disk_reads,
           executions,
           ROUND(elapsed_time / GREATEST(executions, 1) / 1000000, 2) AS avg_elapsed_sec,
           ROUND(elapsed_time / 1000000, 2) AS total_elapsed_sec
    FROM v$sql
    WHERE executions > 0
    ORDER BY elapsed_time DESC
)
WHERE ROWNUM <= 10;

-- 按每次执行平均耗时排序
SELECT *
FROM (
    SELECT sql_id,
           SUBSTR(sql_text, 1, 200) AS sql_text,
           elapsed_time,
           executions,
           ROUND(elapsed_time / GREATEST(executions, 1) / 1000000, 2) AS avg_elapsed_sec
    FROM v$sql
    WHERE executions > 0
    ORDER BY elapsed_time / GREATEST(executions, 1) DESC
)
WHERE ROWNUM <= 10;

-- 按物理读排序（高 I/O SQL）
SELECT *
FROM (
    SELECT sql_id,
           SUBSTR(sql_text, 1, 200) AS sql_text,
           disk_reads,
           buffer_gets,
           executions,
           ROUND(disk_reads / GREATEST(executions, 1), 0) AS avg_disk_reads
    FROM v$sql
    WHERE executions > 0 AND disk_reads > 0
    ORDER BY disk_reads DESC
)
WHERE ROWNUM <= 10;

-- 按逻辑读排序（高内存消耗 SQL）
SELECT *
FROM (
    SELECT sql_id,
           SUBSTR(sql_text, 1, 200) AS sql_text,
           buffer_gets,
           executions,
           ROUND(buffer_gets / GREATEST(executions, 1), 0) AS avg_buffer_gets
    FROM v$sql
    WHERE executions > 0
    ORDER BY buffer_gets DESC
)
WHERE ROWNUM <= 10;
```

---

## 三、AWR 历史慢 SQL 定位（DBA_HIST，只读）

```sql
-- 从 AWR 历史快照获取 TOP N 慢 SQL（按总耗时）
SELECT *
FROM (
    SELECT s.sql_id,
           SUBSTR(t.sql_text, 1, 200) AS sql_text,
           SUM(s.elapsed_time_delta) / 1000000 AS total_elapsed_sec,
           SUM(s.cpu_time_delta) / 1000000 AS total_cpu_sec,
           SUM(s.buffer_gets_delta) AS total_buffer_gets,
           SUM(s.disk_reads_delta) AS total_disk_reads,
           SUM(s.executions_delta) AS total_executions,
           ROUND(SUM(s.elapsed_time_delta) / GREATEST(SUM(s.executions_delta), 1) / 1000000, 2) AS avg_elapsed_sec
    FROM dba_hist_sqlstat s
    JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
    WHERE s.snap_id IN (
        SELECT snap_id FROM dba_hist_snapshot
        WHERE begin_interval_time >= SYSDATE - NUMTODSINTERVAL(24, 'HOUR')
    )
    GROUP BY s.sql_id, t.sql_text
    ORDER BY SUM(s.elapsed_time_delta) DESC
)
WHERE ROWNUM <= 10;

-- 查看 AWR 快照时间范围
SELECT snap_id, begin_interval_time, end_interval_time
FROM dba_hist_snapshot
WHERE begin_interval_time >= SYSDATE - 7
ORDER BY snap_id DESC;
```

---

## 四、执行计划获取与解读（只读）

```sql
-- 从共享池获取当前执行计划
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(
    sql_id          => '&sql_id',
    cursor_child_no => 0,
    format          => 'ALLSTATS LAST'
));

-- 从 AWR 获取历史执行计划
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_AWR(
    sql_id    => '&sql_id',
    format    => 'ALLSTATS LAST'
));

-- 查看 SQL 的执行计划历史（是否有变化）
SELECT plan_hash_value,
       MIN(timestamp) AS first_seen,
       MAX(timestamp) AS last_seen,
       COUNT(*) AS plan_count
FROM dba_hist_sql_plan
WHERE sql_id = '&sql_id'
GROUP BY plan_hash_value;
```

| 执行计划关键指标 | 含义 | 优化提示 |
|------|------|---------|
| TABLE ACCESS FULL | 全表扫描 | 检查是否缺失索引或统计信息过期 |
| INDEX FAST FULL SCAN | 索引全扫描 | 评估是否可改为索引范围扫描 |
| INDEX RANGE SCAN | 索引范围扫描 | 较为理想，检查索引列顺序 |
| INDEX UNIQUE SCAN | 唯一索引扫描 | 最优，通常无需优化 |
| NESTED LOOPS | 嵌套循环连接 | 小表驱动大表时效率高 |
| HASH JOIN | 哈希连接 | 大表连接适用，检查 PGA 是否充足 |
| CARDINALITY | 预估行数 | 如与实际偏差超 10x，统计信息可能过期 |
| A-Rows vs E-Rows | 实际 vs 预估行数 | 偏差大说明统计信息不准确 |

```
访问路径性能排序（优→劣）：
INDEX UNIQUE SCAN > INDEX RANGE SCAN > INDEX FULL SCAN > INDEX FAST FULL SCAN > TABLE ACCESS BY INDEX ROWID > TABLE ACCESS FULL
```

---

## 五、全表扫描与索引使用检测（只读）

```sql
-- 检测全表扫描最多的表
SELECT *
FROM (
    SELECT object_owner,
           object_name,
           operation,
           options,
           COUNT(*) AS occurrences
    FROM v$sql_plan
    WHERE operation = 'TABLE ACCESS'
      AND options = 'FULL'
      AND object_owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
    GROUP BY object_owner, object_name, operation, options
    ORDER BY occurrences DESC
)
WHERE ROWNUM <= 20;

-- 未使用索引检测
SELECT table_owner,
       table_name,
       index_name,
       num_rows,
       last_analyzed
FROM dba_indexes
WHERE owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND status = 'VALID'
  AND monitoring = 'YES'
ORDER BY last_analyzed ASC;

-- 索引使用监控（需先启用监控：ALTER INDEX xxx MONITORING USAGE）
SELECT *
FROM v$object_usage
WHERE used = 'NO'
  AND start_monitoring IS NOT NULL
ORDER BY start_monitoring DESC;
```

---

## 六、统计信息新鲜度检查（只读）

```sql
-- 表统计信息新鲜度
SELECT owner,
       table_name,
       num_rows,
       blocks,
       last_analyzed,
       ROUND(SYSDATE - last_analyzed) AS days_stale
FROM dba_tab_statistics
WHERE owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND stale_stats = 'YES'
ORDER BY days_stale DESC;

-- 索引统计信息新鲜度
SELECT table_owner,
       table_name,
       index_name,
       last_analyzed,
       ROUND(SYSDATE - last_analyzed) AS days_stale
FROM dba_ind_statistics
WHERE table_owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND stale_stats = 'YES'
ORDER BY days_stale DESC;

-- 查看表的数据变更比例（DBA_TAB_MODIFICATIONS）
SELECT table_owner,
       table_name,
       inserts,
       updates,
       deletes,
       timestamp AS last_modified,
       ROUND((inserts + updates + deletes) / GREATEST(num_rows, 1) * 100, 2) AS pct_modified
FROM dba_tab_modifications
WHERE table_owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
ORDER BY (inserts + updates + deletes) DESC;
```

---

## 七、SQL 优化方向参考（只诊断，不执行）

| 问题 | 现象 | 建议方向 |
|------|------|---------|
| 全表扫描 | TABLE ACCESS FULL + 大表 | 检查索引是否存在、统计信息是否过期 |
| 索引失效 | 隐式类型转换 / 函数作用于列 | 确保 WHERE 条件类型与列一致 |
| 统计信息过期 | E-Rows 与 A-Rows 偏差 > 10x | 收集统计信息（DBMS_STATS） |
| 连接顺序不当 | NESTED LOOPS 驱动大表 | 检查表连接顺序与统计信息 |
| PGA 不足 | HASH JOIN 频繁 TEMP 落盘 | 增大 PGA_AGGREGATE_TARGET |
| 绑定变量窥探 | 执行计划不稳定 | 考虑自适应游标共享或 SQL Profile |
| 硬解析过多 | 高 version_count | 检查是否未使用绑定变量 |
| 子查询未展开 | FILTER 操作 | 改写为 JOIN 或使用 WITH 子句 |

---

## 八、SQL 执行统计详情（v$sqlstats，只读）

```sql
-- 单条 SQL 详细统计
SELECT sql_id,
       plan_hash_value,
       executions,
       elapsed_time,
       cpu_time,
       buffer_gets,
       disk_reads,
       direct_writes,
       rows_processed,
       fetches,
       optimizer_cost,
       version_count,
       loads,
       first_load_time,
       last_load_time,
       last_active_time
FROM v$sqlstats
WHERE sql_id = '&sql_id';

-- 执行计划变化检测（plan_hash_value 是否漂移）
SELECT snap_id,
       plan_hash_value,
       optimizer_cost,
       elapsed_time_total,
       executions_total
FROM dba_hist_sqlstat
WHERE sql_id = '&sql_id'
ORDER BY snap_id;
```

---

## 异常处理
- 单条查询失败不影响整体，标记该维度异常后继续其余查询。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- AWR 快照不存在时，回退到 v$ 动态视图实时查询。
- 本技能仅做只读诊断，不执行任何 DDL/DML，单次执行耗时 ≤5s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：TOP N SQL 列表（SQL_ID + 关键指标） + 执行计划解读 + 全表扫描与索引使用概览 + 统计信息新鲜度 + 优化方向建议。