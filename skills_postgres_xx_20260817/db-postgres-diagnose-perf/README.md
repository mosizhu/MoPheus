# PostgreSQL 综合性能诊断 说明文档

## 能力简介
本技能为只读综合性能诊断技能，一次执行覆盖系统资源层（CPU/内存/IO/连接数）与 PostgreSQL 内部核心指标（缓冲命中率、等待事件、检查点/WAL、vacuum 状态、复制延迟、连接池、查询负载），生成多维度性能健康报告，定位瓶颈并给出优化方向（不执行任何变更）。

## 适用场景
- 数据库整体性能下降（响应变慢、吞吐降低）的根因定位
- 周期性性能抖动（特定时段变慢）的时序对比诊断
- 资源瓶颈定位：CPU 瓶颈、IO 瓶颈、内存不足、连接数打满
- 实例健康度日常巡检（一键生成多维度健康报告）
- 新实例上线前的性能基线采集
- 大促/流量高峰前的容量评估与性能预检

## 触发话术
- "帮我看看 PostgreSQL 整体性能怎么样"
- "数据库最近变慢了，帮我全面诊断一下"
- "PostgreSQL 实例健康检查"
- "帮我做一次性能巡检"
- "CPU 使用率很高，是不是数据库的问题"
- "IO 等待很严重，帮我排查一下"
- "连接数快满了，看看什么情况"
- "帮我采集一下性能基线数据"
- "看看 WAL 生成速率和检查点是否正常"
- "主备复制有没有延迟"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | | 目标数据库名（可选，不填则分析所有数据库） |
| top_n | integer | 否 | 10 | 各维度 TOP N 条数 |
| include_system_metrics | boolean | 否 | true | 是否采集系统层指标（CPU/内存/IO），需操作系统级访问权限 |
| check_interval_sec | integer | 否 | 0 | 连续采集间隔秒数（0=单次采集，>0 则采集两次做差值分析，用于趋势判定） |

## 输出示例

```
=== PostgreSQL 综合性能健康报告 ===
检测时间: 2026-08-17 16:00:00
实例: 192.168.1.100:5432
数据库: mydb

--- 性能评分总览 ---
缓冲命中率: 97.8% (优秀)
连接使用率: 45.2% (正常)
等待事件: IO 类占比 38.5% (关注)
死元组比例: 12.3% (正常)
复制延迟: 0.5 MB (正常)
检查点健康度: 请求检查点占比 42.5% (关注)

总体评分: 78/100 (关注级)

--- 系统资源层概览 ---
活跃连接: 85 / 最大连接: 200 (42.5%)
空闲事务: 3 个 (最长 45.2s)
缓冲命中率: 97.8%
事务提交: 12580 / 回滚: 125 (回滚率 0.98%)
临时文件: 125 MB (排序/哈希溢出)

--- 等待事件分布 ---
IO/DataFileRead: 12 会话 (22.5%)
CPU: 18 会话 (33.9%)
LWLock/WALWriteLock: 8 会话 (15.1%)
Lock/transactionid: 5 会话 (9.4%)
Client/ClientRead: 10 会话 (18.9%)

--- 瓶颈根因 ---
[严重] 检查点请求频率过高 (req_checkpoint_ratio=42.5%)，磁盘 IO 压力大
[关注] IO 等待事件占比 38.5%，建议增大 shared_buffers 或优化检查点参数
[关注] 3 个空闲事务 (idle in transaction) 持有锁超过 5 分钟
[正常] 缓冲命中率 97.8%，内存配置合理
[正常] 复制延迟 0.5 MB，无异常

--- 缓冲命中率明细 ---
数据库: mydb        命中率: 97.8%
索引: idx_orders_status  命中率: 45.2% (关注)
索引: idx_users_email    命中率: 99.9% (正常)

--- 检查点与 WAL ---
定时检查点: 125 次
请求检查点: 92 次 (占比 42.5%)
检查点写入: 8.5 GB
WAL 生成速率: 约 15 MB/s (差值模式)

--- 表膨胀风险 ---
public.orders       死元组比例: 35.2% (关注)
public.audit_log     死元组比例: 28.1% (关注)
public.users         死元组比例: 2.1% (正常)

--- 优化建议 ---
[1] 优先: 调大 max_wal_size 降低请求检查点频率 (db-postgres-config-tune)
[2] 优先: 增大 shared_buffers 提升缓冲命中率 (db-postgres-config-tune)
[3] 关注: 排查空闲事务并终止 (db-postgres-session-manage)
[4] 关注: 对 orders 表执行 VACUUM 清理死元组 (db-postgres-stats-refresh)
[5] 建议: 为 orders.status 列创建索引 (db-postgres-index-design)
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与分析。
- 不执行任何 DDL/DML、不调整配置，全程可追溯、无高危。
- 本技能为纯诊断分析层，不发起任何写操作。

## 功能限制
- 不调整 PostgreSQL 配置参数（ALTER SYSTEM / SET）
- 不创建索引（CREATE INDEX）
- 不刷新统计信息（ANALYZE / VACUUM ANALYZE）
- 不终止会话（pg_terminate_backend / pg_cancel_backend）
- 不安装或启用扩展（CREATE EXTENSION）
- 配置调优请用 db-postgres-config-tune，慢查询请用 db-postgres-diagnose-slow-query，死锁请用 db-postgres-diagnose-deadlock，索引优化请用 db-postgres-index-design

## 版本记录
- v1.0.0（2026-08-17）：初始版本；涵盖系统资源层、缓冲命中率、等待事件、检查点/WAL、vacuum、复制延迟、连接负载、查询负载、配置参数合理性共 10 个诊断维度；safe_level 为 query；支持快照与差值采集双模式。