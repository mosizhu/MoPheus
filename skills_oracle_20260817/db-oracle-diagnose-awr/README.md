# Oracle AWR 报告分析：等待事件与热点 SQL 定位 说明文档

## 能力简介
本技能为只读诊断技能，从 AWR 历史快照（DBA_HIST_*）与 v$ 动态视图解析 Oracle 数据库性能数据，定位 TOP 等待事件与热点 SQL，并给出优化方向建议（不执行任何变更）。

## 适用场景
- Oracle 数据库性能突然变慢，需快速定位瓶颈
- AWR 报告自动解读与关键指标提取
- 等待事件根因分析（如 enq: TX - row lock contention、log file sync 等）
- 热点 SQL 与资源消耗关联诊断
- RAC 环境全局等待事件分析
- 定期性能巡检与趋势对比

## 触发话术
- "帮我分析一下这个 AWR 报告的等待事件"
- "数据库最近很慢，看看主要卡在哪里"
- "查一下哪些等待事件占比最高"
- "定位一下最近的热点 SQL"
- "看看 DB Time 主要消耗在哪里"
- "RAC 环境下 gc 等待事件有没有异常"
- "帮我分析一下 AWR 快照 100 到 101 之间的性能"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| snap_id_begin | integer | 否 | 0 | AWR 起始快照 ID（为 0 则自动选择最近一对快照） |
| snap_id_end | integer | 否 | 0 | AWR 结束快照 ID（为 0 则自动选择最近一对快照） |
| top_n | integer | 否 | 10 | 返回 TOP N 条等待事件 / 热点 SQL |
| time_range_hours | integer | 否 | 24 | 自动选择快照时的时间范围（小时） |

## 输出示例
```
=== AWR 快照信息 ===
快照范围: 100 ~ 101（2026-08-17 10:00 ~ 2026-08-17 11:00）
DB Time: 3,250.50 秒  |  Elapsed: 3,600 秒
DB CPU: 2,180.30 秒  |  %DB Time = 67.1%

=== 负载概要 ===
Redo Size: 8,450.00 MB
逻辑读: 1,250,000,000 次  |  物理读: 12,500,000 次
执行次数: 452,000  |  提交次数: 35,200  |  回滚次数: 48

=== TOP 5 等待事件（按等待时间） ===
等待类           等待事件                          等待时间(秒)    占比
User I/O         db file sequential read          820.50         25.2%
User I/O         db file scattered read           450.20         13.8%
Commit           log file sync                    380.00         11.7%
Concurrency      buffer busy waits                210.30          6.5%
Application      enq: TX - row lock contention    180.50          5.6%
解读: db file sequential read 占比最高(25.2%)，说明存在大量索引扫描或单块读等待，
      建议检查热点 SQL 的索引效率与执行计划。

=== 时间模型分布 ===
DB CPU:                          2,180.30 秒 (67.1%)
sql execute elapsed time:        2,950.00 秒 (90.7%)
parse time elapsed:                120.50 秒 (3.7%)
hard parse elapsed time:            45.00 秒 (1.4%)
PL/SQL execution elapsed time:     85.20 秒 (2.6%)

=== 热点 SQL TOP 5（按总耗时） ===
1. SQL_ID: 9m7787camwh4m
   总耗时: 450.20 秒 | CPU: 320.50 秒 | 执行: 12,500 次 | 平均: 0.036 秒/次
   逻辑读: 85,000,000 | 物理读: 2,500,000 | 占比: 13.8%
   SQL: SELECT o.order_id, c.customer_name FROM orders o JOIN ...

2. SQL_ID: 5k6234abc1234
   总耗时: 320.80 秒 | CPU: 280.10 秒 | 执行: 850 次 | 平均: 0.377 秒/次
   逻辑读: 45,000,000 | 物理读: 1,200,000 | 占比: 9.9%
   SQL: SELECT /*+ PARALLEL(8) */ * FROM order_items WHERE ...

=== 等待事件与 SQL 关联 ===
等待事件: db file sequential read
  SQL_ID: 9m7787camwh4m  → 采样 320 次 (45.2%)
  SQL_ID: 5k6234abc1234  → 采样 180 次 (25.4%)

=== 实例效率命中率 ===
Buffer Cache Hit Ratio:     92.5%   ← 低于 95%，需关注
Library Cache Hit Ratio:    98.2%   ← 正常
Soft Parse Ratio:           96.5%   ← 正常

=== 综合诊断结论 ===
1. 主要瓶颈: User I/O 等待（39.0%），集中在索引扫描和全表扫描
2. 次瓶颈: log file sync 占比 11.7%，检查提交频率
3. SQL 9m7787camwh4m 为最大资源消耗者，建议检查执行计划
4. Buffer Cache Hit Ratio 偏低(92.5%)，建议评估增大 SGA 或优化 SQL
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与参考。
- 不执行任何 DDL/DML、不调整配置，全程可追溯、无高危。

## 功能限制
- 不执行 SQL Profile 创建/绑定（DBMS_SQLTUNE）
- 不执行 SPM 基线操作
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）
- 不修改 SQL 文本、不调整实例参数
- 不生成 AWR 报告快照（不执行 DBMS_WORKLOAD_REPOSITORY.CREATE_SNAPSHOT）
- 索引建议请用对应索引设计类技能，统计刷新请用统计信息维护类技能

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle AWR 报告分析技能，只读诊断（query / db-query），覆盖负载概要、等待事件 TOP N 按等待类分类、热点 SQL 多维排序（Elapsed/CPU/Buffer Gets/Disk Reads/Executions）、时间模型分解、实例效率命中率、等待事件与 SQL 关联分析、RAC 全局等待事件。