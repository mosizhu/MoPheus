# Oracle 死锁 Trace 分析与根因诊断 说明文档

## 能力简介
本技能为只读诊断技能，解析 Oracle 死锁 trace 文件（.trc）与 alert 日志中的 ORA-00060 死锁段，结合 V$LOCK / V$SESSION / DBA_BLOCKERS / DBA_WAITERS 实时查询锁等待链，定位死锁根因并给出复现与预防建议（不执行任何变更）。

## 适用场景
- ORA-00060 死锁发生后根因分析
- 死锁 trace 文件自动解读
- 高频死锁的预防性排查
- 并发事务加锁顺序冲突诊断
- TM 表锁（外键未索引）导致死锁排查
- ITL 不足导致死锁排查

## 触发话术
- "帮我分析一下这个 Oracle 死锁 trace 文件"
- "刚才报了 ORA-00060，查一下死锁原因"
- "看看现在数据库有哪些锁等待"
- "为什么这两个事务会死锁"
- "怎么避免 Oracle 死锁"
- "查一下外键有没有缺失索引导致 TM 死锁"
- "ITL 等待很高，是不是有死锁风险"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| trace_file_path | string | 否 | | 死锁 trace 文件路径（为空则自动从 alert log 定位最近 ORA-00060 trace） |
| time_range_hours | integer | 否 | 24 | 查询最近 N 小时内的死锁记录 |
| deadlock_type | string | 否 | all | 死锁类型过滤：all / tx / tm / itl |

## 输出示例

```
=== 死锁来源 ===
来源: trace 文件 /u01/app/oracle/diag/rdbms/orcl/ORCL/trace/ORCL_ora_12345.trc
发生时间: 2026-08-17 10:15:30
死锁类型: TX 事务锁（行级锁交叉等待）

=== 死锁依赖图 ===
        持有 TX-00090014 (行1)              等待 TX-00090014 (行1)
事务 A (SID 61) ──────────────────────────────────────────→ 事务 B (SID 72)
        等待 TX-00010015 (行2)              持有 TX-00010015 (行2)
事务 A (SID 61) ←────────────────────────────────────────── 事务 B (SID 72)

死锁环: A → 行2(被B持有) → B → 行1(被A持有) → A  ⇒ 死锁

=== 涉及会话 ===
事务 A (SID: 61, SERIAL#: 12345, USER: APP_USER)
  机器: app-server-01  程序: JDBC Thin Client
  当前 SQL: UPDATE order_items SET qty=5 WHERE item_id=2001
  状态: 被回滚

事务 B (SID: 72, SERIAL#: 23456, USER: APP_USER)
  机器: app-server-02  程序: JDBC Thin Client
  当前 SQL: UPDATE orders SET status='SHIPPED' WHERE order_id=1001
  状态: 执行成功

=== 竞争行对象 ===
对象1: ORDER_ITEMS (data_object_id: 41651)
  ROWID: AAABBB.AAAAAW.AAA
  行数据: ITEM_ID=2001, ORDER_ID=1001, QTY=3

对象2: ORDERS (data_object_id: 40077)
  ROWID: AAACCC.AAAABG.AAB
  行数据: ORDER_ID=1001, STATUS='PENDING', CUSTOMER_ID=5001

=== 回滚对象 ===
回滚事务: 事务 A (SID 61)
回滚原因: Oracle 选择 undo 量最少的事务回滚（ORDER_ITEMS 单行更新 undo 量更小）

=== 根因结论 ===
两事务以不同顺序更新 ORDER_ITEMS 和 ORDERS 表：
- 事务 A 先更新 ORDER_ITEMS 再更新 ORDERS
- 事务 B 先更新 ORDERS 再更新 ORDER_ITEMS
交叉持有/等待导致死锁。

=== 复现步骤 ===
1. 会话1: UPDATE order_items SET qty=5 WHERE item_id=2001;
2. 会话2: UPDATE orders SET status='SHIPPED' WHERE order_id=1001;
3. 会话1: UPDATE orders SET status='SHIPPED' WHERE order_id=1001; -- 等待 B
4. 会话2: UPDATE order_items SET qty=5 WHERE item_id=2001; -- 等待 A → 死锁

=== 预防建议 ===
1. 统一加锁顺序：所有事务按表的主键或固定顺序访问资源
2. 缩短事务：将订单和订单项更新放在同一个短事务中
3. 按主键排序：先查询需要更新的行，按主键升序统一更新顺序
4. 考虑使用 SELECT FOR UPDATE NOWAIT 在事务开始时获取锁
```

## 安全边界
- 安全等级为 query（只读安全），仅做 trace 解析与实时查询诊断、产出根因与预防建议。
- 不 KILL 会话/事务、不修改隔离级别、不调整存储参数。

## 功能限制
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改隔离级别、不调整 INITRANS 等存储参数
- 不创建外键索引、不调整表结构
- 不调用其它 Skill、不自动修复

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle 死锁 trace 分析与根因诊断技能，只读诊断（query / db-query），覆盖死锁 trace 解析、TX/TM/ITL 三类死锁识别、等待依赖图构建、竞争行对象定位、实时锁等待链查询、外键无索引排查、根因与预防建议输出。