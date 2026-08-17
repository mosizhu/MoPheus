# Oracle SQL 调优方案生成

## 能力简介
本技能针对 Oracle SQL 性能问题，基于 SQL_ID 或 SQL 文本输出多维度结构化调优方案：执行计划深度解读（访问路径 / 连接方式 / 代价估算偏差）、SQL 改写策略（子查询展开 / JOIN 改写 / UNION 优化 / 分页优化 / 分析函数替代）、索引优化建议（单列 / 复合 / 覆盖 / 函数索引推荐）、统计信息诊断与刷新建议、Hint 调优建议、绑定变量窥探与自适应游标分析。本技能为只读方案（query 级），不直接执行。自包含、单一职责。

## 适用场景
- 单条 SQL 性能调优，需输出完整优化方案
- AWR / ASH TOP SQL 优化方案输出
- 执行计划异常分析（计划漂移、代价估算偏差）
- SQL 改写与优化评审（代码走查）
- 索引设计评审（基于 SQL 查询模式）
- 绑定变量窥探与自适应游标问题排查
- 统计信息过期导致的执行计划异常

## 触发话术
- "帮我把这个 SQL_ID 做个调优方案"
- "这条 SQL 跑得很慢，帮我分析一下执行计划"
- "AWR 报告里 TOP 1 的 SQL 怎么优化，给个方案"
- "这条 SQL 全表扫描了，怎么建索引"
- "这个子查询能不能改写成 JOIN，帮我看看"
- "SQL 执行计划变了，突然变慢，帮我排查"
- "这条 SQL 绑定变量窥探有问题，怎么优化"
- "帮我给这个 SQL 出个索引建议"
- "这条 SQL 统计信息过期了，给个优化方案"
- "这个多表 JOIN 太慢了，分析一下连接顺序"
- "帮我分析这个 SQL 的执行计划，看看有没有优化空间"
- "这条分页查询慢，怎么改写"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| sql_id | string | 否 | | 待调优的 SQL_ID（优先使用；为空则需提供 sql_text） |
| sql_text | string | 否 | | 待调优的 SQL 文本（sql_id 为空时使用，用于静态分析） |
| tune_scope | string | 否 | full | 调优范围：full（全维度分析）/ plan（仅执行计划）/ rewrite（仅 SQL 改写）/ index（仅索引建议）/ stats（仅统计信息）/ hint（仅 Hint 调优） |
| include_sql_profile | boolean | 否 | false | 是否在方案中包含 SQL Profile 建议（默认 false，仅输出建议供 DBA 审查） |
| include_sql_rewrite | boolean | 否 | true | 是否在方案中包含 SQL 改写建议（默认 true） |
| include_index_advice | boolean | 否 | true | 是否在方案中包含索引建议（默认 true） |

## 输出示例

```
=== SQL 基本信息 ===
SQL_ID: 8k3u2j1p9x5q
SQL 文本: SELECT o.order_id, o.customer_name, od.product_name, od.quantity
          FROM orders o, order_details od
          WHERE o.order_id = od.order_id
            AND o.order_date >= DATE'2026-01-01'
            AND o.status = 'CONFIRMED'
          ORDER BY o.order_date DESC
执行频率: 1,250 次/小时
平均耗时: 3.2 秒
平均 CPU: 2.8 秒
平均逻辑读: 1,850,000
平均物理读: 12,500
当前执行计划 HASH: 2846171653
历史计划: 稳定（仅 1 个 plan_hash_value）

=== 问题诊断 ===
瓶颈定位: IO 瓶颈（物理读高，全表扫描）
根因分析:
  1. ORDERS 表全表扫描（TABLE ACCESS FULL），order_date 列无索引
  2. ORDERS 与 ORDER_DETAILS 使用 HASH JOIN，ORDER_DETAILS 表被全表扫描
  3. ORDER_DETAILS 表 order_id 列无索引

=== 执行计划解读 ===
| Id | Operation              | Name          | E-Rows | A-Rows |
|----|------------------------|---------------|--------|--------|
|  0 | SELECT STATEMENT       |               |    100 |     50 |
|  1 |  SORT ORDER BY         |               |    100 |     50 |
|* 2 |   HASH JOIN            |               |    100 |     50 |
|* 3 |    TABLE ACCESS FULL   | ORDERS        |  10000 |  8500  |
|* 4 |    TABLE ACCESS FULL   | ORDER_DETAILS |  500K  |  480K  |

解读:
  - ORDERS 全表扫描（8500 行），需在 (status, order_date) 上建复合索引
  - ORDER_DETAILS 全表扫描（480K 行），需在 order_id 上建索引
  - HASH JOIN 合理，但两表全扫导致大量 IO

=== 优化建议（按优先级排序） ===
| 优先级 | 类别 | 建议 | 预期收益 | 风险 |
|--------|------|------|---------|------|
| 高 | 索引 | 创建 idx_orders_status_date ON orders(status, order_date, order_id) | 逻辑读降低 90%+ | 索引维护开销 |
| 高 | 索引 | 创建 idx_od_order_id ON order_details(order_id) 含 product_name, quantity | 逻辑读降低 95%+ | 索引维护开销 |
| 中 | SQL 改写 | 使用 ANSI JOIN 语法替代隐式逗号连接 | 可读性提升 | 无 |
| 低 | 统计信息 | ORDERS 表统计信息已过期 15 天，建议刷新 | 优化器估算更准确 | 无 |

=== SQL 改写建议 ===
原 SQL:
  SELECT o.order_id, o.customer_name, od.product_name, od.quantity
  FROM orders o, order_details od
  WHERE o.order_id = od.order_id
    AND o.order_date >= DATE'2026-01-01'
    AND o.status = 'CONFIRMED'
  ORDER BY o.order_date DESC

改写后:
  SELECT o.order_id, o.customer_name, od.product_name, od.quantity
  FROM orders o
  INNER JOIN order_details od ON o.order_id = od.order_id
  WHERE o.status = 'CONFIRMED'
    AND o.order_date >= DATE'2026-01-01'
  ORDER BY o.order_date DESC

改写理由: 使用 ANSI JOIN 显式声明连接条件，优化器更容易识别连接关系，
         配合建议索引可实现 INDEX RANGE SCAN + INDEX RANGE SCAN + NESTED LOOPS 的高效路径

=== 索引建议 ===
-- 1. ORDERS 表复合索引（等值列 status 在前，范围列 order_date 在后）
CREATE INDEX idx_orders_status_date ON orders(status, order_date, order_id);
-- 维护成本: 低（插入/更新时维护 3 列索引，ORDER 表日均 5000 行写入）

-- 2. ORDER_DETAILS 表覆盖索引
CREATE INDEX idx_od_order_id ON order_details(order_id, product_name, quantity);
-- 维护成本: 中（插入/更新时维护 3 列索引，日均 50000 行写入）

=== 统计信息建议 ===
ORDERS 表统计信息: last_analyzed = 2026-08-02（已过期 15 天）
建议执行: EXEC DBMS_STATS.GATHER_TABLE_STATS('ERP', 'ORDERS',
    estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
    method_opt => 'FOR ALL COLUMNS SIZE AUTO', cascade => TRUE);

=== 验证方案 ===
调优前:
  SELECT /*+ FULL(o) FULL(od) */ ...  -- 模拟调优前全表扫描
调优后:
  SELECT /*+ INDEX(o idx_orders_status_date) INDEX(od idx_od_order_id) */ ...

验证指标:
  - 执行时间: 期望从 3.2s 降至 < 0.1s
  - 逻辑读: 期望从 1,850,000 降至 < 50,000
  - 物理读: 期望从 12,500 降至 < 100
  - 执行计划: INDEX RANGE SCAN + INDEX RANGE SCAN + NESTED LOOPS

=== 回撤方案 ===
如需回退到调优前状态:
  - 删除索引: DROP INDEX idx_orders_status_date; DROP INDEX idx_od_order_id;
  - 无需其他操作（SQL 文本未修改，统计信息刷新不影响正确性）
```

## 安全边界
- 安全等级为 query（只读方案），仅做方案设计。
- 不执行 SQL 改写（不 ALTER SESSION / 不修改 SQL 文本）。
- 不创建/删除索引（不执行 DDL）。
- 不收集统计信息（不执行 DBMS_STATS.GATHER_*）。
- 不绑定 SQL Profile / SPM Baseline（不执行 DBMS_SQLTUNE / DBMS_SPM）。

## 功能限制
- 不执行 DDL/DML/ALTER 操作
- 不修改 SQL 文本、不调整优化器参数
- 不收集统计信息、不创建 SQL Profile/SPM Baseline
- 不调用其它 Skill、不自动修复、仅按需手动触发
- 索引创建、统计信息刷新、SQL Profile 绑定等操作请使用对应执行类技能

## 版本记录
- v1.0.0（2026-08-17）：新建。按出厂标准化落地，单一职责「Oracle SQL 调优方案生成」（query/db-ops），覆盖执行计划分析、SQL 改写、索引建议、统计信息诊断、Hint 调优、绑定变量分析、SQL Profile/SPM Baseline 建议、验证方案与回撤方案，不直接执行。