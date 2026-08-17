---
name: "db-oracle-plan-tuning"
description: "Oracle SQL 调优方案生成技能。核心能力：基于 SQL_ID 或 SQL 文本，从执行计划分析、SQL 改写、索引建议、统计信息、优化器提示、绑定变量等多维度输出结构化调优方案。涵盖：执行计划深度解读（访问路径 / 连接方式 / 代价估算偏差）、SQL 改写策略（子查询展开 / JOIN 改写 / UNION 优化 / 分页优化 / 分析函数替代）、索引优化建议（单列 / 复合 / 覆盖 / 函数索引推荐）、统计信息诊断与刷新建议、Hint 调优建议、绑定变量窥探与自适应游标分析。适用场景：单条 SQL 性能调优、AWR TOP SQL 优化方案输出、执行计划异常分析、SQL 改写与优化评审。功能限制：仅输出调优方案与建议，不执行 SQL 改写（不 ALTER SESSION / 不修改 SQL 文本）、不创建/删除索引（不执行 DDL）、不收集统计信息（不执行 DBMS_STATS）、不绑定 SQL Profile / SPM Baseline（不执行 DBMS_SQLTUNE / DBMS_SPM）；索引创建、统计信息刷新、SQL Profile 绑定等操作请使用对应执行类技能。"
version: "v1.0.0"
tags: db-ops
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
    desc: "待调优的 SQL_ID（优先使用；为空则需提供 sql_text）"
  - name: "sql_text"
    type: "string"
    required: false
    default: ""
    desc: "待调优的 SQL 文本（sql_id 为空时使用，用于静态分析）"
  - name: "tune_scope"
    type: "string"
    required: false
    default: "full"
    desc: "调优范围：full（全维度分析）/ plan（仅执行计划分析）/ rewrite（仅 SQL 改写）/ index（仅索引建议）/ stats（仅统计信息）/ hint（仅 Hint 调优）"
  - name: "include_sql_profile"
    type: "boolean"
    required: false
    default: false
    desc: "是否在方案中包含 SQL Profile 建议（默认 false，仅输出建议供 DBA 审查）"
  - name: "include_sql_rewrite"
    type: "boolean"
    required: false
    default: true
    desc: "是否在方案中包含 SQL 改写建议（默认 true）"
  - name: "include_index_advice"
    type: "boolean"
    required: false
    default: true
    desc: "是否在方案中包含索引建议（默认 true）"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle SQL 调优方案生成

> 针对指定 SQL（SQL_ID 或 SQL 文本），输出多维度结构化调优方案：执行计划分析、SQL 改写、索引建议、统计信息诊断、Hint 调优、绑定变量分析。本技能为 query 级方案，仅输出建议不执行任何变更。自包含。

## 核心能力
- 单一职责：Oracle SQL 调优方案生成（诊断 → 分析 → 建议 → 对比方案）。
- 多维度分析：执行计划、SQL 改写、索引、统计信息、Hint、绑定变量。
- 支持按 SQL_ID 在线分析或按 SQL 文本静态分析。

## 适用场景
- 单条 SQL 性能调优，需输出完整优化方案
- AWR / ASH TOP SQL 优化方案输出
- 执行计划异常分析（计划漂移、代价估算偏差）
- SQL 改写与优化评审（代码走查）
- 索引设计评审（基于 SQL 查询模式）
- 绑定变量窥探与自适应游标问题排查
- 统计信息过期导致的执行计划异常

## 功能限制 / 安全边界
- 不执行 SQL 改写（不 ALTER SESSION、不修改 SQL 文本）
- 不创建/删除索引（不执行 CREATE INDEX / DROP INDEX）
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）
- 不绑定 SQL Profile（不执行 DBMS_SQLTUNE.ACCEPT_SQL_PROFILE）
- 不绑定 SPM Baseline（不执行 DBMS_SPM.LOAD_PLANS_FROM_CURSOR_CACHE）
- 不修改优化器参数（不执行 ALTER SYSTEM / ALTER SESSION SET）
- 仅输出方案与建议，由 DBA 审查后执行；单次生成耗时 ≤5s

---

## 一、推理框架：SQL 调优方案生成链

```
用户提供 SQL_ID 或 SQL 文本
    |
    v
[1] SQL 信息收集（前置采集）
    | 从 v$sql / v$sqlstats 获取 SQL 完整文本与关键指标
    | 从 AWR 历史获取执行统计与趋势（DBA_HIST_SQLSTAT）
    | 获取当前执行计划（DBMS_XPLAN.DISPLAY_CURSOR）
    | 获取历史执行计划（DBMS_XPLAN.DISPLAY_AWR）
    v
[2] 执行计划深度解读
    | 访问路径分析（全表扫描 vs 索引扫描 vs ROWID 访问）
    | 连接方式分析（NESTED LOOPS / HASH JOIN / SORT MERGE JOIN / CARTESIAN）
    | 连接顺序分析（驱动表选择是否合理）
    | 代价估算分析（CARDINALITY / E-Rows vs A-Rows 偏差）
    | 分区裁剪与并行执行检查
    v
[3] SQL 改写策略
    | 子查询优化（标量子查询转 JOIN、NOT IN 转 NOT EXISTS / ANTI-JOIN）
    | JOIN 改写（驱动表调整、外连接转内连接、笛卡尔积消除）
    | UNION 优化（UNION 转 UNION ALL、合并重复查询）
    | 分页优化（ROWNUM / OFFSET-FETCH 优化）
    | 分析函数替代（自连接 / 子查询 → 分析函数）
    v
[4] 索引优化建议
    | 基于 WHERE 谓词推荐索引（列顺序、选择性）
    | 基于 JOIN 列推荐索引
    | 基于 ORDER BY / GROUP BY 推荐索引
    | 覆盖索引建议（避免回表）
    | 函数索引建议（对函数作用于列的场景）
    v
[5] 统计信息诊断
    | 表统计信息新鲜度检查
    | 索引统计信息新鲜度检查
    | 直方图检查（列数据倾斜情况）
    | 统计信息过期影响评估
    v
[6] Hint 调优建议
    | 连接方式 Hint（LEADING / USE_NL / USE_HASH / USE_MERGE）
    | 索引 Hint（INDEX / INDEX_RS / INDEX_FFS / NO_INDEX）
    | 并行 Hint（PARALLEL / PARALLEL_INDEX）
    | 查询转换 Hint（UNNEST / NO_UNNEST / MERGE / NO_MERGE）
    v
[7] 绑定变量与自适应游标分析
    | 绑定变量窥探影响分析
    | 自适应游标共享（ACS）检查
    | 绑定变量分级策略建议
    v
[8] 输出调优方案
    | 问题诊断（瓶颈定位、根因分析）
    | 优化建议（按优先级排序：高/中/低）
    | 预期收益评估（估算 CPU / IO / 执行时间下降幅度）
    | 回撤方案（SQL Profile 删除 / Baseline 禁用 / Hint 移除）
    | 验证方案（调优前后对比 SQL + 验证指标）
```

---

## 二、SQL 信息收集（前置采集，只读 SQL）

### 2.1 从共享池获取 SQL 详情

```sql
-- 获取 SQL 完整文本与关键指标
SELECT sql_id,
       sql_fulltext,
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
       optimizer_mode,
       parsing_schema_name,
       version_count,
       loads,
       first_load_time,
       last_load_time,
       last_active_time,
       ROUND(elapsed_time / GREATEST(executions, 1) / 1000000, 4) AS avg_elapsed_sec,
       ROUND(cpu_time / GREATEST(executions, 1) / 1000000, 4) AS avg_cpu_sec,
       ROUND(buffer_gets / GREATEST(executions, 1), 0) AS avg_buffer_gets,
       ROUND(disk_reads / GREATEST(executions, 1), 0) AS avg_disk_reads,
       ROUND(rows_processed / GREATEST(executions, 1), 0) AS avg_rows
FROM v$sqlstats
WHERE sql_id = '&sql_id';

-- 获取 SQL 绑定变量信息（by_address 方式）
SELECT name,
       position,
       datatype_string,
       value_string,
       last_captured
FROM v$sql_bind_capture
WHERE sql_id = '&sql_id'
ORDER BY position;
```

### 2.2 从 AWR 历史获取 SQL 执行趋势

```sql
-- SQL 执行统计历史趋势（按快照）
SELECT s.snap_id,
       TO_CHAR(sn.begin_interval_time, 'YYYY-MM-DD HH24:MI') AS snap_time,
       s.plan_hash_value,
       s.executions_delta AS executions,
       ROUND(s.elapsed_time_delta / 1000000, 2) AS elapsed_sec,
       ROUND(s.cpu_time_delta / 1000000, 2) AS cpu_sec,
       s.buffer_gets_delta AS buffer_gets,
       s.disk_reads_delta AS disk_reads,
       ROUND(s.elapsed_time_delta / GREATEST(s.executions_delta, 1) / 1000000, 4) AS avg_elapsed_sec,
       s.optimizer_cost
FROM dba_hist_sqlstat s
JOIN dba_hist_snapshot sn ON s.snap_id = sn.snap_id
WHERE s.sql_id = '&sql_id'
ORDER BY s.snap_id DESC;

-- 执行计划变化检测（plan_hash_value 漂移）
SELECT plan_hash_value,
       MIN(snap_id) AS first_snap,
       MAX(snap_id) AS last_snap,
       COUNT(*) AS snap_count,
       ROUND(SUM(elapsed_time_delta) / 1000000, 2) AS total_elapsed_sec
FROM dba_hist_sqlstat
WHERE sql_id = '&sql_id'
GROUP BY plan_hash_value
ORDER BY first_snap DESC;
```

### 2.3 获取执行计划

```sql
-- 从共享池获取当前执行计划（含实际行数与内存统计）
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(
    sql_id          => '&sql_id',
    cursor_child_no => 0,
    format          => 'ALLSTATS LAST +OUTLINE +PEEKED_BINDS'
));

-- 从 AWR 获取历史执行计划
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_AWR(
    sql_id    => '&sql_id',
    plan_hash_value => NULL,
    format    => 'ALLSTATS +OUTLINE'
));

-- 获取 SQL 执行计划的 Outline（用于 SQL Profile / Baseline）
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(
    sql_id          => '&sql_id',
    cursor_child_no => 0,
    format          => 'ADVANCED +OUTLINE'
));
```

---

## 三、执行计划深度解读（只读）

### 3.1 执行计划关键指标解读

| 操作类型 | 说明 | 良好指标 | 需关注指标 | 优化方向 |
|---------|------|---------|-----------|---------|
| **TABLE ACCESS FULL** | 全表扫描 | 小表（< 1000 行） | 大表（> 10000 行）且频繁执行 | 建索引 / 分区裁剪 |
| **INDEX UNIQUE SCAN** | 唯一索引扫描 | 最优访问路径 | — | 无需优化 |
| **INDEX RANGE SCAN** | 索引范围扫描 | 选择性好的范围查询 | 返回大量行 | 检查索引列顺序 |
| **INDEX FULL SCAN** | 索引全扫描 | 排序/分页场景 | 未利用排序避免排序 | 检查是否可范围扫描 |
| **INDEX FAST FULL SCAN** | 索引快速全扫描 | 覆盖索引场景 | 大量逻辑读 | 考虑覆盖索引 |
| **INDEX SKIP SCAN** | 索引跳跃扫描 | 前导列无法过滤时 | 效率低，扫描多分支 | 调整索引列顺序 |
| **TABLE ACCESS BY INDEX ROWID** | 回表访问 | 少量回表 | 大量回表 + 随机读 | 覆盖索引 |
| **NESTED LOOPS** | 嵌套循环连接 | 小表驱动大表 | 驱动表行数 > 1000 | 调整连接顺序或 HASH JOIN |
| **HASH JOIN** | 哈希连接 | 大表连接、无索引 | PGA 不足时落盘 | 检查 PGA 大小 |
| **SORT MERGE JOIN** | 排序合并连接 | 数据已排序 | 数据量大需排序 | 建索引避免排序 |
| **CARTESIAN** | 笛卡尔积 | 无（几乎总是异常） | 任何场景 | 检查 JOIN 条件 |
| **FILTER** | 过滤操作 | 小结果集 | 子查询未展开 | UNNEST 改写 |
| **VIEW** | 视图展开 | 简单视图 | 复杂视图嵌套多层 | 物化视图 / WITH 子句 |

### 3.2 执行计划异常检测（只读诊断 SQL）

```sql
-- 检测全表扫描最多的表（全局视图）
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

-- 检测笛卡尔积（CARTESIAN JOIN）
SELECT sql_id,
       plan_hash_value,
       child_number,
       operation,
       options,
       object_owner,
       object_name
FROM v$sql_plan
WHERE operation = 'MERGE JOIN'
  AND options = 'CARTESIAN'
  AND object_owner IS NOT NULL;

-- 检测 FILTER 操作（子查询未展开）
SELECT sql_id,
       plan_hash_value,
       child_number,
       operation,
       options,
       filter_predicates
FROM v$sql_plan
WHERE operation = 'FILTER'
  AND filter_predicates IS NOT NULL;
```

### 3.3 代价估算偏差分析

```sql
-- 获取 SQL 监视报告（需开启 MONITOR，适用于长时间运行的 SQL）
SELECT DBMS_SQLTUNE.REPORT_SQL_MONITOR(
    sql_id       => '&sql_id',
    type         => 'TEXT',
    report_level => 'ALL'
) AS monitor_report
FROM dual;

-- 检查 SQL 的 optimizer_cost 与实际开销的偏差
SELECT sql_id,
       plan_hash_value,
       optimizer_cost,
       elapsed_time,
       cpu_time,
       buffer_gets,
       ROUND(buffer_gets / GREATEST(optimizer_cost, 1), 2) AS buffer_gets_per_cost
FROM v$sqlstats
WHERE sql_id = '&sql_id';
```

---

## 四、SQL 改写策略（仅输出建议，不执行）

### 4.1 子查询优化

| 原始写法 | 问题 | 改写建议 | 适用条件 |
|---------|------|---------|---------|
| `SELECT ... FROM t1 WHERE col IN (SELECT col FROM t2)` | 子查询可能 FILTER | 改写为 `SELECT ... FROM t1 JOIN t2 ON t1.col = t2.col` | t2.col 去重或不关心重复 |
| `SELECT ... FROM t1 WHERE col NOT IN (SELECT col FROM t2)` | NULL 问题 + 性能差 | 改写为 `NOT EXISTS (SELECT 1 FROM t2 WHERE t2.col = t1.col)` 或 `LEFT JOIN ... WHERE t2.col IS NULL` | t2.col 可能含 NULL |
| `SELECT (SELECT col FROM t2 WHERE t2.id = t1.id) FROM t1` | 标量子查询逐行执行 | 改写为 `LEFT JOIN t2 ON t2.id = t1.id` | 大结果集 |
| `SELECT ... FROM t1 WHERE EXISTS (SELECT 1 FROM t2 WHERE ...)` | 可能 UNNEST 失败 | 使用 `/*+ UNNEST */` Hint 或改写为 JOIN | 优化器未自动展开 |
| `SELECT ... FROM (SELECT ... FROM t1) v WHERE ...` | 内联视图阻止谓词推入 | 使用 `/*+ MERGE */` Hint 或 WITH 子句改写 | 内联视图有聚合 |

### 4.2 JOIN 改写

| 原始写法 | 问题 | 改写建议 |
|---------|------|---------|
| 笛卡尔积（无连接条件） | 结果集膨胀 | 补全 JOIN 条件 |
| 外连接但实际不需要 | 阻止索引使用 | 改为内连接 |
| 驱动表行数大 | NESTED LOOPS 低效 | 调整表顺序或使用 `/*+ LEADING */` |
| 多表连接顺序不当 | 中间结果集膨胀 | 使用 `/*+ LEADING(a b c) */` 调整连接顺序 |

### 4.3 UNION 优化

```sql
-- 原始：UNION 去重（排序 + 去重，开销大）
SELECT col1, col2 FROM t1
UNION
SELECT col1, col2 FROM t2;

-- 改写：UNION ALL（无需去重时，性能提升显著）
SELECT col1, col2 FROM t1
UNION ALL
SELECT col1, col2 FROM t2;

-- 原始：UNION 后排序分页
SELECT * FROM (
    SELECT col1, col2 FROM t1
    UNION
    SELECT col1, col2 FROM t2
) WHERE ROWNUM <= 10;

-- 改写：各分支独立分页再 UNION ALL（减少中间结果集）
SELECT * FROM (
    SELECT col1, col2 FROM t1 WHERE ROWNUM <= 10
    UNION ALL
    SELECT col1, col2 FROM t2 WHERE ROWNUM <= 10
) WHERE ROWNUM <= 10;
```

### 4.4 分页查询优化

```sql
-- 原始：传统 ROWNUM 分页（全量排序后取分页）
-- 问题：大表排序开销大，且无法利用索引有序性
SELECT *
FROM (
    SELECT a.*, ROWNUM rn
    FROM (
        SELECT * FROM t ORDER BY create_time DESC
    ) a
    WHERE ROWNUM <= 100
)
WHERE rn > 50;

-- 改写1：使用 OFFSET-FETCH（12c+）
SELECT * FROM t
ORDER BY create_time DESC
OFFSET 50 ROWS FETCH NEXT 50 ROWS ONLY;

-- 改写2：使用分析函数 + 覆盖索引
SELECT * FROM (
    SELECT t.*, ROW_NUMBER() OVER (ORDER BY create_time DESC) rn
    FROM t
) WHERE rn BETWEEN 51 AND 100;
-- 建议：在 (create_time) 上建索引配合排序

-- 改写3：游标方式分页（大数据量深层翻页）
SELECT * FROM t
WHERE (create_time, id) < (:last_create_time, :last_id)
ORDER BY create_time DESC, id DESC
FETCH FIRST 50 ROWS ONLY;
```

### 4.5 分析函数替代自连接/子查询

```sql
-- 原始：自连接取每组 TOP N（如每个部门薪资最高的员工）
SELECT e.*
FROM emp e
WHERE e.salary = (
    SELECT MAX(salary) FROM emp WHERE dept_id = e.dept_id
);

-- 改写：使用分析函数
SELECT *
FROM (
    SELECT e.*,
           RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) rk
    FROM emp e
) WHERE rk = 1;

-- 原始：自连接做累计汇总
SELECT e1.id, e1.amount,
       (SELECT SUM(e2.amount) FROM emp e2 WHERE e2.id <= e1.id) AS running_total
FROM emp e1;

-- 改写：使用窗口函数
SELECT id, amount,
       SUM(amount) OVER (ORDER BY id) AS running_total
FROM emp;
```

---

## 五、索引优化建议（仅输出建议，不创建）

### 5.1 索引建议推演规则

```
分析 WHERE 条件中的谓词 → 确定索引候选列
    |
    ├── 等值谓词（=） → 选择性高的列排在索引前导列
    ├── 范围谓词（>、<、BETWEEN、LIKE 'xxx%'） → 放在等值列之后
    ├── ORDER BY 列 → 可纳入索引末尾避免排序
    ├── GROUP BY 列 → 可纳入索引利用排序
    └── SELECT 列 → 可纳入索引末尾做覆盖索引
    v
确定索引列顺序 → 输出 CREATE INDEX 建议语句
```

### 5.2 索引建议类型决策

| 场景 | 索引类型 | 示例 |
|------|---------|------|
| 单列等值查询 | 单列索引 | `CREATE INDEX idx_t_col ON t(col);` |
| 多列等值 + 范围查询 | 复合索引（等值列前，范围列后） | `CREATE INDEX idx_t_a_b ON t(a, b);` |
| 查询列全在索引中 | 覆盖索引（含 SELECT 列） | `CREATE INDEX idx_t_a_b_c ON t(a, b, c);` |
| 函数作用于列 | 函数索引 | `CREATE INDEX idx_t_upper_col ON t(UPPER(col));` |
| 前后模糊匹配 | 全文索引（Oracle Text） | `CREATE INDEX idx_t_col_ctx ON t(col) INDEXTYPE IS CTXSYS.CONTEXT;` |
| JSON 字段查询 | JSON 索引 | `CREATE INDEX idx_t_json ON t(json_col) INDEXTYPE IS CTXSYS.CONTEXT;` |

### 5.3 获取优化器推荐的缺失索引（SQL Tuning Advisor 辅助）

```sql
-- 创建 SQL Tuning 任务（仅分析，不执行）
DECLARE
    l_task_name VARCHAR2(30);
BEGIN
    l_task_name := DBMS_SQLTUNE.CREATE_TUNING_TASK(
        sql_id      => '&sql_id',
        scope       => 'COMPREHENSIVE',
        time_limit  => 60,
        task_name   => 'tune_task_' || '&sql_id',
        description => 'SQL tuning task for &sql_id'
    );
    DBMS_OUTPUT.PUT_LINE('Task created: ' || l_task_name);
END;
/

-- 执行 Tuning 任务
EXEC DBMS_SQLTUNE.EXECUTE_TUNING_TASK(task_name => 'tune_task_&sql_id');

-- 获取 Tuning 报告（含索引建议）
SET LONG 1000000
SELECT DBMS_SQLTUNE.REPORT_TUNING_TASK(task_name => 'tune_task_&sql_id')
FROM dual;

-- 清理 Tuning 任务
EXEC DBMS_SQLTUNE.DROP_TUNING_TASK(task_name => 'tune_task_&sql_id');
```

### 5.4 基于执行计划的索引建议 SQL

```sql
-- 检测全表扫描的表及其对应 SQL 谓词（用于分析建索引可行性）
SELECT p.sql_id,
       p.object_owner,
       p.object_name,
       p.filter_predicates,
       p.access_predicates
FROM v$sql_plan p
WHERE p.operation = 'TABLE ACCESS'
  AND p.options = 'FULL'
  AND p.object_owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND p.sql_id = '&sql_id';

-- 获取目标表现有索引
SELECT index_name,
       column_name,
       column_position,
       descend
FROM dba_ind_columns
WHERE table_owner = '&table_owner'
  AND table_name = '&table_name'
ORDER BY index_name, column_position;

-- 获取目标表列统计信息（选择性、直方图）
SELECT column_name,
       data_type,
       num_distinct,
       num_nulls,
       ROUND(num_distinct / GREATEST(num_rows, 1) * 100, 2) AS selectivity_pct,
       histogram,
       num_buckets
FROM dba_tab_col_statistics
WHERE owner = '&table_owner'
  AND table_name = '&table_name'
ORDER BY selectivity_pct;
```

---

## 六、统计信息诊断（只读）

### 6.1 统计信息新鲜度检查

```sql
-- 表统计信息新鲜度
SELECT owner,
       table_name,
       num_rows,
       blocks,
       last_analyzed,
       ROUND(SYSDATE - last_analyzed) AS days_stale,
       stale_stats,
       sample_size,
       ROUND(sample_size / GREATEST(num_rows, 1) * 100, 2) AS sample_pct
FROM dba_tab_statistics
WHERE owner = '&table_owner'
  AND table_name = '&table_name';

-- 索引统计信息新鲜度
SELECT table_owner,
       table_name,
       index_name,
       num_rows AS index_rows,
       distinct_keys,
       clustering_factor,
       leaf_blocks,
       last_analyzed,
       ROUND(SYSDATE - last_analyzed) AS days_stale
FROM dba_ind_statistics
WHERE table_owner = '&table_owner'
  AND table_name = '&table_name'
ORDER BY index_name;

-- 数据变更比例（DBA_TAB_MODIFICATIONS）
SELECT table_owner,
       table_name,
       inserts,
       updates,
       deletes,
       timestamp AS last_modified,
       ROUND((inserts + updates + deletes) / GREATEST((SELECT num_rows FROM dba_tab_statistics
           WHERE owner = m.table_owner AND table_name = m.table_name), 1) * 100, 2) AS pct_modified
FROM dba_tab_modifications m
WHERE table_owner = '&table_owner'
  AND table_name = '&table_name';
```

### 6.2 直方图检查

```sql
-- 列直方图类型与桶数
SELECT column_name,
       histogram,
       num_buckets,
       num_distinct,
       ROUND(num_distinct / GREATEST(num_rows, 1) * 100, 2) AS selectivity_pct
FROM dba_tab_col_statistics
WHERE owner = '&table_owner'
  AND table_name = '&table_name'
  AND histogram != 'NONE'
ORDER BY num_buckets DESC;

-- 直方图建议：数据倾斜的列（distinct 值少但分布不均）应建直方图
SELECT column_name,
       num_distinct,
       density,
       num_nulls,
       ROUND(num_distinct / GREATEST(num_rows, 1) * 100, 2) AS selectivity_pct
FROM dba_tab_col_statistics
WHERE owner = '&table_owner'
  AND table_name = '&table_name'
  AND histogram = 'NONE'
  AND num_distinct > 0
  AND num_distinct < 500
ORDER BY selectivity_pct;
```

### 6.3 统计信息刷新建议

```sql
-- 统计信息刷新建议（仅输出，不执行）
-- 表级刷新
-- EXEC DBMS_STATS.GATHER_TABLE_STATS(
--     ownname => '&table_owner',
--     tabname => '&table_name',
--     estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
--     method_opt => 'FOR ALL COLUMNS SIZE AUTO',
--     cascade => TRUE
-- );

-- Schema 级刷新
-- EXEC DBMS_STATS.GATHER_SCHEMA_STATS(
--     ownname => '&schema_name',
--     estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
--     method_opt => 'FOR ALL COLUMNS SIZE AUTO',
--     cascade => TRUE
-- );
```

---

## 七、Hint 调优建议（仅输出建议，不执行）

### 7.1 Hint 分类与使用场景

#### 连接方式 Hint

| Hint | 作用 | 适用场景 |
|------|------|---------|
| `/*+ LEADING(a b c) */` | 指定连接顺序（a → b → c） | 优化器选错驱动表 |
| `/*+ USE_NL(a b) */` | 强制 NESTED LOOPS（a 驱动 b） | 小表驱动大表，有索引 |
| `/*+ USE_HASH(a b) */` | 强制 HASH JOIN | 大表连接，无合适索引 |
| `/*+ USE_MERGE(a b) */` | 强制 SORT MERGE JOIN | 数据已排序，等值连接 |
| `/*+ ORDERED */` | 按 FROM 顺序连接 | 精确控制连接顺序 |

#### 索引 Hint

| Hint | 作用 | 适用场景 |
|------|------|---------|
| `/*+ INDEX(t idx_name) */` | 强制使用指定索引 | 优化器选错索引 |
| `/*+ INDEX_RS(t idx_name) */` | 强制索引范围扫描 | 需范围扫描而非全扫描 |
| `/*+ INDEX_FFS(t idx_name) */` | 强制索引快速全扫描 | 覆盖索引场景 |
| `/*+ NO_INDEX(t idx_name) */` | 禁用指定索引 | 索引低效，避免使用 |
| `/*+ FULL(t) */` | 强制全表扫描 | 小表，索引反而更慢 |

#### 查询转换 Hint

| Hint | 作用 | 适用场景 |
|------|------|---------|
| `/*+ UNNEST */` | 展开子查询 | 子查询 FILTER 未展开 |
| `/*+ NO_UNNEST */` | 不展开子查询 | 子查询展开后效果差 |
| `/*+ MERGE(v) */` | 合并内联视图 | 视图阻止谓词推入 |
| `/*+ NO_MERGE(v) */` | 不合并内联视图 | 视图合并后代价更大 |
| `/*+ MATERIALIZE */` | 物化 WITH 子句 | 多次引用同一 CTE |

#### 并行 Hint

| Hint | 作用 | 适用场景 |
|------|------|---------|
| `/*+ PARALLEL(t 4) */` | 表并行度为 4 | 大表全扫描 / 大排序 |
| `/*+ PARALLEL_INDEX(t idx 4) */` | 索引并行扫描 | 索引范围扫描数据量大 |
| `/*+ NO_PARALLEL(t) */` | 禁用并行 | OLTP 场景防止资源争用 |

### 7.2 Hint 使用原则

```
1. 能用索引优化就不加 Hint（Hint 是最后手段）
2. 一个 Hint 解决一个问题，避免堆砌 Hint
3. 加 Hint 后必须在测试环境验证执行计划
4. 记录 Hint 原因与生效条件，防止后续变更失效
5. 优先使用 SQL Profile / Baseline 而非硬编码 Hint
```

---

## 八、绑定变量与自适应游标分析（只读）

### 8.1 绑定变量窥探影响分析

```sql
-- 查看 SQL 绑定变量窥探值
SELECT name,
       position,
       datatype_string,
       value_string,
       was_captured,
       last_captured
FROM v$sql_bind_capture
WHERE sql_id = '&sql_id'
ORDER BY position;

-- 查看 SQL 的子游标（不同绑定变量值可能产生不同计划）
SELECT child_number,
       child_address,
       executions,
       elapsed_time,
       cpu_time,
       buffer_gets,
       is_bind_sensitive,
       is_bind_aware,
       is_shareable,
       plan_hash_value
FROM v$sql
WHERE sql_id = '&sql_id'
ORDER BY child_number;

-- 子游标数量与计划差异
SELECT child_number,
       plan_hash_value,
       executions,
       ROUND(elapsed_time / GREATEST(executions, 1) / 1000000, 4) AS avg_elapsed_sec,
       ROUND(buffer_gets / GREATEST(executions, 1), 0) AS avg_buffer_gets,
       is_bind_sensitive,
       is_bind_aware,
       is_shareable
FROM v$sql
WHERE sql_id = '&sql_id'
ORDER BY child_number;
```

### 8.2 自适应游标共享（ACS）检查

```sql
-- 检查 ACS 相关统计
SELECT name,
       value
FROM v$sysstat
WHERE name IN (
    'cursor authentications',
    'cursor bind mismatch',
    'bind mismatch'
);

-- 查看游标共享状态
SELECT child_number,
       is_bind_sensitive,
       is_bind_aware,
       is_shareable,
       plan_hash_value,
       parsing_schema_name,
       optimizer_mode,
       executions
FROM v$sql
WHERE sql_id = '&sql_id'
ORDER BY child_number;
```

### 8.3 绑定变量优化建议

| 问题 | 现象 | 建议 |
|------|------|------|
| 绑定变量窥探导致计划不稳定 | 多个子游标，plan_hash_value 不同 | 检查数据倾斜；考虑使用 `/*+ BIND_AWARE */` |
| 未使用绑定变量 | version_count 极高 | 改写为绑定变量 |
| 绑定变量分级 | 不同值的行数差异大 | 锁定执行计划（SQL Profile / Baseline） |
| 自适应游标未生效 | is_bind_aware = 'N' | 检查 `_optimizer_adaptive_cursor_sharing` 参数 |

---

## 九、SQL Profile 与 SPM Baseline 建议（仅输出建议，不执行）

### 9.1 SQL Profile 建议

```sql
-- 创建 SQL Profile 建议（仅输出，需 DBA 审查后手动执行）
-- 场景：优化器选择次优计划，需固定更好的计划
-- 步骤：
-- 1. 使用 SQL Tuning Advisor 生成 Profile
-- 2. 审查 Profile 建议
-- 3. 在测试环境验证
-- 4. 在生产环境执行

-- 获取 SQL Tuning Advisor 推荐的 Profile
-- DECLARE
--     l_task_name VARCHAR2(30) := 'tune_task_' || '&sql_id';
-- BEGIN
--     l_task_name := DBMS_SQLTUNE.CREATE_TUNING_TASK(
--         sql_id => '&sql_id',
--         scope  => 'COMPREHENSIVE',
--         time_limit => 60
--     );
--     DBMS_SQLTUNE.EXECUTE_TUNING_TASK(task_name => l_task_name);
-- END;
-- /

-- 查看 Profile 建议
-- SELECT DBMS_SQLTUNE.REPORT_TUNING_TASK(task_name => 'tune_task_&sql_id')
-- FROM dual;

-- 接受 Profile（需人工确认）
-- EXEC DBMS_SQLTUNE.ACCEPT_SQL_PROFILE(
--     task_name => 'tune_task_&sql_id',
--     task_owner => USER,
--     replace => TRUE
-- );

-- 禁用/删除 Profile
-- EXEC DBMS_SQLTUNE.ALTER_SQL_PROFILE(name => '&profile_name', attribute_name => 'STATUS', value => 'DISABLED');
-- EXEC DBMS_SQLTUNE.DROP_SQL_PROFILE(name => '&profile_name');
```

### 9.2 SPM Baseline 建议

```sql
-- 固定执行计划（SPM Baseline）建议（仅输出，不执行）
-- 场景：SQL 执行计划不稳定，需固定为已知的良好计划

-- 从共享池加载计划到 Baseline
-- DECLARE
--     l_plans_loaded PLS_INTEGER;
-- BEGIN
--     l_plans_loaded := DBMS_SPM.LOAD_PLANS_FROM_CURSOR_CACHE(
--         sql_id => '&sql_id',
--         plan_hash_value => &good_plan_hash_value
--     );
-- END;
-- /

-- 查看 SQL 的 Baseline
-- SELECT sql_handle, plan_name, enabled, accepted, fixed, origin
-- FROM dba_sql_plan_baselines
-- WHERE sql_text LIKE '%&sql_text_fragment%';

-- 禁用 Baseline
-- EXEC DBMS_SPM.ALTER_SQL_PLAN_BASELINE(
--     sql_handle => '&sql_handle',
--     plan_name => '&plan_name',
--     attribute_name => 'ENABLED',
--     attribute_value => 'NO'
-- );
```

---

## 十、SQL 调优方案输出模板

### 输出结构

**1. SQL 基本信息**
- SQL_ID、SQL 完整文本
- 执行频率、平均耗时、平均 CPU、平均逻辑读
- 当前执行计划 HASH 值、历史计划变化情况

**2. 问题诊断**
- 瓶颈定位（CPU 瓶颈 / IO 瓶颈 / 锁等待 / 解析瓶颈）
- 根因分析（全表扫描 / 索引失效 / 统计信息过期 / 连接方式不当 / 子查询未展开 / 绑定变量问题）

**3. 执行计划解读**
- 访问路径分析
- 连接方式与顺序分析
- 代价估算偏差分析
- 关键操作行数对比（E-Rows vs A-Rows）

**4. 优化建议（按优先级排序）**

| 优先级 | 类别 | 建议 | 预期收益 | 风险 |
|--------|------|------|---------|------|
| 高 | — | — | — | — |
| 中 | — | — | — | — |
| 低 | — | — | — | — |

**5. SQL 改写建议**（如有）
- 原 SQL 与改写后 SQL 对比
- 改写理由说明

**6. 索引建议**（如有）
- 建议创建的索引 DDL
- 建议删除的无用索引（如有）
- 索引维护成本评估

**7. 统计信息建议**（如有）
- 需要刷新的表/索引
- 直方图建议

**8. Hint 建议**（如有）
- 推荐 Hint 及说明
- 使用前提条件

**9. 验证方案**
- 调优前后对比 SQL
- 验证指标（执行时间 / CPU / 逻辑读 / 物理读 / 执行计划）
- 验证环境建议

**10. 回撤方案**
- 如何回退到调优前状态
- SQL Profile 删除 / Baseline 禁用 / Hint 移除

---

## 十一、常见 SQL 优化场景速查

| 场景 | 典型问题 | 调优方向 |
|------|---------|---------|
| 分页查询慢 | 大表全排序 + ROWNUM | 分析函数 + 覆盖索引 + 游标分页 |
| 多表关联慢 | CARTESIAN / 驱动表行数大 | 调整连接顺序、补充索引、HASH JOIN |
| 子查询慢 | FILTER 逐行执行 | 改写为 JOIN、UNNEST Hint |
| IN 列表慢 | 大量值与索引选择性差 | 改写为 JOIN、分批 IN、使用临时表 |
| OR 条件慢 | 索引失效 | 改写为 UNION ALL、使用 BITMAP 索引 |
| LIKE '%xxx%' 慢 | 索引失效 | 全文索引（Oracle Text）、限制业务 |
| GROUP BY 慢 | 大排序 | 建索引利用排序、增大 PGA |
| DISTINCT 慢 | 大排序去重 | 检查是否可以 EXISTS 替代、确保有索引 |
| 函数索引用不上 | 函数与索引不一致 | 统一函数写法、使用虚拟列 |
| 大表 UPDATE/DELETE | 全表扫描 + 大事务 | 分批处理、使用 ROWID 范围、分区 |

---

## 异常处理
- SQL_ID 在共享池中不存在时，回退到 AWR 历史查询，若仍不存在则提示用户提供 SQL 文本进行静态分析。
- 部分性能视图（如 v$sql_bind_capture）在权限不足时可能返回空，标记"权限不足，跳过绑定变量分析"。
- 执行计划获取失败时，尝试从 AWR 历史获取，若均失败则输出"无法获取执行计划"。
- 本技能仅做只读诊断与方案输出，不执行任何 DDL/DML/ALTER，单次执行耗时 ≤5s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. **SQL 基本信息**：SQL_ID / 文本 / 关键指标（执行次数、平均耗时、CPU、逻辑读、物理读）
  2. **问题诊断**：瓶颈定位 + 根因分析
  3. **执行计划解读**：访问路径 + 连接方式 + 代价估算偏差 + 关键操作行数对比
  4. **优化建议**：按优先级排序（高/中/低），含类别、建议内容、预期收益、风险
  5. **SQL 改写建议**（如有）：原 SQL vs 改写后 SQL + 改写理由
  6. **索引建议**（如有）：DDL + 维护成本评估
  7. **统计信息建议**（如有）：需刷新的表/索引 + 直方图建议
  8. **Hint 建议**（如有）：推荐 Hint + 使用前提
  9. **验证方案**：调优前后对比 + 验证指标
  10. **回撤方案**：回退操作步骤