---
name: "db-oracle-diagnose-deadlock"
description: "Oracle 死锁 trace 分析与根因诊断技能。核心能力：解析 Oracle 死锁 trace 文件（.trc）与 alert 日志中的 ORA-00060 死锁段、从 V$LOCK / V$SESSION / DBA_BLOCKERS / DBA_WAITERS 实时查询锁等待链、绘制等待依赖图（Wait-for-Graph）定位死锁环、区分 TX 事务锁死锁 / TM 表锁死锁 / ITL 槽位死锁、定位被回滚事务与竞争行对象、给出复现步骤与预防建议。适用场景：ORA-00060 死锁根因分析、高频死锁预防性排查、并发事务加锁顺序冲突诊断、ITL 不足导致死锁排查。功能限制：本技能仅做 trace 解析与实时查询诊断、产出根因与预防建议，不 KILL 会话/事务、不修改隔离级别与锁参数、不调整 INITRANS 等存储参数。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: true
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名）"
  - name: "trace_file_path"
    type: "string"
    required: false
    default: ""
    desc: "死锁 trace 文件路径（可选，为空则自动从 alert log 定位最近 ORA-00060 trace）"
  - name: "time_range_hours"
    type: "integer"
    required: false
    default: 24
    desc: "查询最近 N 小时内的死锁记录，默认 24 小时"
  - name: "deadlock_type"
    type: "string"
    required: false
    default: "all"
    desc: "死锁类型过滤：all（全部）/ tx（TX 事务锁）/ tm（TM 表锁）/ itl（ITL 槽位）"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 死锁 Trace 分析与根因诊断

本技能为只读诊断技能，解析 Oracle 死锁 trace 文件与 alert 日志中的 ORA-00060 死锁段，结合 V$LOCK / V$SESSION / DBA_BLOCKERS / DBA_WAITERS 实时查询锁等待链，定位死锁根因并给出复现与预防建议（不执行任何变更）。

---

## 核心能力
- 解析 Oracle 死锁 trace 文件（*.trc），提取死锁环中的事务、锁类型、SQL 语句与等待行
- 从 alert 日志自动定位最近 ORA-00060 死锁对应的 trace 文件路径
- 实时查询当前锁等待链（V$LOCK / DBA_BLOCKERS / DBA_WAITERS / V$LOCKED_OBJECT）
- 绘制等待依赖图（Wait-for-Graph），定位死锁环
- 区分三类死锁：TX 事务锁（ITL 行级锁）/ TM 表锁 / ITL 槽位不足
- 定位被回滚事务及竞争行对象（ROWID → 表名 → 行数据）
- 给出复现步骤与预防建议

## 适用场景
- ORA-00060 死锁发生后根因分析
- 死锁 trace 文件自动解读
- 高频死锁的预防性排查
- 并发事务加锁顺序冲突诊断
- TM 表锁（外键未索引）导致死锁排查
- ITL 不足导致死锁排查

## 功能限制 / 安全边界
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改隔离级别（不执行 ALTER SESSION SET ISOLATION_LEVEL）
- 不调整存储参数（不执行 ALTER TABLE ... INITRANS / MAXTRANS）
- 不修改索引、不创建外键索引、不调整表结构
- 不调用其它 Skill、不自动修复、仅按需手动触发

---

## 一、推理框架：Oracle 死锁诊断链

```
用户报告 ORA-00060 / 提交死锁 trace 文件
    |
    v
[1] 来源确认：trace 文件 / 实时锁等待 / alert log
    | 定位 trace 文件路径
    | 提取 ORA-00060 时间线
    v
[2] 死锁类型识别
    | TX 事务锁（enq: TX - row lock contention）→ 行级锁冲突
    | TM 表锁（enq: TM - contention）→ 外键无索引 / DDL 冲突
    | ITL 槽位死锁 → INITRANS 不足
    v
[3] 等待依赖图构建
    | 提取死锁环中各个会话的 SID/SERIAL#、持有锁、等待锁、SQL、ROWID
    | 绘制 Wait-for-Graph：S1 持有 A 等待 B → S2 持有 B 等待 A → 成环
    v
[4] 竞争行对象定位
    | ROWID → dba_objects 反向解析表名
    | 查询行数据（如实例可连）
    v
[5] 根因判定与预防建议
    | 统一加锁顺序 / 缩短事务 / 外键补索引 / 增大 INITRANS
```

---

## 二、自动定位死锁 Trace 文件（只读）

### 2.1 从 alert 日志定位最近 ORA-00060 的 trace 文件

```sql
-- 查看 alert 日志路径
SELECT value FROM v$diag_info WHERE name = 'Diag Trace';

-- 查看 trace 文件目录
SELECT value FROM v$diag_info WHERE name = 'Diag Trace';

-- 读取 alert 日志中最近 ORA-00060 记录（需外部工具）
-- 可使用 ADRCI 或直接读取 alert log 文件 grep "ORA-00060"
-- alert log 路径: <Diag Trace>/alert_<ORACLE_SID>.log
```

### 2.2 从 trace 文件目录定位死锁 trace

```sql
-- 查看所有 trace 文件（按时间排序，最新的在最后）
-- trace 文件路径: <Diag Trace>/<ORACLE_SID>_ora_*.trc
-- 死锁 trace 特征：文件中包含 "DEADLOCK DETECTED" 或 "ORA-00060"
```

### 2.3 手动生成死锁诊断 dump（紧急场景，只读）

```sql
-- 诊断当前系统锁状态（仅生成 trace，不执行变更）
-- ALTER SYSTEM DUMP SYSTEM_STATE;
-- 查看 dump 路径
SELECT value FROM v$diag_info WHERE name = 'Default Trace File';
```

---

## 三、Oracle 死锁 Trace 文件格式解析

```
*** 2026-08-17 10:15:30.123
DEADLOCK DETECTED ( ORA-00060 )
[Transaction Deadlock]

The following deadlock is not an ORACLE error. It is a
deadlock due to user error in the design of an application...

The following information describes the deadlock and the sessions
involved in the deadlock. Please forward the entire deadlock section
to Oracle Support.

Deadlock graph:
                       ---------Blocker(s)--------  ---------Waiter(s)---------
Resource Name          process session holds waits  process session holds waits
TX-00090014-0000a2b3        24      61     X             28      72           X
TX-00010015-00009c8d        28      72     X             24      61           X

session 61: DID 0001-0018-00000002 session 72: DID 0001-001C-00000011
session 72: DID 0001-001C-00000011 session 61: DID 0001-0018-00000002

Rows waited on:
  Session 61: obj - rowid=0000A2B3.AAABBB.0001
  (dictionary objn - 41651, file - 4, block - 123, slot - 1)
  Session 72: obj - rowid=00009C8D.AAACCC.0002
  (dictionary objn - 40077, file - 4, block - 456, slot - 2)

----- Information for the OTHER waiting session(s) -----
Session 72:
  ...
  current SQL:
  UPDATE orders SET status='SHIPPED' WHERE order_id=1001

----- Information for THIS session (session 61) -----
  current SQL:
  UPDATE order_items SET qty=5 WHERE item_id=2001

----- End of deadlock section -----
```

### Trace 关键字段解读

| 字段 | 含义 | 诊断要点 |
|------|------|---------|
| Deadlock graph | 死锁依赖图 | 识别谁持有（holds）谁等待（waits） |
| Resource Name | 锁资源名（TX-...） | TX=事务锁，TM=表锁 |
| process / session | 进程号 / 会话 SID | 对应 V$SESSION 的 SID |
| holds X / waits X | 持有/等待独占锁 | X=Exclusive，S=Share |
| Rows waited on | 等待的具体行 | obj=对象号，rowid=行地址 |
| dictionary objn | 数据字典对象号 | 关联 DBA_OBJECTS 获取表名 |
| current SQL | 当前执行的 SQL | 死锁发生时事务正在执行的语句 |

---

## 四、死锁类型识别与分类

### 4.1 TX 事务锁死锁（最常见）

```
特征：Resource Name 以 "TX-" 开头
成因：两个事务互相等待对方持有的行级锁
典型场景：事务A更新行1→行2，事务B更新行2→行1（交叉更新顺序）
```

```sql
-- 查询当前 TX 锁等待链
SELECT blocking_session,
       sid,
       serial#,
       wait_class,
       event,
       seconds_in_wait,
       blocking_session_status
FROM v$session
WHERE blocking_session IS NOT NULL
  AND event LIKE 'enq: TX%';
```

### 4.2 TM 表锁死锁

```
特征：Resource Name 以 "TM-" 开头
成因：外键列无索引 → 更新父表主键时子表全表加锁
     或 DDL 与 DML 并发冲突
典型场景：删除父表记录时，子表外键列无索引导致子表被锁
```

```sql
-- 查询未建索引的外键列（TM 死锁高发区）
SELECT a.table_name,
       a.column_name,
       a.constraint_name,
       c.r_owner,
       c.r_constraint_name,
       c_pk.table_name AS parent_table
FROM all_cons_columns a
JOIN all_constraints c
  ON a.owner = c.owner
 AND a.constraint_name = c.constraint_name
WHERE c.constraint_type = 'R'
  AND c.owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND NOT EXISTS (
    SELECT 1 FROM all_ind_columns i
    WHERE i.table_owner = a.owner
      AND i.table_name = a.table_name
      AND i.column_name = a.column_name
      AND i.column_position = 1
  );
```

### 4.3 ITL 槽位死锁

```
特征：trace 中显示 "ITL" 相关信息
成因：表/索引的 INITRANS 设置过小，并发事务数超过 ITL 槽位数
典型场景：高并发更新小块表，ITL 槽位耗尽
```

```sql
-- 查询 INITRANS 较小的表（可能存在 ITL 死锁风险）
SELECT owner,
       table_name,
       ini_trans,
       max_trans,
       pct_free,
       pct_used
FROM dba_tables
WHERE owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND ini_trans = 1
ORDER BY owner, table_name;

-- 查看段 ITL 等待统计
SELECT owner,
       object_name,
       subobject_name,
       value AS itl_waits
FROM v$segment_statistics
WHERE statistic_name = 'ITL waits'
  AND value > 0
ORDER BY value DESC;
```

---

## 五、实时锁等待链查询（只读）

### 5.1 当前锁等待依赖图（DBA_BLOCKERS / DBA_WAITERS）

```sql
-- 查询当前阻塞者（持有锁但未等待的会话）
SELECT holding_session
FROM dba_blockers;

-- 查询当前等待者与被等待者详情
SELECT waiting_session,
       holding_session,
       lock_type,
       mode_held,
       mode_requested,
       lock_id1,
       lock_id2
FROM dba_waiters
ORDER BY holding_session;
```

### 5.2 锁等待链递归查询（V$LOCK / V$SESSION）

```sql
-- 递归查询锁等待链（从顶层阻塞者到最底层等待者）
SELECT LEVEL AS chain_level,
       LPAD(' ', (LEVEL - 1) * 4) || s.username AS user_name,
       s.sid,
       s.serial#,
       s.status,
       s.event,
       s.seconds_in_wait,
       s.blocking_session,
       s.sql_id,
       s.row_wait_obj#,
       s.row_wait_file#,
       s.row_wait_block#,
       s.row_wait_row#,
       l.type AS lock_type,
       l.lmode AS lock_mode,
       l.request AS lock_request,
       l.ctime AS lock_seconds
FROM v$session s
LEFT JOIN v$lock l
  ON s.sid = l.sid
WHERE s.sid IN (SELECT DISTINCT blocking_session FROM v$session WHERE blocking_session IS NOT NULL)
   OR s.blocking_session IS NOT NULL
START WITH s.blocking_session IS NULL
  AND s.sid IN (SELECT DISTINCT holding_session FROM dba_waiters)
CONNECT BY PRIOR s.sid = s.blocking_session
ORDER SIBLINGS BY s.sid;
```

### 5.3 锁等待与事务信息关联

```sql
-- 锁等待 + 事务详情（含 SQL 文本）
SELECT w.waiting_session AS waiter_sid,
       w.holding_session AS holder_sid,
       w.lock_type,
       w.mode_held,
       w.mode_requested,
       ws.username AS waiter_user,
       ws.machine AS waiter_machine,
       ws.program AS waiter_program,
       hs.username AS holder_user,
       hs.machine AS holder_machine,
       hs.program AS holder_program,
       ws.sql_id AS waiter_sql_id,
       SUBSTR(wsql.sql_text, 1, 200) AS waiter_sql_text,
       hs.sql_id AS holder_sql_id,
       SUBSTR(hsql.sql_text, 1, 200) AS holder_sql_text
FROM dba_waiters w
JOIN v$session ws ON w.waiting_session = ws.sid
JOIN v$session hs ON w.holding_session = hs.sid
LEFT JOIN v$sql wsql ON ws.sql_id = wsql.sql_id
LEFT JOIN v$sql hsql ON hs.sql_id = hsql.sql_id;
```

### 5.4 锁等待涉及的对象

```sql
-- 查询当前被锁住的对象
SELECT lo.object_id,
       o.owner,
       o.object_name,
       o.object_type,
       lo.session_id,
       lo.oracle_username,
       lo.os_user_name,
       lo.process,
       lo.locked_mode
FROM v$locked_object lo
JOIN dba_objects o ON lo.object_id = o.object_id
WHERE o.owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
ORDER BY lo.session_id;
```

---

## 六、死锁环中竞争行对象定位（只读）

### 6.1 从 trace 中的 ROWID 反向解析对象

```sql
-- 从 trace 中提取 dictionary objn（数据对象号），反向查询表名
SELECT owner,
       object_name,
       object_type,
       data_object_id
FROM dba_objects
WHERE data_object_id = &objn;

-- 从 ROWID 查询具体行数据
SELECT *
FROM &table_name
WHERE ROWID = '&rowid_value';
```

### 6.2 从 trace 中的 file/block 定位段对象

```sql
-- 根据 file# 和 block# 定位段对象
SELECT owner,
       segment_name,
       segment_type,
       partition_name
FROM dba_extents
WHERE file_id = &file_id
  AND &block_id BETWEEN block_id AND block_id + blocks - 1
  AND owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP');
```

---

## 七、死锁依赖图构建

### 依赖图构建规则

```
1. 从 trace 的 Deadlock graph 中提取：
   - Resource Name（TX-... / TM-...）
   - process / session（对应 V$SESSION.SID）
   - holds / waits（X=独占，S=共享）

2. 构建有向图：
   - 节点：Session ID
   - 边：会话 A 持有资源 R1 → 会话 B 等待资源 R1
   - 死锁环：A → B → ... → A 形成闭环

3. 判定回滚对象：
   - Oracle 选择 undo 量最少的事务回滚
   - 从 trace 的 "Rows waited on" 段可推断
```

### 典型死锁环示例

```
场景：事务交叉更新同一组行

  事务 A (SID 61)                    事务 B (SID 72)
     │                                    │
     ├─ 持有: TX-00090014 (行1) ──→ B 等待
     │                                    │
     ├─ 等待: TX-00010015 (行2) ←── B 持有

依赖环: A → 行2 → B → 行1 → A  ⇒ 死锁
回滚方: 事务 A (undo 量更少)
```

---

## 八、常见 Oracle 死锁模式与预防

| 死锁模式 | 成因 | 典型 SQL 模式 | 预防方案 |
|---------|------|-------------|---------|
| 交叉更新（TX） | 两事务以不同顺序更新相同行 | T1: UPDATE A→B; T2: UPDATE B→A | 统一加锁顺序（按主键/ROWID 排序后更新） |
| 外键无索引（TM） | 更新/删除父表主键时子表全表加锁 | DELETE parent WHERE pk=1;（子表外键无索引） | 在外键列上创建索引（索引创建由索引设计专项技能负责） |
| ITL 槽位不足 | INITRANS 过小，并发事务数超过 ITL 槽位 | 高频并发更新同一个小表 | 增大 INITRANS（ALTER TABLE ... INITRANS N） |
| 位图索引死锁 | 并发 DML 操作位图索引列 | 多个会话同时 INSERT/UPDATE 位图索引列 | OLTP 场景避免使用位图索引，改用 B-Tree 索引 |
| 主键/唯一键冲突 | 并发插入相同键值 | INSERT INTO t VALUES(1, ...); ← 两会话同时 | 使用序列生成主键、INSERT IGNORE 逻辑 |
| 分布式事务死锁 | 跨数据库链接的事务互相等待 | DB Link 事务 | 统一事务边界、避免循环 DB Link |

---

## 九、死锁预防最佳实践

### 9.1 应用层预防

| 原则 | 说明 |
|------|------|
| 统一加锁顺序 | 所有事务按相同顺序访问资源（如按主键升序） |
| 缩短事务 | 减少事务持有锁的时间，避免在事务中做用户交互 |
| 尽早锁定 | 在事务开始时一次性获取所有需要的锁 |
| 最小锁粒度 | 能用行锁不用表锁，能用 SELECT FOR UPDATE 不用 LOCK TABLE |

### 9.2 数据库层预防

```sql
-- 监控死锁发生频率
SELECT name,
       value
FROM v$sysstat
WHERE name IN (
    'enqueue deadlocks',
    'enqueue timeouts',
    'enqueue waits',
    'enqueue requests'
);

-- 查看死锁历史统计
SELECT *
FROM v$enqueue_stat
WHERE cum_wait_time > 0
  AND eq_type IN ('TX', 'TM')
ORDER BY cum_wait_time DESC;
```

### 9.3 死锁高发场景排查

```sql
-- 查询最近发生死锁的会话（需审计/日志支持）
-- 从 DBA_HIST_ACTIVE_SESS_HISTORY 定位锁等待历史
SELECT sample_time,
       session_id,
       session_serial#,
       blocking_session,
       blocking_session_serial#,
       event,
       sql_id,
       blocking_session_status
FROM dba_hist_active_sess_history
WHERE event LIKE 'enq: TX%'
   OR event LIKE 'enq: TM%'
ORDER BY sample_time DESC;
```

---

## 异常处理
- trace 文件不存在时，回退到实时 V$LOCK / DBA_WAITERS 查询当前锁等待状态。
- 实例连接失败返回明确连接错误信息，不输出数据库原始异常堆栈。
- ROWID 查询失败时标记"无法解析该行数据"，不影响整体分析结论。
- 本技能仅做只读诊断，不执行任何 DDL/DML，单次执行耗时 ≤5s，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：
  1. 死锁来源（trace 文件路径 / 实时查询）
  2. 死锁类型（TX / TM / ITL）
  3. 死锁依赖图（持有/等待关系 + 死锁环）
  4. 涉及会话（SID、SQL、用户名、机器、程序）
  5. 竞争行对象（表名 + ROWID + 行数据）
  6. 回滚对象（哪个事务被回滚 + 原因）
  7. 根因结论
  8. 复现步骤
  9. 预防建议清单