# Oracle 综合性能诊断（CPU / IO / 锁）说明文档

## 能力简介
本技能为只读诊断技能，从 v$ 动态视图、AWR 历史快照（DBA_HIST_*）与 OS 层统计信息三个维度，对 Oracle 数据库进行 CPU、IO、锁的综合性能诊断，定位瓶颈并给出优化方向建议（不执行任何变更）。

## 适用场景
- 数据库响应变慢，需综合定位是 CPU 瓶颈 / IO 瓶颈 / 锁等待
- 应用反馈"时而快时而慢"，需同时排查 CPU 波动与锁争用
- 定期性能巡检，产出 CPU/IO/锁三维健康报告
- 高并发 OLTP 系统锁争用与 CPU 关联分析
- 批量任务期间的 IO 吞吐与 CPU 压力评估

## 触发话术
- "数据库响应很慢，全面诊断一下是 CPU 高还是 IO 慢还是锁"
- "帮我做一个 CPU/IO/锁的综合性能诊断"
- "数据库 CPU 很高，看看是什么原因"
- "数据库 IO 很慢，排查一下哪些表空间 IO 高"
- "数据库锁等待严重，看看当前锁等待链"
- "帮我做一次数据库性能巡检"
- "数据库时而快时而慢，综合排查一下"
- "看看数据库的 CPU、IO、锁这三个维度有没有问题"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| diagnose_scope | string | 否 | all | 诊断范围：all（全部）/ cpu（仅 CPU）/ io（仅 IO）/ lock（仅锁） |
| top_n | integer | 否 | 10 | 返回 TOP N 条结果 |
| time_range_hours | integer | 否 | 24 | 历史数据查询时间范围（小时） |
| snap_id_begin | integer | 否 | 0 | AWR 历史查询起始快照 ID（为 0 则自动选择最近一对快照） |
| snap_id_end | integer | 否 | 0 | AWR 历史查询结束快照 ID（为 0 则自动选择最近一对快照） |

## 输出示例
```
=== 宏观诊断概览 ===
OS CPU: 8 核, 使用率 85.2%, Idle 14.8%, Load 6.5
DB CPU 占比: 72.3%（CPU 瓶颈风险）
IO 等待类占比: User I/O 18.2%, System I/O 4.5%
当前锁等待: 3 个会话被阻塞, 1 个阻塞者

=== CPU 诊断 ===
时间模型分布:
  DB CPU:                          2,180.30 秒 (72.3%)
  sql execute elapsed time:        2,650.00 秒 (87.9%)
  parse time elapsed:                120.50 秒 (4.0%)
  hard parse elapsed time:            15.00 秒 (0.5%)
  PL/SQL execution elapsed time:     85.20 秒 (2.8%)

TOP 5 CPU SQL:
1. SQL_ID: 9m7787camwh4m  CPU: 450.20 秒 (20.7%)  Exec: 12,500 次
   SELECT o.order_id, c.customer_name FROM orders o JOIN ...
2. SQL_ID: 5k6234abc1234  CPU: 320.80 秒 (14.7%)  Exec: 850 次
   SELECT /*+ PARALLEL(8) */ * FROM order_items WHERE ...

CPU 诊断结论: CPU 使用率偏高(85.2%)，硬解析比例低(0.5%)，
主要瓶颈在 SQL 执行阶段(87.9%)，TOP 2 SQL 占总 CPU 35.4%。

=== IO 诊断 ===
IO 等待事件 TOP 5:
  db file sequential read        820.50 秒 (45.2%)  avg 8.5ms
  db file scattered read         450.20 秒 (24.8%)  avg 15.3ms
  log file parallel write        180.00 秒 (9.9%)   avg 3.2ms
  direct path read               120.50 秒 (6.6%)   avg 22.1ms
  direct path write               80.20 秒 (4.4%)   avg 18.5ms

表空间 IO 热点 TOP 3:
  USERS_TS:  读 12,500 MB, 写 2,300 MB, avg_read 12.3ms
  IDX_TS:    读 8,200 MB, 写 1,100 MB, avg_read 8.5ms
  UNDOTBS1:  读 3,500 MB, 写 5,800 MB, avg_write 3.2ms

Temp 使用: 8,192 MB / 32,768 MB (25.0%)
排序溢出率: 3.2%（正常范围）

IO 诊断结论: User I/O 占比 18.2%，avg_read 在正常范围(8~15ms)，
direct path read/write 存在，说明有并行查询和排序落盘。

=== 锁诊断 ===
当前锁等待链:
  [L1] SYS (SID 61)  ← 顶级阻塞者（未等待）
    [L2] HR (SID 72)  ← 等待 TX(事务锁), 已等 125 秒
      [L3] APP (SID 88) ← 等待 TX(事务锁), 已等 45 秒

阻塞详情:
  Holder SID 61: UPDATE orders SET status='LOCKED' WHERE order_id=1001
  Waiter SID 72: UPDATE orders SET status='SHIPPED' WHERE order_id=1001
  Waiter SID 88: UPDATE order_items SET qty=5 WHERE order_id=1001

enqueue 锁统计:
  TX(事务锁): 1,250 次等待, avg_wait 45ms
  TM(DML表锁): 48 次等待, avg_wait 12ms

ITL 等待: ITL waits = 0（正常）
热块冲突: buffer busy waits 集中在 orders 表（128 次）

锁诊断结论: 存在 3 层锁等待链，SID 61 长期持锁阻塞下游，
建议检查该事务是否异常（持锁时长 > 125 秒需关注）。

=== 综合诊断结论 ===
主瓶颈: CPU（DB CPU 占比 72.3%，OS CPU 85.2%）
次瓶颈: IO（User I/O 18.2%，direct path read 存在）
附带问题: 锁等待（SID 61 长期持锁阻塞 2 个会话）

关联分析:
  - 锁等待导致 CPU 空转: 被阻塞会话 SID 72/88 在等待中不消耗 CPU
  - IO 瓶颈影响 CPU 效率: direct path read 导致 CPU 等待 IO

优化建议:
  1. [CPU] 优化 TOP 2 SQL 的执行计划，降低 CPU 消耗
  2. [IO] 检查 direct path read 的 SQL，考虑调整并行度或 PGA
  3. [锁] 排查 SID 61 会话事务异常，必要时评估是否 KILL
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与参考。
- 不执行任何 DDL/DML、不调整配置，全程可追溯、无高危。

## 功能限制
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改实例参数（不执行 ALTER SYSTEM SET）
- 不调整表/索引存储参数（不执行 ALTER TABLE/INDEX）
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）
- 不执行 SQL Profile/SPM 操作
- 索引建议请用对应索引设计类技能，死锁深度分析请用死锁诊断类技能

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle 综合性能诊断技能，只读诊断（query / db-query），覆盖 CPU 诊断（OS CPU 负载、时间模型、TOP CPU SQL、CPU 等待事件）、IO 诊断（IO 等待事件、表空间/数据文件 IO 热点、Temp 排序溢出）、锁诊断（递归锁等待链、阻塞会话与 SQL 关联、enqueue 锁类型争用、热块/ITL 等待）、AWR 历史趋势、三维度关联分析与优化建议。