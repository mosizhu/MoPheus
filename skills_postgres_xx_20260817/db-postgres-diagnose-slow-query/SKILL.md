---
name: "db-postgres-diagnose-slow-query"
description: "PostgreSQL 慢查询日志深度分析技能。核心能力：pg_stat_statements 慢查询 TOP N 筛查、慢查询日志文件（CSV/TEXT）解析、EXPLAIN ANALYZE 执行计划解读（含 cost/actual time/rows 偏差）、顺序扫描（Seq Scan）检测、索引命中率与未使用索引分析、锁等待分析、auto_explain 日志关联。适用场景：慢查询定位与根因分析、执行计划瓶颈诊断、全表扫描与索引失效排查、锁竞争导致的慢查询。功能限制：本技能仅做查询与分析，不创建索引、不修改 SQL、不执行 VACUUM/ANALYZE、不调整 PostgreSQL 配置参数；索引创建请用 db-postgres-index-design，统计信息刷新请用 db-postgres-stats-refresh。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "PostgreSQL 实例地址（host:port）"
  - name: "db_name"
    type: "string"
    required: false
    default: ""
    desc: "目标数据库名（可选，不填则分析所有数据库）"
  - name: "sql_text"
    type: "string"
    required: false
    default: ""
    desc: "待分析的 SQL 语句（可选，用于 EXPLAIN ANALYZE 解读）"
  - name: "log_file_path"
    type: "string"
    required: false
    default: ""
    desc: "慢查询日志文件路径（可选，用于从日志文件解析慢查询，支持 CSV 格式与标准文本格式）"
  - name: "top_n"
    type: "integer"
    required: false
    default: 20
    desc: "返回慢查询 TOP N 条数"
  - name: "min_duration_ms"
    type: "integer"
    required: false
    default: 1000
    desc: "慢查询最小耗时阈值（毫秒），用于过滤分析结果"
support_db: postgresql
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# PostgreSQL 慢查询日志深度分析

本技能为只读慢查询分析技能，基于 `pg_stat_statements`、慢查询日志文件、`EXPLAIN ANALYZE`、系统统计视图，定位慢查询根因并给出优化方向建议（不执行任何变更）。

---

## 核心能力
- 从 `pg_stat_statements` 筛查 TOP N 慢查询（按 total_time / mean_time / calls 排序）
- 解析 PostgreSQL 慢查询日志文件（CSV 格式 / 标准 text 格式），提取耗时超标 SQL
- 对给定 SQL 做 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` 深度解读
- 顺序扫描（Seq Scan）检测、索引命中率分析、未使用索引识别
- 锁等待分析（`pg_locks` + `pg_stat_activity` 关联）
- `auto_explain` 日志关联分析（自动记录的执行计划）
- 表膨胀（bloat）与 autovacuum 状态与慢查询的关联分析

## 适用场景
- 慢查询 TOP N 筛查与统计分析
- 从 PostgreSQL 慢查询日志文件中批量提取慢 SQL
- 对指定 SQL 执行 EXPLAIN ANALYZE 深度解读，定位瓶颈算子
- 检测全表扫描（Seq Scan）占比高的表
- 查看索引使用率与未使用索引
- 诊断锁等待导致的慢查询
- 分析 auto_explain 自动记录的执行计划

## 功能限制 / 安全边界
- 不创建索引（不执行 CREATE INDEX / CREATE INDEX CONCURRENTLY）
- 不修改 SQL 语句内容
- 不刷新统计信息（不执行 ANALYZE / VACUUM ANALYZE）
- 不调整 PostgreSQL 配置参数（不执行 ALTER SYSTEM / SET）
- 不安装或启用扩展（不执行 CREATE EXTENSION）
- 不终止会话（不执行 pg_terminate_backend / pg_cancel_backend）
- 不调用其它 Skill、不自动修复、仅按需手动触发

---

## 前置检查：确保 pg_stat_statements 扩展已启用

```sql
-- 检查是否已安装
SELECT * FROM pg_extension WHERE extname = 'pg_stat_statements';

-- 检查 shared_preload_libraries 是否包含 pg_stat_statements
SHOW shared_preload_libraries;

-- 若未启用，需在 postgresql.conf 中添加并重启（本技能不执行）
-- shared_preload_libraries = 'pg_stat_statements'
```

---

## 一、推理框架：PostgreSQL 慢查询诊断链

```
用户报告查询慢 / CPU 高 / IO 高
    |
    v
[1] 定位慢查询来源
    | pg_stat_statements 统计视图（按 total_time / mean_time 排序）
    | 或 PostgreSQL 慢查询日志文件（log_min_duration_statement 控制）
    v
[2] 获取执行计划
    | EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <SQL>
    | 分析：节点类型 / 实际耗时 / 估算偏差 / 缓冲区命中
    v
[3] 判断瓶颈类型
    | Seq Scan         → 全表扫描 → 检查索引缺失 / 统计信息过期
    | Index Scan       → 索引扫描 → 检查索引选择性 / 回表代价
    | Bitmap Heap Scan → 位图扫描 → 检查是否适合普通索引扫描
    | Nested Loop      → 嵌套循环 → 检查内表是否有索引
    | Hash Join        → 哈希连接 → 检查 work_mem 是否足够
    | Sort             → 排序操作 → 检查是否需要索引规避排序
    | Lock Wait        → 锁等待   → 检查 pg_locks 竞争
    v
[4] 给出优化建议（参考，不执行）
```

---

## 二、pg_stat_statements 慢查询定位（只读）

```sql
-- 重置统计（可选，本技能不执行，仅提示）
-- SELECT pg_stat_statements_reset();

-- TOP N 慢查询（按总耗时排序）
SELECT queryid,
       LEFT(query, 200) AS query_preview,
       calls,
       ROUND(total_exec_time::numeric, 2) AS total_ms,
       ROUND(mean_exec_time::numeric, 2) AS avg_ms,
       ROUND(min_exec_time::numeric, 2) AS min_ms,
       ROUND(max_exec_time::numeric, 2) AS max_ms,
       ROUND(stddev_exec_time::numeric, 2) AS stddev_ms,
       rows,
       shared_blks_hit,
       shared_blks_read,
       ROUND(shared_blks_hit::numeric / NULLIF(shared_blks_hit + shared_blks_read, 0) * 100, 2) AS cache_hit_ratio
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
  AND query !~* '(pg_stat|pg_catalog|information_schema)'
ORDER BY total_exec_time DESC
LIMIT 20;

-- TOP N 慢查询（按平均耗时排序，适合发现偶发慢查询）
SELECT queryid,
       LEFT(query, 200) AS query_preview,
       calls,
       ROUND(mean_exec_time::numeric, 2) AS avg_ms,
       ROUND(total_exec_time::numeric, 2) AS total_ms,
       ROUND(max_exec_time::numeric, 2) AS max_ms,
       ROUND(stddev_exec_time::numeric, 2) AS stddev_ms
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
  AND calls > 10
ORDER BY mean_exec_time DESC
LIMIT 20;

-- IO 密集型查询（共享缓冲区命中率低）
SELECT queryid,
       LEFT(query, 200) AS query_preview,
       calls,
       shared_blks_hit,
       shared_blks_read,
       ROUND(shared_blks_hit::numeric / NULLIF(shared_blks_hit + shared_blks_read, 0) * 100, 2) AS cache_hit_ratio
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
  AND shared_blks_hit + shared_blks_read > 0
ORDER BY cache_hit_ratio ASC
LIMIT 20;

-- 高频率执行查询（执行次数多，即使单次快也可能累积成大问题）
SELECT queryid,
       LEFT(query, 200) AS query_preview,
       calls,
       ROUND(mean_exec_time::numeric, 2) AS avg_ms,
       ROUND(total_exec_time::numeric, 2) AS total_ms
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY calls DESC
LIMIT 20;
```

---

## 三、EXPLAIN ANALYZE 执行计划深度解读

```sql
-- 基础执行计划（仅估算）
EXPLAIN <sql>;

-- 实际执行计划（含真实耗时、缓冲区使用）
EXPLAIN (ANALYZE, BUFFERS) <sql>;

-- 完整 JSON 格式（含成本模型、实际耗时、缓冲区，适合程序化分析）
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <sql>;

-- 带详细信息的执行计划
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON) <sql>;
```

### 执行计划关键字段解读

| 节点类型 | 含义 | 优化提示 |
|----------|------|---------|
| Seq Scan | 全表顺序扫描 | 检查是否缺失索引、统计信息过期、或表太小不需要索引 |
| Index Scan | 索引扫描 + 回表 | 关注 Heap Fetches 数量，回表代价高时考虑覆盖索引 |
| Index Only Scan | 仅索引扫描（覆盖索引） | 最优扫描方式，关注 Heap Fetches 是否因可见性检查导致回表 |
| Bitmap Heap Scan | 位图索引扫描 + 回表 | 多条件过滤时常见，检查是否可改为普通 Index Scan |
| Nested Loop | 嵌套循环连接 | 内表必须有索引，否则性能极差 |
| Hash Join | 哈希连接 | 大表连接，检查 work_mem 是否足够避免磁盘溢出 |
| Merge Join | 归并连接 | 两表均已排序，检查是否有合适索引支持 |
| Sort | 排序操作 | 检查 work_mem，评估是否可通过索引规避排序 |
| HashAggregate | 哈希聚合 | 检查 work_mem |
| Parallel Seq Scan | 并行顺序扫描 | 大表扫描时出现，关注 worker 数量 |

### EXPLAIN 分析要点

| 指标 | 含义 | 关注阈值 |
|------|------|---------|
| `actual time` | 实际启动时间..总耗时（ms） | 占比高的算子即为瓶颈 |
| `rows` (估算) vs `actual rows` | 估算行数与实际行数偏差 | 偏差 > 10x → 统计信息过期 |
| `Buffers: shared hit` | 共享缓冲区命中数 | 越高越好 |
| `Buffers: shared read` | 磁盘读取数 | 高 → 缓存不足或数据量大 |
| `Buffers: temp read/written` | 临时文件读写 | 非零 → work_mem 不足 |
| `Heap Fetches` | 回表次数 (Index Only Scan) | 高 → 表膨胀（autovacuum 不及时） |
| `Planning Time` | 计划时间 | 偏高 → 复杂查询或统计信息问题 |
| `Execution Time` | 执行时间 | 核心关注指标 |

```
节点类型性能排序（扫描方式，优→劣）：
Index Only Scan > Index Scan > Bitmap Index Scan > Bitmap Heap Scan > Parallel Seq Scan > Seq Scan

连接方式选择（因数据量而异，无绝对优劣）：
Nested Loop（小表驱动大表） > Merge Join（已排序） > Hash Join（大表连接）
```

---

## 四、全表扫描与索引使用分析（只读）

```sql
-- 表级扫描统计：顺序扫描 vs 索引扫描
SELECT schemaname,
       relname,
       seq_scan,
       seq_tup_read,
       idx_scan,
       idx_tup_fetch,
       n_tup_ins,
       n_tup_upd,
       n_tup_del,
       n_live_tup,
       n_dead_tup,
       ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_tuple_ratio,
       last_vacuum,
       last_autovacuum,
       last_analyze,
       last_autoanalyze
FROM pg_stat_user_tables
ORDER BY seq_scan DESC
LIMIT 20;

-- 全表扫描占比高但索引扫描少的表（索引缺失或无效）
SELECT schemaname,
       relname,
       seq_scan,
       idx_scan,
       seq_tup_read,
       CASE WHEN idx_scan + seq_scan > 0
            THEN ROUND(seq_scan::numeric / (seq_scan + idx_scan) * 100, 2)
            ELSE 0 END AS seq_scan_ratio
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_scan_ratio DESC;

-- 索引使用率
SELECT schemaname,
       relname,
       indexrelname,
       idx_scan,
       idx_tup_read,
       idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC
LIMIT 20;

-- 未使用的索引（可能为冗余索引，需评估是否删除）
SELECT schemaname,
       relname,
       indexrelname,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indisunique = false
ORDER BY pg_relation_size(indexrelid) DESC;

-- 索引 IO 统计（磁盘读取多说明索引不在缓存中）
SELECT schemaname,
       relname,
       indexrelname,
       idx_blks_read,
       idx_blks_hit,
       ROUND(idx_blks_hit::numeric / NULLIF(idx_blks_hit + idx_blks_read, 0) * 100, 2) AS cache_hit_ratio
FROM pg_statio_user_indexes
ORDER BY idx_blks_read DESC
LIMIT 20;
```

---

## 五、慢查询日志文件解析（只读）

PostgreSQL 慢查询日志通过 `log_min_duration_statement` 参数控制，日志格式由 `log_destination` 和 `log_line_prefix` 决定。

### 日志配置查看（仅查看）

```sql
SHOW log_min_duration_statement;
SHOW log_destination;
SHOW log_directory;
SHOW log_filename;
SHOW log_line_prefix;
SHOW log_statement;
```

### CSV 日志格式解析

PostgreSQL 支持 CSV 格式日志，包含以下关键字段：

| CSV 字段 | 含义 | 分析用途 |
|----------|------|---------|
| `log_time` | 日志时间戳 | 时间维度分析 |
| `user_name` | 用户名 | 按用户分析 |
| `database_name` | 数据库名 | 按库分析 |
| `session_id` | 会话 ID | 关联同一会话 |
| `duration` | 执行耗时（ms） | 核心排序指标 |
| `statement` | SQL 语句 | 慢查询内容 |
| `rows` | 返回行数 | 结果集大小 |
| `application_name` | 应用名称 | 按来源分析 |

```sql
-- 若日志记录在 PostgreSQL 表中（使用 CSV 导入），可直接查询
-- 假设已导入到 slow_log 表
SELECT log_time,
       user_name,
       database_name,
       duration,
       LEFT(statement, 300) AS query_preview,
       rows
FROM slow_log
WHERE duration > 1000
ORDER BY duration DESC
LIMIT 50;
```

### log_min_duration_statement 慢查询日志采样

```sql
-- 查看当前慢查询日志配置
SELECT name, setting, unit, context, boot_val, reset_val
FROM pg_settings
WHERE name IN (
    'log_min_duration_statement',
    'log_duration',
    'log_statement',
    'log_min_duration_sample',
    'log_statement_sample_rate',
    'log_parameter_max_length',
    'log_parameter_max_length_on_error'
)
ORDER BY name;
```

---

## 六、锁等待与慢查询关联分析（只读）

```sql
-- 当前锁等待关系（阻塞链）
SELECT blocked_locks.pid           AS blocked_pid,
       blocked_activity.usename    AS blocked_user,
       blocked_activity.query      AS blocked_query,
       blocking_locks.pid          AS blocking_pid,
       blocking_activity.usename   AS blocking_user,
       blocking_activity.query     AS blocking_query,
       blocked_activity.wait_event_type,
       blocked_activity.wait_event
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity
  ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
  ON blocking_locks.locktype = blocked_locks.locktype
  AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
  AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
  AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
  AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
  AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
  AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
  AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
  AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
  AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
  AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity
  ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- 长时间运行的事务（可能导致锁持有和表膨胀）
SELECT pid,
       usename,
       application_name,
       client_addr,
       state,
       NOW() - xact_start AS xact_duration,
       NOW() - query_start AS query_duration,
       LEFT(query, 200) AS query_preview,
       wait_event_type,
       wait_event
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start IS NOT NULL
  AND NOW() - xact_start > interval '30 seconds'
ORDER BY xact_start;

-- 空闲事务（持有锁但不活动，危险）
SELECT pid,
       usename,
       application_name,
       client_addr,
       state,
       NOW() - state_change AS idle_duration,
       LEFT(query, 200) AS last_query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND NOW() - state_change > interval '5 minutes';
```

---

## 七、auto_explain 与慢查询关联（只读）

`auto_explain` 扩展可自动记录超过阈值的 SQL 执行计划到日志，无需手动 EXPLAIN。

```sql
-- 检查 auto_explain 是否启用
SELECT * FROM pg_extension WHERE extname = 'auto_explain';

-- 查看 auto_explain 配置
SELECT name, setting, unit, context
FROM pg_settings
WHERE name LIKE 'auto_explain%'
ORDER BY name;

-- 关键参数说明
-- auto_explain.log_min_duration  : 自动记录执行计划的最小耗时阈值（-1=禁用）
-- auto_explain.log_analyze       : 是否记录实际执行耗时（类似 EXPLAIN ANALYZE）
-- auto_explain.log_buffers       : 是否记录缓冲区使用
-- auto_explain.log_timing        : 是否记录各节点耗时
-- auto_explain.log_triggers      : 是否记录触发器执行
-- auto_explain.log_verbose       : 是否记录详细信息
-- auto_explain.log_nested_statements : 是否记录嵌套语句
-- auto_explain.sample_rate       : 采样率（0-1）
```

---

## 八、表膨胀与 autovacuum 关联分析（只读）

表膨胀（Bloat）会导致查询走 Seq Scan 时扫描更多页，索引扫描回表代价增大，是慢查询的重要根因之一。

```sql
-- 死元组比例（高死元组比例 → 表膨胀 → 查询变慢）
SELECT schemaname,
       relname,
       n_live_tup,
       n_dead_tup,
       ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_ratio,
       last_autovacuum,
       last_autoanalyze,
       autovacuum_count,
       autoanalyze_count
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY dead_ratio DESC
LIMIT 20;

-- autovacuum 运行状态
SELECT name, setting, unit, context
FROM pg_settings
WHERE name LIKE 'autovacuum%'
  AND name IN (
    'autovacuum',
    'autovacuum_max_workers',
    'autovacuum_naptime',
    'autovacuum_vacuum_threshold',
    'autovacuum_analyze_threshold',
    'autovacuum_vacuum_scale_factor',
    'autovacuum_analyze_scale_factor',
    'autovacuum_vacuum_cost_delay',
    'autovacuum_vacuum_cost_limit'
  )
ORDER BY name;
```

---

## 九、查询优化最佳实践（参考）

| 问题 | 原因 | PostgreSQL 解决方案 |
|------|------|-------------------|
| Seq Scan 大表 | 缺少索引 | 评估为 WHERE/JOIN 列创建索引 |
| 索引未被使用 | 统计信息过期 / 选择性低 | 执行 ANALYZE 刷新统计 / 考虑部分索引 |
| Index Only Scan 有大量 Heap Fetches | 表膨胀，可见性检查需回表 | 执行 VACUUM 清理死元组 |
| Hash Join 溢出到磁盘 | work_mem 不足 | 适当增大 work_mem |
| Sort 溢出到磁盘 | work_mem 不足 | 适当增大 work_mem 或创建排序索引 |
| 前导通配符 LIKE '%xxx' | 无法使用 B-tree 索引 | 使用 pg_trgm GIN 索引 |
| 函数作用于列 WHERE LOWER(col)='x' | 索引失效 | 创建表达式索引 |
| OR 条件多表 | 索引选择困难 | 使用 UNION ALL 拆分 |
| 大偏移分页 LIMIT 100000 OFFSET 1000000 | 需扫描前面所有行 | 使用游标分页（Keyset Pagination） |
| IN 列表过长 | 优化器处理耗时 | 使用临时表 + JOIN |
| DISTINCT 大结果集 | 排序去重 | 用 GROUP BY 替代或确保有合适索引 |
| 统计信息过期 | 执行计划偏差大 | 调优 autovacuum 参数或手动 ANALYZE |
| 锁等待 | 长事务 / 未提交事务 | 定位阻塞源，优化事务逻辑 |

---

## 异常处理
- 单条查询失败不影响整体，标记该维度异常后继续其余查询。
- `pg_stat_statements` 未安装时提示用户启用扩展（本技能不执行 CREATE EXTENSION）。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- `EXPLAIN ANALYZE` 实际执行会消耗资源，仅在用户明确指定 SQL 时执行。
- 本技能仅做只读查询，不执行任何 DDL/DML，单次执行耗时 ≤ 5s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出慢查询 TOP N 列表（含 queryid、平均耗时、执行次数、缓存命中率）
- 执行计划解读（瓶颈算子、估算偏差、缓冲区使用、优化方向）
- 全表扫描与索引使用报告（Seq Scan 占比、未使用索引、索引命中率）
- 锁等待分析报告（阻塞链、长事务、空闲事务）
- 表膨胀与 autovacuum 状态
- 汇总优化建议（按重点排序，标注由哪个专项技能负责执行）