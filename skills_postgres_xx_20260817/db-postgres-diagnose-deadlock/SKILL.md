---
name: "db-postgres-diagnose-deadlock"
description: "PostgreSQL 死锁诊断分析技能。核心能力：pg_locks 锁等待关系分析、阻塞链检测（谁阻塞了谁）、死锁日志解析（log_lock_waits / deadlock_timeout）、锁模式冲突矩阵推演、事务隔离级别与锁升级分析、咨询锁（advisory lock）死锁排查。适用场景：死锁发生后根因分析与日志回溯、高并发下锁等待阻塞链排查、DDL 与 DML 互锁诊断、应用层咨询锁冲突排查。功能限制：本技能仅做只读查询与日志分析，不 KILL 会话、不终止事务、不修改隔离级别与锁参数；事务终止请用 db-postgres-session-manage。"
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
  - name: "log_file_path"
    type: "string"
    required: false
    default: ""
    desc: "PostgreSQL 日志文件路径（可选，用于从日志中解析死锁详情）"
  - name: "min_duration_sec"
    type: "integer"
    required: false
    default: 5
    desc: "锁等待最小持续时间阈值（秒）"
  - name: "deadlock_log_lines"
    type: "integer"
    required: false
    default: 200
    desc: "从日志文件尾部读取的行数"
support_db: postgresql
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# PostgreSQL 死锁诊断分析

本技能为只读死锁诊断技能，基于 `pg_locks`、`pg_stat_activity`、PostgreSQL 死锁日志、锁模式冲突矩阵，定位死锁根因与锁等待阻塞链，给出预防建议（不执行任何变更）。

---

## 核心能力
- 实时锁等待关系分析（`pg_locks` + `pg_stat_activity` 关联查询）
- 阻塞链检测：从被阻塞会话向上追溯所有阻塞源，输出完整阻塞树
- 死锁日志解析：从 PostgreSQL 日志文件中提取死锁详情
- 锁模式冲突矩阵推演：根据持有锁与请求锁的模式判定是否冲突
- 事务隔离级别与锁升级分析
- 咨询锁（advisory lock）死锁排查
- 长事务 / 空闲事务持有锁排查

## 适用场景
- 发生死锁后的根因分析与日志回溯
- 高并发下锁等待 / 阻塞链排查（应用响应慢、请求堆积）
- DDL（ALTER TABLE 等）与 DML 互锁诊断
- 应用层咨询锁（pg_advisory_lock）冲突排查
- 长事务未提交导致锁持有累积
- 空闲事务（idle in transaction）持有锁排查

## 功能限制 / 安全边界
- 不终止会话（不执行 `pg_terminate_backend` / `pg_cancel_backend`）
- 不 KILL 事务 / 连接
- 不修改隔离级别（不执行 `SET TRANSACTION ISOLATION LEVEL`）
- 不调整锁相关参数（不执行 `ALTER SYSTEM SET deadlock_timeout` 等）
- 不修改 `log_lock_waits` 等日志配置
- 不调用其它 Skill、不自动修复、仅按需手动触发

---

## 前置检查：确认锁日志配置

```sql
SELECT name, setting, unit, context, boot_val, reset_val
FROM pg_settings
WHERE name IN (
    'log_lock_waits',
    'deadlock_timeout',
    'lock_timeout',
    'max_locks_per_transaction'
)
ORDER BY name;
```

| 参数 | 含义 | 建议值 |
|------|------|--------|
| `log_lock_waits` | 是否记录锁等待超过 deadlock_timeout 的事件到日志 | on（推荐开启） |
| `deadlock_timeout` | 死锁检测间隔（默认 1s） | 1s-5s |
| `lock_timeout` | 语句等待锁的超时时间（默认 0=不超时） | 按业务设定 |
| `max_locks_per_transaction` | 每个事务平均锁槽位数 | 默认 64 |

---

## 一、推理框架：PostgreSQL 死锁诊断链

```
用户报告：应用报错 deadlock / 请求卡住 / 响应慢
    |
    v
[1] 检查当前锁等待状态
    | pg_locks WHERE NOT granted → 当前等待锁
    | pg_stat_activity wait_event → Lock/transactionid / Lock/relation 等
    v
[2] 构建阻塞链
    | 从被阻塞 pid 向上追溯 → 谁持有目标锁 → 继续追溯 → 直到根阻塞源
    | 输出阻塞树 / 阻塞链
    v
[3] 判定死锁类型
    | 环形等待（T1 等 T2，T2 等 T1）→ 已被 PostgreSQL 自动检测并回滚一方
    | 长事务持有锁 → 其他事务排队等待 → 非死锁但类似效果
    | DDL 等 AccessExclusiveLock → 阻塞所有读写
    | 咨询锁冲突 → 应用层逻辑死锁
    v
[4] 日志回溯
    | 从 PostgreSQL 日志中搜索 "deadlock" / "waits for" / "blocked by"
    | 提取死锁详情：涉及进程、SQL、锁模式、等待链
    v
[5] 给出根因结论与预防建议（参考，不执行）
```

---

## 二、当前锁等待与阻塞链检测（只读）

### 2.1 锁等待概览

```sql
SELECT
    a.pid, a.usename, a.application_name, a.client_addr,
    a.state, a.wait_event_type, a.wait_event,
    NOW() - a.query_start AS query_wait_duration,
    NOW() - a.xact_start AS xact_duration,
    LEFT(a.query, 200) AS waiting_query
FROM pg_stat_activity a
WHERE a.wait_event_type = 'Lock'
  AND a.pid != pg_backend_pid()
ORDER BY a.query_start;
```

### 2.2 阻塞链检测（核心查询）

```sql
WITH RECURSIVE lock_chain AS (
    SELECT
        blocked.pid AS blocked_pid,
        blocked.usename AS blocked_user,
        blocked.query AS blocked_query,
        blocked.wait_event_type AS blocked_wait_type,
        blocked.wait_event AS blocked_wait_event,
        NOW() - blocked.query_start AS blocked_wait_duration,
        blocking.pid AS blocking_pid,
        blocking.usename AS blocking_user,
        blocking.query AS blocking_query,
        blocking.state AS blocking_state,
        NOW() - blocking.xact_start AS blocking_xact_duration,
        blocked_locks.locktype,
        blocked_locks.relation::regclass AS locked_relation,
        blocked_locks.mode AS requested_mode,
        blocked_locks.granted AS blocked_granted,
        1 AS level
    FROM pg_catalog.pg_locks blocked_locks
    JOIN pg_catalog.pg_stat_activity blocked
        ON blocked.pid = blocked_locks.pid
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
    JOIN pg_catalog.pg_stat_activity blocking
        ON blocking.pid = blocking_locks.pid
    WHERE NOT blocked_locks.granted
      AND blocked.pid != pg_backend_pid()
)
SELECT * FROM lock_chain
ORDER BY level, blocked_wait_duration DESC;
```

### 2.3 锁模式冲突矩阵解读

| 锁模式 | 缩写 | 典型操作 | 冲突说明 |
|--------|------|---------|---------|
| AccessShareLock | AS | SELECT | 仅与 AccessExclusiveLock 冲突 |
| RowShareLock | RS | SELECT FOR UPDATE/SHARE | 与 ExclusiveLock、AccessExclusiveLock 冲突 |
| RowExclusiveLock | RE | INSERT/UPDATE/DELETE | 与 ShareLock、ShareRowExclusiveLock、ExclusiveLock、AccessExclusiveLock 冲突 |
| ShareUpdateExclusiveLock | SUE | VACUUM/ANALYZE/CREATE INDEX CONCURRENTLY | 与 SUE、ShareLock、SRE、ExclusiveLock、AccessExclusiveLock 冲突 |
| ShareLock | S | CREATE INDEX（非 CONCURRENTLY） | 与 RE、SUE、SRE、ExclusiveLock、AccessExclusiveLock 冲突 |
| ShareRowExclusiveLock | SRE | CREATE TRIGGER / ALTER TABLE 部分操作 | 与 RE、SUE、S、SRE、ExclusiveLock、AccessExclusiveLock 冲突 |
| ExclusiveLock | E | 某些 ALTER TABLE 操作 | 与 RS、RE、SUE、S、SRE、E、AccessExclusiveLock 冲突 |
| AccessExclusiveLock | AE | DROP TABLE/TRUNCATE/ALTER TABLE/REINDEX | 与所有锁模式冲突 |

---

## 三、死锁日志解析

典型死锁日志格式：
```
ERROR:  deadlock detected
DETAIL:  Process 12345 waits for ShareLock on transaction 67890; blocked by process 12346.
Process 12346 waits for ShareLock on transaction 67891; blocked by process 12345.
HINT:  See server log for query details.
CONTEXT:  while updating tuple (0,5) in relation "orders"
```

| 日志字段 | 提取内容 | 分析用途 |
|----------|---------|---------|
| `Process <pid>` | 涉及死锁的进程 ID | 关联 `pg_stat_activity` |
| `waits for <lockmode> on transaction <xid>` | 等待的锁类型和事务 ID | 判定锁冲突类型 |
| `blocked by process <pid>` | 阻塞源进程 ID | 构建等待环 |
| `while updating tuple` | 触发死锁的元组位置 | 定位具体行 |
| `relation "<table>"` | 涉及的表名 | 定位冲突对象 |

---

## 四、长事务与空闲事务持有锁排查（只读）

```sql
-- 长时间运行的事务（持有锁未释放）
SELECT
    pid, usename, application_name, client_addr, state,
    NOW() - xact_start AS xact_duration,
    NOW() - query_start AS query_duration,
    LEFT(query, 300) AS query_preview,
    wait_event_type, wait_event, backend_start
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start IS NOT NULL
  AND NOW() - xact_start > interval '30 seconds'
ORDER BY xact_start;

-- 空闲事务（idle in transaction，持有锁但不活动，高危）
SELECT
    pid, usename, application_name, client_addr, state,
    NOW() - state_change AS idle_duration,
    NOW() - xact_start AS xact_duration,
    LEFT(query, 300) AS last_query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND NOW() - state_change > interval '5 minutes'
ORDER BY state_change;

-- 查看长事务持有的锁
SELECT
    a.pid, a.usename, a.state,
    NOW() - a.xact_start AS xact_duration,
    l.locktype, l.relation::regclass AS locked_object, l.mode, l.granted
FROM pg_stat_activity a
JOIN pg_locks l ON a.pid = l.pid
WHERE a.xact_start IS NOT NULL
  AND NOW() - a.xact_start > interval '30 seconds'
  AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY a.xact_start, l.mode;
```

---

## 五、DDL 与 DML 互锁诊断（只读）

```sql
SELECT
    blocking.pid AS ddl_pid,
    blocking.usename AS ddl_user,
    LEFT(blocking.query, 200) AS ddl_query,
    NOW() - blocking.query_start AS ddl_duration,
    COUNT(DISTINCT blocked.pid) AS blocked_session_count,
    STRING_AGG(DISTINCT blocked.pid::text, ', ') AS blocked_pids
FROM pg_locks ddl_lock
JOIN pg_stat_activity blocking
    ON blocking.pid = ddl_lock.pid
JOIN pg_locks blocked_lock
    ON blocked_lock.relation = ddl_lock.relation
    AND blocked_lock.pid != ddl_lock.pid
    AND NOT blocked_lock.granted
JOIN pg_stat_activity blocked
    ON blocked.pid = blocked_lock.pid
WHERE ddl_lock.mode = 'AccessExclusiveLock'
  AND ddl_lock.granted
  AND ddl_lock.database = (SELECT oid FROM pg_database WHERE datname = current_database())
GROUP BY blocking.pid, blocking.usename, blocking.query, blocking.query_start
ORDER BY ddl_duration DESC;
```

---

## 六、咨询锁（Advisory Lock）死锁排查（只读）

```sql
-- 当前持有的咨询锁
SELECT
    l.pid, a.usename, a.application_name, a.state,
    l.locktype, l.classid, l.objid, l.objsubid, l.mode, l.granted,
    NOW() - a.query_start AS query_duration
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.locktype = 'advisory'
  AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY l.classid, l.objid, l.granted;

-- 咨询锁等待会话
SELECT
    a.pid, a.usename, a.state,
    NOW() - a.query_start AS wait_duration,
    LEFT(a.query, 300) AS waiting_query,
    l.locktype, l.classid, l.objid, l.mode, l.granted
FROM pg_stat_activity a
JOIN pg_locks l ON a.pid = l.pid
WHERE l.locktype = 'advisory'
  AND NOT l.granted
  AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY a.query_start;
```

---

## 七、常见死锁模式与预防

| 模式 | 成因 | PostgreSQL 表现 | 预防建议 |
|------|------|---------------|---------|
| 双向更新（环形等待） | 事务 A 更新行 1 等行 2，事务 B 更新行 2 等行 1 | 锁 mode: RowExclusiveLock，死锁检测自动回滚一方 | 统一访问顺序（按主键排序后更新），缩短事务 |
| 外键级联死锁 | 父表与子表交叉更新，外键约束触发锁检查 | 子表 DML 触发父表 ShareLock 检查 | 先更新父表再更新子表；或使用延迟约束 |
| 唯一键冲突 | 并发插入相同唯一键 | 事务等待对方提交或回滚后可见 | 使用 INSERT ... ON CONFLICT 处理 |
| DDL 与 DML 互锁 | ALTER TABLE 等需要 AccessExclusiveLock | DDL 等待所有 DML 完成，后续 DML 被 DDL 阻塞 | 使用 CREATE INDEX CONCURRENTLY；DDL 时设置 lock_timeout |
| 咨询锁死锁 | 应用层两个事务以不同顺序获取同一对咨询锁 | advisory lock 等待，触发 deadlock_timeout 检测 | 统一获取咨询锁的顺序；使用 try_lock 变体 |
| 空闲事务持有锁 | 事务开启后未提交/回滚，一直持有锁 | 锁 granted=true，其他会话排队等待 | 设置 idle_in_transaction_session_timeout 参数 |
| 大批量更新锁升级 | 单事务更新大量行，持有大量 RowExclusiveLock | 锁槽位（max_locks_per_transaction）不足 | 分批提交；适当调大 max_locks_per_transaction |

---

## 八、输出格式

```text
=== 当前锁等待状态 ===
检测时间: <timestamp>
数据库: <db_name>

被阻塞会话:
  PID: <pid> | 用户: <user> | 等待时长: <duration>
  SQL: <query>

阻塞源:
  PID: <pid> | 用户: <user> | 事务持续: <duration>
  SQL: <query>

阻塞链: <blocked_pid> → <blocking_pid>

根因: <conclusion>
建议: <recommendation>
```

---

## 异常处理
- 单条查询失败不影响整体
- 实例连接失败返回明确连接错误信息
- `log_lock_waits` 未开启时提示用户启用
- 无锁等待或死锁时输出明确结论
- 日志文件不存在或无权访问时提示路径错误
- 本技能仅做只读查询，单次执行耗时 ≤ 5s
