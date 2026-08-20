# PostgreSQL 慢查询日志深度分析 说明文档

## 能力简介
本技能为只读慢查询分析技能，基于 `pg_stat_statements`、慢查询日志文件、`EXPLAIN ANALYZE`、系统统计视图，定位慢查询根因并给出优化方向建议（不执行任何变更）。

## 适用场景
- 慢查询 TOP N 筛查与统计分析
- 从 PostgreSQL 慢查询日志文件（CSV/TEXT）中批量提取慢 SQL
- 对指定 SQL 执行 EXPLAIN ANALYZE 深度解读，定位瓶颈算子
- 检测全表扫描（Seq Scan）占比高的表
- 查看索引使用率与未使用索引
- 诊断锁等待导致的慢查询
- 分析 auto_explain 自动记录的执行计划
- 表膨胀与 autovacuum 状态与慢查询关联分析

## 触发话术
- "帮我查一下 PostgreSQL 的慢查询有哪些"
- "分析一下这条 SQL 的执行计划，PostgreSQL 的"
- "看看哪些表存在全表扫描，按 Seq Scan 排序"
- "哪些索引一直没被用到，帮我查一下"
- "有没有锁等待导致的慢查询"
- "帮我解析这个 PostgreSQL 慢查询日志文件"
- "分析一下 auto_explain 记录的慢查询执行计划"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | | 目标数据库名（可选，不填则分析所有数据库） |
| sql_text | string | 否 | | 待分析的 SQL 语句（可选，用于 EXPLAIN ANALYZE 解读） |
| log_file_path | string | 否 | | 慢查询日志文件路径（可选，支持 CSV 格式与标准文本格式） |
| top_n | integer | 否 | 20 | 返回慢查询 TOP N 条数 |
| min_duration_ms | integer | 否 | 1000 | 慢查询最小耗时阈值（毫秒） |

## 输出示例

```
=== PostgreSQL 慢查询 TOP5 (pg_stat_statements) ===
1. queryid: 1234567890
   SQL: SELECT * FROM orders WHERE status = $1 AND created_at > $2
   执行次数: 12580  平均耗时: 3250.50ms  总耗时: 40891290.00ms
   最大耗时: 12800.00ms  标准差: 850.30ms
   缓存命中率: 45.20%

=== EXPLAIN ANALYZE 分析 ===
SQL: SELECT * FROM orders WHERE status = 'pending' AND created_at > '2024-01-01'
节点类型: Seq Scan on orders
  实际耗时: 3200.5ms  估算行数: 100000  实际行数: 320
  估算偏差: 312x (统计信息严重过期)
  缓冲区: shared hit=5 read=24500
瓶颈: 缺少索引导致全表扫描，缓冲区命中率极低
建议: 为 (status, created_at) 创建复合索引；执行 ANALYZE orders 刷新统计信息

=== 全表扫描分析 ===
表: public.orders  Seq Scan: 12580 次  Idx Scan: 0 次
死元组比例: 35.2% (需 VACUUM)
建议: 评估为 orders 表添加索引；执行 VACUUM orders 清理死元组

=== 锁等待分析 ===
阻塞PID: 12345 (user: app_user)  被阻塞PID: 12346
等待事件: Lock/transactionid
阻塞SQL: UPDATE orders SET status = 'done' WHERE id = 100
被阻塞SQL: UPDATE orders SET status = 'cancel' WHERE id = 100
阻塞时长: 45.3s
建议: 排查阻塞事务，优化事务逻辑避免长事务
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与分析。
- 不执行任何 DDL/DML、不调整配置，全程可追溯、无高危。
- 本技能为纯诊断分析层，不发起任何写操作。

## 功能限制
- 不创建索引（CREATE INDEX / CREATE INDEX CONCURRENTLY）
- 不修改 SQL 语句内容
- 不刷新统计信息（ANALYZE / VACUUM ANALYZE）
- 不调整 PostgreSQL 配置参数（ALTER SYSTEM / SET）
- 不安装或启用扩展（CREATE EXTENSION）
- 不终止会话（pg_terminate_backend / pg_cancel_backend）
- 索引创建请用 db-postgres-index-design，统计刷新请用 db-postgres-stats-refresh

## 版本记录
- v1.0.0（2026-08-17）：初始版本；基于 pg_stat_statements / 日志文件 / EXPLAIN ANALYZE 的慢查询诊断；safe_level 为 query；涵盖全表扫描、索引使用、锁等待、auto_explain、表膨胀共 9 个分析维度。