# Oracle 实时指标监控（CPU / 连接数 / 慢查询数）

## 能力简介
本技能为只读监控技能，从 v$ 动态视图、v$sysmetric 实时指标视图与 ASH 历史采样三个维度，对 Oracle 数据库进行 CPU、连接数、慢查询数的实时监控，产出结构化指标快照并给出阈值对照与建议（不执行任何变更）。

## 适用场景
- 数据库实时状态巡检，快速了解 CPU/连接/慢查询水位
- 连接数异常突增排查（连接风暴/连接泄漏）
- 慢查询数量激增排查（应用变更/执行计划变化）
- 资源水位监控与容量评估
- 日常巡检快照采集

## 触发话术
- "查看 Oracle 数据库当前的 CPU 使用率和连接数"
- "帮我看看数据库有多少慢查询在跑"
- "采集一下数据库的实时指标（CPU、连接、慢查询）"
- "数据库连接数是不是到上限了"
- "看看当前有哪些长时间运行的 SQL"
- "数据库实时状态巡检"
- "查一下 CPU 水位和慢查询数量"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| metric_type | string | 否 | | 指标类型：cpu / connection / slow_query（可选，为空则全量采集） |
| top_n | integer | 否 | 10 | 返回 TOP N 条结果 |
| slow_threshold_sec | integer | 否 | 5 | 慢查询判定阈值（秒） |
| time_range_hours | integer | 否 | 1 | 历史数据查询时间范围（小时） |

## 输出示例
```
=== 实时指标概览 ===
CPU 使用率: 45.2%（正常）  |  连接数: 185/500 (37.0%，正常)  |  当前慢查询: 3 个

=== CPU 维度 ===
OS CPU: 8 核, 使用率 45.2%, Idle 54.8%, Load 2.3
DB CPU 占比: 38.5%（正常）
时间模型:
  DB CPU:                          1,250.30 秒
  sql execute elapsed time:        1,480.00 秒
  parse time elapsed:                 42.50 秒
  hard parse elapsed time:            5.20 秒 (0.4%)

CPU 趋势（最近 1 小时）:
  09:00  42.1% | 09:15  45.8% | 09:30  43.2% | 09:45  44.7% | 10:00  45.2%

=== 连接数维度 ===
当前会话: 185 / sessions 上限: 500 (使用率 37.0%)
当前活跃会话: 12 / 185 (6.5%)
会话状态分布:
  INACTIVE  165 (89.2%)
  ACTIVE     12 (6.5%)
  CACHED      8 (4.3%)

连接来源 TOP 5:
  APP_USER          程序: JDBC Thin Client      120 个连接 (活跃: 8)
  READONLY_USER     程序: sqlplus@host01          45 个连接 (活跃: 1)
  MONITOR_USER      程序: OEM.Custom              8 个连接 (活跃: 0)

长空闲会话（> 30 分钟）: 5 个
  SID 128  APP_USER  idle 95min  logon: 2026-08-17 08:25

=== 慢查询维度 ===
当前慢查询（> 5s）: 3 个
  SID 45   APP_USER  已运行 128s  等待: db file sequential read
    SQL: SELECT o.order_id, c.name FROM orders o JOIN customers c ...
  SID 72   APP_USER  已运行 35s   等待: direct path read
    SQL: SELECT /*+ PARALLEL(4) */ * FROM order_items WHERE ...
  SID 88   APP_USER  已运行 8s    等待: CPU
    SQL: SELECT COUNT(*) FROM transactions WHERE status = 'PENDING'

历史慢查询 TOP 5（按 CPU 时间）:
  1. SQL_ID: 9m7787camwh4m  CPU: 450.2s  Elapsed: 520.3s  Exec: 12500
  2. SQL_ID: 5k6234abc1234  CPU: 320.8s  Elapsed: 380.5s  Exec: 850

慢查询趋势（最近 1 小时）:
  09:45  2 个 | 09:50  3 个 | 09:55  2 个 | 10:00  3 个

=== 阈值对照 ===
✅ CPU 使用率: 45.2%（正常，< 60%）
✅ 连接使用率: 37.0%（正常，< 60%）
✅ 当前慢查询: 3 个（正常，< 5）
⚠️ 长空闲会话: 5 个（建议关注，SID 128 空闲 95min）
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与展示。
- 不执行任何 DDL/DML、不调整配置，全程可追溯、无高危。
- 不 KILL 会话、不修改参数、不触发告警。

## 功能限制
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改实例参数（不执行 ALTER SYSTEM SET）
- 不调整连接数上限（不修改 processes/sessions 参数）
- 不执行 SQL Profile/SPM 操作
- 自包含、单一职责，不调用其他 Skill

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle 实时指标监控技能，只读查询（query / db-query），覆盖 CPU 监控（OS CPU 使用率、DB CPU 占比、时间模型、趋势）、连接数监控（会话数/上限、状态分布、来源分布、长空闲会话检测）、慢查询监控（当前长时间运行 SQL、历史慢查询 TOP N、等待事件分布、ASH 趋势），产出结构化指标快照与阈值对照建议。