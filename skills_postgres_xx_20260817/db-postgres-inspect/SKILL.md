---
name: "db-postgres-inspect"
description: "PostgreSQL 基础巡检与健康检查技能（只读）。核心能力：12 维度健康指标采集（连接、缓冲命中、锁等待、长事务、空闲事务、死锁、复制延迟、慢查询、死元组、检查点、WAL 归档、磁盘使用）并对照统一阈值表分级评估（ok/warning/critical），输出结构化巡检报告（Markdown/HTML）。适用场景：实例健康巡检、交付前检查、周期性健康评估、异常项快速定位。功能限制：不执行任何写操作、不修改配置参数、不执行自动修复脚本、自包含、单一职责、不终止会话，仅采集与报告。"
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
    desc: "目标数据库名（可选，不填则巡检所有数据库）"
  - name: "report_format"
    type: "string"
    required: false
    default: "markdown"
    desc: "报告格式：markdown/html（可选）"
  - name: "top_n"
    type: "integer"
    required: false
    default: 10
    desc: "各维度 TOP N 条数"
support_db: postgresql
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-18"
---

# PostgreSQL 基础巡检与健康检查

> 以只读方式对 PostgreSQL 实例执行多维度健康巡检：采集健康指标、对照统一阈值表分级评估、输出结构化报告。本技能不修改任何数据或配置，自包含。

## 核心能力
- 单一职责：基础巡检 + 报告。采集 12 维度指标，与统一阈值表比对，输出 ok/warning/critical 分级报告。
- 12 维度覆盖：连接使用率、缓冲命中率、锁等待、长事务、空闲事务、死锁、复制延迟、慢查询、死元组比例、检查点健康度、WAL 归档、磁盘使用。

## 适用场景
- 实例健康巡检、交付前检查、周期性健康评估、异常项快速定位。

## 功能限制 / 安全边界
- 不执行任何写操作（INSERT/UPDATE/DELETE/DDL）、不修改配置参数、不执行自动修复脚本。
- 自包含、单一职责，不终止（KILL）会话；仅按需手动触发，单次执行耗时 ≤ 5s。
- 单条采集失败不影响整体，该维度标记 unknown 后继续；异常时返回结构化提示，不泄露原始报错栈。
- 不调用其它 Skill、不自动修复。

## 执行逻辑
1. 连接目标实例（连接失败则记录并跳过，不抛出原始异常栈）。
2. 执行 12 维度只读采集（见下方 SQL）。
3. 逐项对照统一阈值表评估状态：ok / warning / critical / unknown。
4. 按 report_format 输出 Markdown 或 HTML 报告（HTML 仅本地渲染，不引用任何外部资源）。

---

## 前置检查：确认关键扩展与配置

```sql
-- 检查 pg_stat_statements 扩展（用于慢查询统计）
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'pg_stat_statements';

-- 检查统计收集器是否启用
SELECT name, setting
FROM pg_settings
WHERE name IN (
    'track_counts',
    'track_io_timing',
    'track_activities'
)
ORDER BY name;
```

| 扩展/参数 | 用途 | 缺失影响 |
|-----------|------|---------|
| `pg_stat_statements` | 查询性能统计 | 慢查询维度仅统计当前活跃查询，无法获取历史 TOP N |
| `track_counts` | 表/索引访问统计 | 缓冲命中率维度不完整 |
| `track_activities` | 会话活动监控 | 无法获取等待事件与连接状态 |

---

## 12 维度巡检采集 SQL

### 1. 连接使用率

```sql
SELECT
    COUNT(*) AS current_connections,
    current_setting('max_connections')::int AS max_connections,
    ROUND(COUNT(*) * 100.0 / current_setting('max_connections')::int, 2) AS usage_pct
FROM pg_stat_activity;
```

### 2. 缓冲命中率

```sql
SELECT
    datname,
    blks_hit,
    blks_read,
    ROUND(blks_hit::numeric / NULLIF(blks_hit + blks_read, 0) * 100, 2) AS cache_hit_ratio
FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1')
  AND blks_hit + blks_read > 0
ORDER BY cache_hit_ratio ASC;
```

### 3. 锁等待数

```sql
SELECT COUNT(*) AS lock_wait_count
FROM pg_stat_activity
WHERE wait_event_type = 'Lock'
  AND state != 'idle'
  AND pid != pg_backend_pid();
```

### 4. 长事务数（超过 60 秒）

```sql
SELECT COUNT(*) AS long_trx_count
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start IS NOT NULL
  AND NOW() - xact_start > interval '60 seconds'
  AND pid != pg_backend_pid();
```

### 5. 空闲事务数（idle in transaction，超过 5 分钟）

```sql
SELECT COUNT(*) AS idle_in_trx_count
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND NOW() - state_change > interval '5 minutes'
  AND pid != pg_backend_pid();
```

### 6. 死锁次数

```sql
SELECT SUM(deadlocks) AS deadlock_count
FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1');
```

### 7. 复制延迟（主库执行）

```sql
SELECT
    application_name,
    client_addr,
    state,
    sync_state,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) AS replay_lag,
    replay_lag AS replay_lag_time
FROM pg_stat_replication;
```

### 8. 慢查询 TOP N（依赖 pg_stat_statements）

```sql
SELECT
    queryid,
    LEFT(query, 200) AS query_preview,
    calls,
    ROUND(mean_exec_time::numeric, 2) AS avg_ms,
    ROUND(total_exec_time::numeric, 2) AS total_ms,
    ROUND(max_exec_time::numeric, 2) AS max_ms
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
  AND query !~* '(pg_stat|pg_catalog|information_schema)'
ORDER BY mean_exec_time DESC
LIMIT 20;
```

### 9. 死元组比例 TOP N（表膨胀风险）

```sql
SELECT
    schemaname,
    relname,
    n_live_tup,
    n_dead_tup,
    ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_ratio,
    last_autovacuum,
    last_autoanalyze,
    autovacuum_count
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY dead_ratio DESC
LIMIT 20;
```

### 10. 检查点健康度

```sql
SELECT
    checkpoints_timed,
    checkpoints_req,
    ROUND(checkpoints_req::numeric / NULLIF(checkpoints_timed + checkpoints_req, 0) * 100, 2) AS req_checkpoint_ratio,
    buffers_checkpoint,
    buffers_clean,
    buffers_backend,
    buffers_backend_fsync
FROM pg_stat_bgwriter;
```

### 11. WAL 归档状态

```sql
SELECT
    archived_count,
    failed_count,
    last_archived_wal,
    last_archived_time,
    ROUND(failed_count::numeric / NULLIF(archived_count + failed_count, 0) * 100, 2) AS archive_fail_ratio
FROM pg_stat_archiver;
```

### 12. 磁盘使用

```sql
SELECT
    datname,
    pg_size_pretty(pg_database_size(datname)) AS db_size,
    pg_database_size(datname) AS db_size_bytes
FROM pg_database
WHERE datname NOT IN ('template0', 'template1')
ORDER BY pg_database_size(datname) DESC;

-- 表空间使用率（若有关键表空间）
SELECT
    spcname,
    pg_size_pretty(pg_tablespace_size(spcname)) AS size
FROM pg_tablespace;
```

---

## 统一阈值评估表（唯一权威，全部维度按此判定）

| 检查项 | 警告阈值 (warning) | 严重阈值 (critical) | 评估方向 |
|--------|--------------------|----------------------|---------|
| 连接使用率 | 70% | 85% | 越高越危险 |
| 缓冲命中率 | 95% | 90% | 越低越危险 |
| 锁等待数 | 1 | 5 | 越高越危险 |
| 长事务数 | 1 | 3 | 越高越危险 |
| 空闲事务数 | 1 | 3 | 越高越危险 |
| 死锁次数 | 1 | 5 | 越高越危险 |
| 复制延迟(字节) | 100MB | 1GB | 越高越危险 |
| 慢查询(avg_ms) | 1000ms | 5000ms | 越高越危险 |
| 死元组比例 | 10% | 20% | 越高越危险 |
| 请求检查点占比 | 30% | 60% | 越高越危险 |
| WAL 归档失败率 | 10% | 30% | 越高越危险 |
| 磁盘使用率 | 70% | 85% | 越高越危险 |

---

## 报告输出模板

```text
# PostgreSQL 巡检报告
> 实例: {instance_host} | 数据库: {db_name} | 时间: {timestamp}
> 概览: 共检查 N 项 | 严重 X 项 | 警告 Y 项 | 正常 Z 项 | 未知 U 项

## 巡检得分
| 维度 | 得分 | 状态 |
|------|------|------|
| 连接使用率 | 92/100 | ok |
| 缓冲命中率 | 98/100 | ok |
| ... | ... | ... |

## 巡检明细
| 检查项 | 当前值 | 状态 | 阈值 |
|--------|--------|------|------|
| 连接使用率 | 45% | ok | 警告>70% 严重>85% |
| 缓冲命中率 | 99.2% | ok | 警告<95% 严重<90% |
| 锁等待数 | 12 | critical | 警告>1 严重>5 |
| ... | ... | ... | ... |

## 异常详情
### critical 项
- **锁等待数**: 当前 12，严重阈值 >5。建议使用 db-postgres-diagnose-deadlock 排查阻塞链。

### warning 项
- **死元组比例**: 表 public.orders 死元组比例 12.5%，警告阈值 >10%。建议关注 autovacuum 状态，或使用 db-postgres-diagnose-perf 深入分析。

## 建议
- critical 项：列出当前值与严重阈值，提示需立即处理，标注由哪个专项技能负责执行
- warning 项：列出当前值与警告阈值，提示建议关注，标注由哪个专项技能负责执行
```

---

## 异常处理
- 单条采集 SQL 失败不影响整体，该维度标记 unknown 后继续其余采集。
- 实例连接失败整体返回明确的连接错误信息，不输出数据库原始异常堆栈。
- `pg_stat_statements` 未安装时，慢查询维度仅统计当前活跃查询，标记为降级模式。
- 非主库执行复制延迟采集时，该维度标记 N/A 并说明"请在主库执行"。
- 所有输出均为结构化文本，不引用外部资源，单次执行耗时 ≤ 5s。

## 输出格式
- 巡检概览：维度总数、严重/警告/正常/未知项计数
- 巡检得分：按维度 0-100 打分，直观展示健康度
- 巡检明细表：每项当前值、状态、阈值对照
- 异常详情：critical 和 warning 项展开说明，标注建议处理方向
- 关联技能推荐：按异常项推荐对应的专项技能（如 db-postgres-diagnose-deadlock、db-postgres-diagnose-perf 等）