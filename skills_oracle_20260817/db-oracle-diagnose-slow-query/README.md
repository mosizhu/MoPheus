# Oracle 慢查询诊断与 TOP N 慢 SQL 定位 说明文档

## 能力简介
本技能为只读诊断技能，从 AWR 历史快照与 v$ 动态视图定位 TOP N 慢 SQL、解读执行计划、检测全表扫描与索引失效，并给出优化方向建议（不执行任何变更）。

## 适用场景
- 数据库响应变慢，需快速定位资源消耗 TOP N SQL
- AWR 报告辅助解读与补充分析
- 按 elapsed time / CPU / 逻辑读 / 物理读 多维度筛查问题 SQL
- 对指定 SQL_ID 做执行计划深度分析
- 排查统计信息过期导致的执行计划异常

## 触发话术
- "帮我查一下 Oracle 最近有哪些慢 SQL"
- "分析一下这个 SQL_ID 的执行计划"
- "看看 AWR 里 TOP 10 耗时 SQL"
- "哪些表存在全表扫描"
- "检查一下统计信息有没有过期"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| sql_id | string | 否 | | 指定 SQL_ID 进行单条深度分析（为空则按 TOP N 筛查） |
| top_n | integer | 否 | 10 | 返回 TOP N 条慢 SQL |
| sort_metric | string | 否 | elapsed | 排序指标：elapsed / cpu / buffer_gets / disk_reads / executions |
| time_range_hours | integer | 否 | 24 | AWR 历史查询时间范围（小时） |

## 输出示例
```
=== Oracle 慢查询 TOP 5（最近 24h，按总耗时） ===
1. SQL_ID: 9m7787camwh4m
   SQL文本: SELECT o.order_id, c.customer_name FROM orders o JOIN customers c ...
   总耗时: 1250.50 秒  |  CPU: 890.32 秒  |  执行次数: 4520
   平均耗时: 0.28 秒/次  |  逻辑读: 12,450,000  |  物理读: 380,000

=== 执行计划分析（SQL_ID: 9m7787camwh4m） ===
Plan Hash: 3910148636
| Id | Operation             | Name       | Rows | Bytes | Cost |
|  0 | SELECT STATEMENT      |            |      |       | 8500 |
|* 1 |  HASH JOIN            |            | 5000 | 450K  | 8500 |
|* 2 |   TABLE ACCESS FULL   | ORDERS     | 5000 | 200K  | 4200 |
|* 3 |   TABLE ACCESS FULL   | CUSTOMERS  | 100K | 4800K | 4300 |
优化建议: ORDERS 表全表扫描，建议在 orders.status 上建索引

=== 全表扫描 TOP 表 ===
表名: ORDERS          全表扫描次数: 12,500
表名: ORDER_ITEMS     全表扫描次数: 8,200

=== 统计信息过期 ===
表名: ORDERS          上次分析: 2026-07-15  已过期 33 天
表名: ORDER_ITEMS     上次分析: 2026-07-20  已过期 28 天
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与参考。
- 不执行任何 DDL/DML、不调整配置，全程可追溯、无高危。

## 功能限制
- 不执行 SQL Profile 创建/绑定（DBMS_SQLTUNE）
- 不执行 SPM 基线操作
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）
- 不修改 SQL 文本、不调整优化器参数
- 索引建议请用对应索引设计类技能，统计刷新请用统计信息维护类技能

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle 慢查询诊断定位技能，只读诊断（query / db-query），覆盖 AWR 历史 + v$ 实时双通道、执行计划解读、全表扫描检测、统计信息新鲜度检查、多维度排序（elapsed/cpu/buffer_gets/disk_reads）。