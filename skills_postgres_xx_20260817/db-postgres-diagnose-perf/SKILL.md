---
name: "db-postgres-diagnose-perf"
description: "PostgreSQL 综合性能诊断技能。核心能力：系统资源层（CPU/内存/IO/连接数）与 PostgreSQL 内部指标（缓冲命中率、等待事件、检查点、WAL 吞吐、vacuum 状态、复制延迟、连接池状态）一站式采集，生成多维度性能健康报告，定位性能瓶颈根因并给出优化方向。适用场景：数据库整体性能下降排查、周期性性能抖动诊断、资源瓶颈定位（CPU/IO/内存/连接）、实例健康度巡检。功能限制：本技能仅做只读查询与诊断分析，不调整配置参数、不创建索引、不终止会话、不执行 VACUUM/ANALYZE；配置调优请用 db-postgres-config-tune，慢查询请用 db-postgres-diagnose-slow-query，死锁请用 db-postgres-diagnose-deadlock，索引优化请用 db-postgres-index-design。"
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
  - name: "top_n"
    type: "integer"
    required: false
    default: 10
    desc: "各维度 TOP N 条数"
  - name: "include_system_metrics"
    type: "boolean"
    required: false
    default: true
    desc: "是否采集系统层指标（CPU/内存/IO），需操作系统级访问权限"
  - name: "check_interval_sec"
    type: "integer"
    required: false
    default: 0
    desc: "连续采集间隔秒数（0=单次采集，>0 则采集两次做差值分析，用于趋势判定）"
support_db: postgresql
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# PostgreSQL 综合性能诊断

本技能为只读综合性能诊断技能，一次执行覆盖系统资源层（CPU/内存/IO/连接数）与 PostgreSQL 内部核心指标（缓冲命中率、等待事件、检查点/WAL、vacuum 状态、复制延迟、连接池、查询负载），生成多维度性能健康报告，定位瓶颈并给出优化方向（不执行任何变更）。

---

## 核心能力
- 系统资源层指标采集：CPU 使用率、内存使用、磁盘 IO 吞吐/延迟、网络连接数（通过 PostgreSQL 系统函数与 OS 级视图）
- PostgreSQL 缓冲命中率分析：shared_buffers 命中率、索引缓存命中率
- 等待事件分类统计：按 wait_event_type 聚合当前等待事件分布，识别 IO / Lock / LWLock / CPU 等瓶颈类型
- 检查点与 WAL 分析：检查点频率、WAL 生成速率、WAL 写入延迟
- Vacuum 与 autovacuum 状态：死元组比例、autovacuum worker 运行状态、表膨胀风险
- 连接与会话负载：活跃/空闲/空闲事务连接数、连接使用率、长事务持有者
- 复制状态与延迟：流复制延迟（字节/秒）、WAL 发送/写入/刷新/重放位置
- 查询负载概览：当前活跃查询、长时间运行查询、等待事件分布
- 配置参数合理性检查：关键性能参数（shared_buffers / work_mem / effective_cache_size 等）与资源匹配度

## 适用场景
- 数据库整体性能下降（响应变慢、吞吐降低）的根因定位
- 周期性性能抖动（特定时段变慢）的时序对比诊断
- 资源瓶颈定位：CPU 瓶颈、IO 瓶颈、内存不足、连接数打满
- 实例健康度日常巡检（一键生成多维度健康报告）
- 新实例上线前的性能基线采集
- 大促/流量高峰前的容量评估与性能预检

## 功能限制 / 安全边界
- 不调整 PostgreSQL 配置参数（不执行 ALTER SYSTEM / SET）
- 不创建索引（不执行 CREATE INDEX）
- 不刷新统计信息（不执行 ANALYZE / VACUUM ANALYZE）
- 不终止会话（不执行 pg_terminate_backend / pg_cancel_backend）
- 不安装或启用扩展（不执行 CREATE EXTENSION）
- 不执行任何 DDL/DML
- 不调用其它 Skill、不自动修复、仅按需手动触发
- 系统层指标采集依赖 PostgreSQL 内置函数与系统视图，不调用外部 Agent

---

## 前置检查：确认关键扩展已启用

```sql
-- 检查必要扩展
SELECT extname, extversion 
FROM pg_extension 
WHERE extname IN ('pg_stat_statements', 'pg_buffercache')
ORDER BY extname;

-- 检查 pg_stat_statements 是否在 shared_preload_libraries 中
SHOW shared_preload_libraries;

-- 检查统计收集器是否启用
SELECT name, setting 
FROM pg_settings 
WHERE name IN (
    'track_counts',
    'track_io_timing',
    'track_functions',
    'track_activities'
)
ORDER BY name;
```

| 扩展/参数 | 用途 | 缺失影响 |
|-----------|------|---------|
| `pg_stat_statements` | 查询性能统计 | 无法获取查询级 TOP N 分析 |
| `pg_buffercache` | 缓冲区内容分析 | 无法分析缓冲命中率与缓存分布 |
| `track_io_timing` | IO 耗时统计 | 无法获取块级 IO 延迟 |
| `track_activities` | 会话活动监控 | 无法获取等待事件与当前查询 |

---

## 一、推理框架：PostgreSQL 综合性能诊断链

```
用户报告：数据库变慢 / CPU 高 / IO 高 / 连接数满
    |
    v
[1] 快速概览（30s 内完成）
    | 系统层：CPU/内存/IO 使用率（pg_stat_activity + pg_stat_bgwriter）
    | 数据库层：连接数、活跃查询、等待事件分类
    | 判断瓶颈大类：CPU / IO / 锁 / 连接 / 复制
    v
[2] 按瓶颈方向深入
    | CPU 高 → 活跃查询 SQL 采样 → 等待事件 CPU 类 → 配置参数
    | IO 高  → 缓冲命中率 → 检查点频率 → WAL 生成速率 → 表膨胀
    | 锁等待 → 阻塞链分析 → 长事务 → 空闲事务（详见 db-postgres-diagnose-deadlock）
    | 连接满 → 连接分布 → 空闲连接 → 连接池配置
    | 复制延迟 → WAL 发送/写入/刷新位置差距 → 网络/IO 瓶颈
    v
[3] 生成健康报告
    | 性能评分（按维度打分）
    | 瓶颈根因结论（优先级排序）
    | 优化建议（标注由哪个专项技能负责执行）
```

---

## 二、系统资源层指标（通过 PostgreSQL 内置函数采集）

> 系统层指标依赖 PostgreSQL 可访问的 OS 统计信息，优先使用 `pg_stat_bgwriter`、`pg_stat_database` 等内置视图。

```sql
-- 数据库级统计概览（提交/回滚数、块读写、死锁、临时文件）
SELECT datname,
       numbackends,
       xact_commit,
       xact_rollback,
       ROUND(xact_rollback::numeric / NULLIF(xact_commit + xact_rollback, 0) * 100, 2) AS rollback_ratio,
       blks_read,
       blks_hit,
       ROUND(blks_hit::numeric / NULLIF(blks_hit + blks_read, 0) * 100, 2) AS cache_hit_ratio,
       tup_returned,
       tup_fetched,
       tup_inserted,
       tup_updated,
       tup_deleted,
       conflicts,
       temp_files,
       pg_size_pretty(temp_bytes) AS temp_size,
       deadlocks,
       stats_reset
FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1')
ORDER BY numbackends DESC;
```

```sql
-- 后台写入器统计（检查点、缓冲区写入、分配次数）
SELECT checkpoints_timed,
       checkpoints_req,
       ROUND(checkpoints_req::numeric / NULLIF(checkpoints_timed + checkpoints_req, 0) * 100, 2) AS req_checkpoint_ratio,
       buffers_checkpoint,
       buffers_clean,
       buffers_backend,
       buffers_backend_fsync,
       buffers_alloc,
       maxwritten_clean,
       pg_size_pretty(buffers_checkpoint * 8192) AS checkpoint_write_size,
       pg_size_pretty(buffers_backend * 8192) AS backend_write_size,
       pg_size_pretty(buffers_alloc * 8192) AS alloc_size,
       stats_reset
FROM pg_stat_bgwriter;
```

---

## 三、连接与会话负载分析（只读）

```sql
-- 连接数概览（总数、按状态分布）
SELECT state,
       COUNT(*) AS session_count,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() AS pct
FROM pg_stat_activity
WHERE pid != pg_backend_pid()
GROUP BY state
ORDER BY session_count DESC;

-- 连接总数与最大连接数
SELECT current_setting('max_connections')::int AS max_connections,
       COUNT(*) AS current_connections,
       ROUND(COUNT(*) * 100.0 / current_setting('max_connections')::int, 2) AS usage_pct
FROM pg_stat_activity;

-- 按数据库、用户、应用连接分布
SELECT datname,
       usename,
       application_name,
       COUNT(*) AS connections
FROM pg_stat_activity
WHERE pid != pg_backend_pid()
GROUP BY datname, usename, application_name
ORDER BY connections DESC;

-- 空闲事务（idle in transaction，高危：持有锁但不活动）
SELECT pid,
       usename,
       application_name,
       client_addr,
       state,
       NOW() - state_change AS idle_duration,
       NOW() - xact_start AS xact_duration,
       LEFT(query, 200) AS last_query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND NOW() - state_change > interval '5 minutes'
ORDER BY state_change;

-- 长时间运行的事务（> 30s）
SELECT pid,
       usename,
       application_name,
       state,
       NOW() - xact_start AS xact_duration,
       NOW() - query_start AS query_duration,
       LEFT(query, 300) AS query_preview,
       wait_event_type,
       wait_event
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start IS NOT NULL
  AND NOW() - xact_start > interval '30 seconds'
ORDER BY xact_start;
```

---

## 四、等待事件分类统计（只读）

等待事件是定位性能瓶颈的核心指标，PostgreSQL 将等待事件分为以下类别：

| wait_event_type | 含义 | 瓶颈方向 |
|-----------------|------|---------|
| `LWLock` | 轻量级锁等待（内存结构互斥） | CPU / 并发竞争 |
| `Lock` | 重量级锁等待（表/行/事务锁） | 锁竞争（详见死锁诊断技能） |
| `BufferPin` | 缓冲区页固定等待 | IO / 并发访问 |
| `Activity` | 后台进程活动等待 | 内部进程协调 |
| `Client` | 等待客户端发送数据 | 应用层/网络 |
| `Extension` | 扩展相关等待 | 第三方扩展 |
| `IPC` | 进程间通信等待 | 并发/同步 |
| `IO` | IO 操作等待 | 磁盘 IO 瓶颈 |
| `Timeout` | 超时等待 | 锁/空闲超时 |
| `CPU` | CPU 相关等待 | CPU 瓶颈 |

```sql
-- 当前等待事件分布（按 wait_event_type 分类）
SELECT COALESCE(wait_event_type, 'CPU') AS wait_type,
       wait_event,
       COUNT(*) AS session_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct
FROM pg_stat_activity
WHERE pid != pg_backend_pid()
  AND state != 'idle'
GROUP BY wait_event_type, wait_event
ORDER BY session_count DESC;

-- 按等待类别汇总
SELECT COALESCE(wait_event_type, 'CPU') AS wait_category,
       COUNT(*) AS session_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct
FROM pg_stat_activity
WHERE pid != pg_backend_pid()
  AND state != 'idle'
GROUP BY wait_event_type
ORDER BY session_count DESC;
```

---

## 五、缓冲命中率分析（只读）

缓冲命中率是衡量内存配置是否合理的核心指标，命中率低意味着 IO 瓶颈。

```sql
-- 全局缓冲命中率
SELECT ROUND(SUM(blks_hit) * 100.0 / NULLIF(SUM(blks_hit) + SUM(blks_read), 0), 2) AS global_cache_hit_ratio
FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1');

-- 按数据库缓冲命中率（低于 95% 需关注）
SELECT datname,
       blks_hit,
       blks_read,
       ROUND(blks_hit::numeric / NULLIF(blks_hit + blks_read, 0) * 100, 2) AS cache_hit_ratio
FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1')
  AND blks_hit + blks_read > 0
ORDER BY cache_hit_ratio ASC;

-- 索引缓冲命中率（按表）
SELECT schemaname,
       relname,
       indexrelname,
       idx_blks_read,
       idx_blks_hit,
       ROUND(idx_blks_hit::numeric / NULLIF(idx_blks_hit + idx_blks_read, 0) * 100, 2) AS idx_cache_hit_ratio
FROM pg_statio_user_indexes
WHERE idx_blks_hit + idx_blks_read > 0
ORDER BY idx_cache_hit_ratio ASC
LIMIT 20;
```

```sql
-- pg_buffercache 分析（若扩展已启用）
-- 按表查看缓冲区占用分布
SELECT c.relname,
       COUNT(*) AS buffers,
       pg_size_pretty(COUNT(*) * 8192) AS buffer_size,
       ROUND(COUNT(*) * 100.0 / (SELECT setting::int FROM pg_settings WHERE name = 'shared_buffers'), 2) AS shared_buffers_pct
FROM pg_buffercache b
JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid)
JOIN pg_database d ON b.reldatabase = d.oid
WHERE d.datname = current_database()
GROUP BY c.relname
ORDER BY buffers DESC
LIMIT 20;
```

---

## 六、检查点与 WAL 分析（只读）

检查点频率过高或 WAL 生成速率过快都会导致 IO 瓶颈。

```sql
-- 检查点统计（两次采集做差值分析）
-- 若 check_interval_sec > 0，间隔后再次采集计算差值
SELECT checkpoints_timed,
       checkpoints_req,
       ROUND(checkpoints_req::numeric / NULLIF(checkpoints_timed + checkpoints_req, 0) * 100, 2) AS req_checkpoint_ratio,
       buffers_checkpoint,
       buffers_clean,
       buffers_backend,
       buffers_backend_fsync
FROM pg_stat_bgwriter;

-- 检查点相关配置
SELECT name, setting, unit, context, boot_val
FROM pg_settings
WHERE name IN (
    'checkpoint_timeout',
    'min_wal_size',
    'max_wal_size',
    'checkpoint_completion_target',
    'checkpoint_flush_after',
    'checkpoint_warning',
    'wal_buffers'
)
ORDER BY name;

-- WAL 当前写入位置与速率
SELECT pg_current_wal_lsn() AS current_wal_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0') AS wal_bytes_since_start,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) AS wal_size;

-- WAL 归档状态（若启用 archive_mode）
SELECT archived_count,
       failed_count,
       last_archived_wal,
       last_archived_time,
       ROUND(failed_count::numeric / NULLIF(archived_count + failed_count, 0) * 100, 2) AS archive_fail_ratio
FROM pg_stat_archiver;
```

---

## 七、Vacuum 与 autovacuum 状态（只读）

```sql
-- 死元组比例 TOP N（高死元组比例 → 表膨胀 → 查询变慢）
SELECT schemaname,
       relname,
       n_live_tup,
       n_dead_tup,
       ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_ratio,
       n_mod_since_analyze,
       last_vacuum,
       last_autovacuum,
       last_analyze,
       last_autoanalyze,
       vacuum_count,
       autovacuum_count,
       analyze_count,
       autoanalyze_count
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY dead_ratio DESC
LIMIT 20;

-- autovacuum 配置
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
    'autovacuum_vacuum_cost_limit',
    'autovacuum_freeze_max_age',
    'autovacuum_multixact_freeze_max_age'
  )
ORDER BY name;

-- 当前 autovacuum worker 活动
SELECT pid,
       datname,
       relid::regclass AS table_name,
       phase,
       heap_blks_total,
       heap_blks_scanned,
       heap_blks_vacuumed,
       index_vacuum_count,
       max_dead_tuples,
       num_dead_tuples
FROM pg_stat_progress_vacuum;
```

---

## 八、复制状态与延迟（只读）

```sql
-- 流复制状态（在主库执行）
SELECT application_name,
       client_addr,
       state,
       sync_state,
       pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS send_lag_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(), write_lsn) AS write_lag_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn) AS flush_lag_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) AS replay_lag,
       write_lag,
       flush_lag,
       replay_lag,
       reply_time
FROM pg_stat_replication;

-- 复制槽状态（逻辑复制）
SELECT slot_name,
       slot_type,
       database,
       active,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS retained_wal_bytes,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained_wal_size,
       restart_lsn,
       confirmed_flush_lsn
FROM pg_replication_slots;
```

---

## 九、查询负载概览（只读）

```sql
-- 当前活跃查询（不含本会话）
SELECT pid,
       usename,
       datname,
       application_name,
       client_addr,
       state,
       NOW() - query_start AS query_duration,
       wait_event_type,
       wait_event,
       LEFT(query, 300) AS query_preview
FROM pg_stat_activity
WHERE state = 'active'
  AND pid != pg_backend_pid()
ORDER BY query_start;

-- 当前活跃查询数
SELECT COUNT(*) AS active_queries
FROM pg_stat_activity
WHERE state = 'active'
  AND pid != pg_backend_pid();

-- 查询负载（pg_stat_statements，若已启用）
SELECT queryid,
       LEFT(query, 200) AS query_preview,
       calls,
       ROUND(mean_exec_time::numeric, 2) AS avg_ms,
       ROUND(total_exec_time::numeric, 2) AS total_ms,
       ROUND(stddev_exec_time::numeric, 2) AS stddev_ms,
       shared_blks_hit,
       shared_blks_read,
       ROUND(shared_blks_hit::numeric / NULLIF(shared_blks_hit + shared_blks_read, 0) * 100, 2) AS cache_hit_ratio
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
  AND query !~* '(pg_stat|pg_catalog|information_schema)'
ORDER BY total_exec_time DESC
LIMIT 20;
```

---

## 十、关键配置参数合理性检查（只读）

```sql
-- 内存相关
SELECT name, setting, unit, context, boot_val
FROM pg_settings
WHERE name IN (
    'shared_buffers',
    'effective_cache_size',
    'work_mem',
    'maintenance_work_mem',
    'wal_buffers',
    'huge_pages',
    'autovacuum_work_mem',
    'hash_mem_multiplier'
)
ORDER BY name;

-- 计划器相关
SELECT name, setting, unit, context
FROM pg_settings
WHERE name IN (
    'random_page_cost',
    'seq_page_cost',
    'effective_io_concurrency',
    'max_worker_processes',
    'max_parallel_workers',
    'max_parallel_workers_per_gather',
    'max_parallel_maintenance_workers',
    'parallel_tuple_cost',
    'parallel_setup_cost',
    'jit'
)
ORDER BY name;

-- 系统资源总量（用于配置合理性对比）
SELECT 'OS Total Memory' AS resource,
       pg_size_pretty(total_memory_bytes) AS value
FROM (
    SELECT setting::bigint * 1024 AS total_memory_bytes
    FROM pg_settings
    WHERE name = 'shared_buffers'
    LIMIT 1
) _;
-- 注意：PostgreSQL 内无法直接获取 OS 总内存，需结合 pg_stat_activity 与 OS 命令
-- 若 shared_buffers < OS 总内存的 25%，建议调大（本技能不执行，仅提示）
```

| 参数 | 建议值 | 含义 |
|------|--------|------|
| `shared_buffers` | OS 总内存的 25%-40% | 共享缓冲区大小 |
| `effective_cache_size` | OS 总内存的 50%-75% | 查询计划器估算的 OS 缓存大小 |
| `work_mem` | 按并发查询数调优（总内存 / (4 * max_connections)） | 单操作排序/哈希内存 |
| `maintenance_work_mem` | OS 总内存的 5%-10%（上限 1GB-2GB） | VACUUM/CREATE INDEX 内存 |
| `wal_buffers` | shared_buffers 的 1/32（默认 -1 自动） | WAL 缓冲区 |
| `random_page_cost` | SSD: 1.0-1.5 / HDD: 4.0 | 随机页访问代价 |
| `effective_io_concurrency` | SSD: 200 / HDD: 2 | 并发 IO 请求数 |

---

## 十一、差值采集模式（趋势分析）

当 `check_interval_sec > 0` 时，两次采集后计算差值，用于判定性能趋势。

```sql
-- 第一次采集（T0 时刻）
-- 记录 pg_stat_bgwriter、pg_stat_database、pg_stat_statements 指标快照

-- 间隔 check_interval_sec 秒后第二次采集（T1 时刻）

-- 趋势指标计算：
-- 缓冲命中率变化 = T1.cache_hit_ratio - T0.cache_hit_ratio
-- 检查点频率 = (T1.checkpoints - T0.checkpoints) / interval_sec
-- WAL 生成速率 = (T1.wal_bytes - T0.wal_bytes) / interval_sec
-- 死元组增长率 = (T1.dead_tuples - T0.dead_tuples) / interval_sec
-- 连接数变化 = T1.connections - T0.connections
-- 事务回滚率变化 = T1.rollback_ratio - T0.rollback_ratio
```

---

## 十二、常见性能瓶颈模式与诊断

| 瓶颈类型 | 典型表现 | 关键指标 | 诊断方向 |
|----------|---------|---------|---------|
| CPU 瓶颈 | 活跃查询多、等待事件 CPU 类占比高 | 活跃连接数高、等待事件集中在 CPU/LWLock | 检查慢查询、高并发短查询、并行度配置 |
| IO 瓶颈 | 缓冲命中率低、IO 等待事件占比高 | cache_hit_ratio < 95%、checkpoint_req 占比高、temp_files 多 | 增大 shared_buffers、优化检查点参数、表膨胀排查 |
| 内存不足 | work_mem 溢出到磁盘、临时文件多 | temp_files/temp_bytes 高、排序/哈希溢出 | 调大 work_mem、优化查询避免大排序 |
| 连接数打满 | 连接数接近 max_connections | current_connections > 80% max_connections | 检查空闲连接、连接池配置、idle in transaction |
| 锁竞争 | Lock 等待事件占比高、事务回滚率高 | wait_event_type = Lock、xact_rollback 比例高 | 详见 db-postgres-diagnose-deadlock |
| 表膨胀 | 死元组比例高、autovacuum 跟不上 | dead_ratio > 20%、autovacuum 延迟 | 调优 autovacuum 参数、表膨胀排查 |
| 复制延迟 | replay_lag 持续增长 | replay_lag_bytes > 100MB 或持续增长 | 检查网络、备库 IO、复制槽积压 |
| WAL 压力 | 检查点频率高、WAL 生成速率快 | req_checkpoint_ratio > 30%、大量写入 | 增大 max_wal_size、调优 checkpoint_timeout |

---

## 异常处理
- 单条查询失败不影响整体，标记该维度异常后继续其余查询。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- `pg_stat_statements` 未安装时跳过查询负载分析，提示用户启用扩展。
- `pg_buffercache` 未安装时跳过缓冲区分布分析，仅使用 pg_statio_* 视图。
- 无活跃查询时输出"当前无活跃查询"，不输出空结果。
- 差值采集模式下，两次采集之间连接中断则输出已采集的部分数据并标注异常。
- 本技能仅做只读查询，单次执行耗时 ≤ 10s（差值采集 ≤ 30s），无第三方依赖、无常驻逻辑。

## 输出格式
- 性能健康评分总览（按维度打分：缓冲命中率、连接使用率、等待事件分布、死元组比例、复制延迟、检查点健康度）
- 系统资源层概览（连接数/缓冲命中率/事务吞吐/临时文件）
- 等待事件分类分布（饼图数据：各类等待事件占比）
- 瓶颈根因结论（按优先级排序，标注严重程度）
- 缓冲命中率明细（数据库级、索引级）
- 检查点与 WAL 状态（检查点频率、WAL 生成速率、归档状态）
- Vacuum 与表膨胀风险报告（死元组 TOP N 表）
- 复制延迟报告（主备延迟量、复制槽状态）
- 关键配置参数合理性评估（与当前资源对比）
- 优化建议（按优先级排序，标注由哪个专项技能负责执行）