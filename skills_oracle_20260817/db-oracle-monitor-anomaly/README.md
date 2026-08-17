# Oracle 历史指标异常检测

## 能力简介
本技能为只读分析技能，基于 AWR 历史快照（DBA_HIST_SYSMETRIC_SUMMARY、DBA_HIST_SYSTEM_EVENT、DBA_HIST_SQLSTAT 等），使用统计学方法（Z-Score / 移动平均偏离度）对 Oracle 历史性能指标进行异常点检测，覆盖 CPU、IO、等待事件、会话数、SQL 性能五个维度，识别突增/突降异常，产出结构化异常报告并给出排查建议（不执行任何变更）。

## 适用场景
- 历史性能异常回溯分析（"昨天下午 3 点数据库为什么慢"）
- CPU/IO/连接数突增突降的根因定位
- 容量规划基线偏离检测
- 周期性性能巡检，自动发现异常时间点
- SQL 执行计划劣化的历史检测
- 大促/变更前后的性能对比异常检测

## 触发话术
- "帮我分析一下最近 7 天 CPU 有没有异常突增的时间点"
- "看看昨天下午数据库 IO 有没有异常延迟"
- "检测一下最近 24 小时有没有 SQL 性能劣化"
- "帮我查一下最近一周的数据库异常指标"
- "数据库昨天下午变慢了，帮我回溯一下是哪个指标出现异常"
- "看看最近 3 天连接数有没有突增"
- "帮我做一次历史指标异常巡检"
- "检测一下 AWR 历史中哪些时间点出现了性能异常"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| anomaly_scope | string | 否 | all | 异常检测范围：all（全部）/ cpu（仅 CPU）/ io（仅 IO）/ wait_event（仅等待事件）/ session（仅会话数）/ sql（仅 SQL 性能劣化） |
| time_range_hours | integer | 否 | 168 | 历史数据回溯时间范围（小时），默认 168（最近 7 天） |
| anomaly_threshold | number | 否 | 2.0 | 异常判定 Z-Score 阈值，默认 2.0（即偏离均值 2 个标准差以上视为异常），值越小越敏感 |
| top_n | integer | 否 | 20 | 返回 TOP N 条异常结果 |
| snap_id_begin | integer | 否 | 0 | AWR 历史查询起始快照 ID（为 0 则自动按 time_range_hours 选择） |
| snap_id_end | integer | 否 | 0 | AWR 历史查询结束快照 ID（为 0 则自动选择最近快照） |

## 输出示例

```
=== 快照范围概览 ===
可用快照: 168 个（快照 ID 1024 ~ 1191）
时间跨度: 2026-08-10 10:00 ~ 2026-08-17 10:00（7 天）
平均快照间隔: 60 分钟

=== CPU 异常检测 ===
Host CPU Utilization 历史均值: 35.2%，标准差: 8.5%
检测到 3 个异常点:

  1. [严重] 2026-08-15 15:00 | Host CPU 65.2% | Z-Score: 3.53 ↑
     关联 TOP SQL:
       SQL_ID 9m7787camwh4m  CPU: 450.2s  Exec: 12,500
         SELECT o.order_id, c.customer_name FROM orders o JOIN ...
       SQL_ID 5k6234abc1234  CPU: 320.8s  Exec: 850
         SELECT /*+ PARALLEL(8) */ * FROM order_items WHERE ...

  2. [警告] 2026-08-14 10:00 | Host CPU 58.5% | Z-Score: 2.74 ↑
  3. [警告] 2026-08-12 14:00 | Database CPU Time Ratio 72.3% | Z-Score: 2.35 ↑

=== IO 异常检测 ===
检测到 2 个异常点:

  1. [严重] 2026-08-15 15:00 | db file sequential read avg_wait_ms: 45.2ms
     Z-Score: 4.12 ↑ | 历史均值: 8.5ms | 标准差: 8.9ms
     delta_waits: 85,200 次

  2. [警告] 2026-08-13 09:00 | log file parallel write avg_wait_ms: 12.5ms
     Z-Score: 2.68 ↑ | 历史均值: 3.2ms | 标准差: 3.5ms

=== 等待事件异常检测 ===
检测到 2 个异常点:

  1. [严重] 2026-08-15 15:00 | User I/O 等待时间: 1,250.5 秒
     Z-Score: 3.85 ↑ | 历史均值: 380.2 秒 | 标准差: 226.1 秒
     深入 TOP 等待事件:
       db file sequential read:  820.5 秒 (65.6%)
       db file scattered read:   320.0 秒 (25.6%)
       direct path read:         110.0 秒 (8.8%)

  2. [警告] 2026-08-13 09:00 | System I/O 等待时间: 280.3 秒
     Z-Score: 2.45 ↑ | 深入 TOP 等待事件:
       log file parallel write:  180.5 秒 (64.4%)
       log file sync:             99.8 秒 (35.6%)

=== 会话数异常检测 ===
检测到 1 个异常点:

  1. [警告] 2026-08-15 15:00 | Session Count: 385
     Z-Score: 2.52 ↑ | 历史均值: 185 | 标准差: 79.4

=== SQL 性能劣化检测 ===
检测到 3 个劣化点:

  1. [严重劣化] 2026-08-15 15:00 | SQL_ID: 9m7787camwh4m
     avg_elapsed_sec: 0.0360s | Z-Score: 4.25 | 均值: 0.0125s | 劣化倍数: 2.88x
     SELECT o.order_id, c.customer_name FROM orders o JOIN ...
     ⚠️ 执行计划 hash 变化: 2853791654 → 3904827613

  2. [警告劣化] 2026-08-15 15:00 | SQL_ID: 5k6234abc1234
     avg_elapsed_sec: 0.3774s | Z-Score: 2.85 | 均值: 0.1502s | 劣化倍数: 2.51x
     SELECT /*+ PARALLEL(8) */ * FROM order_items WHERE ...

  3. [突变劣化] 2026-08-13 14:00 | SQL_ID: 7x8234dde5678
     avg_elapsed_sec: 0.4500s | 超过 p95(0.2018s) 的 2.23 倍
     SELECT * FROM inventory WHERE warehouse_id = :1

=== 综合异常时间线 ===
2026-08-15 15:00 ─── 🔴 多维异常集中爆发
  ├─ CPU:     Host CPU 65.2% (Z=3.53) [严重]
  ├─ IO:      db file sequential read 45.2ms (Z=4.12) [严重]
  ├─ 等待事件: User I/O 1,250.5s (Z=3.85) [严重]
  ├─ 会话数:   Session Count 385 (Z=2.52) [警告]
  └─ SQL:     2 条 SQL 劣化 [严重+警告]

2026-08-14 10:00 ─── 🟡 CPU 偏高
  └─ CPU: Host CPU 58.5% (Z=2.74) [警告]

2026-08-13 09:00 ─── 🟡 IO 异常
  ├─ IO: log file parallel write 12.5ms (Z=2.68) [警告]
  └─ 等待事件: System I/O 280.3s (Z=2.45) [警告]

=== 多维关联分析 ===
🔴 2026-08-15 15:00 为最严重异常时间点，5 个维度同时异常:
   | CPU HIGH + IO HIGH + User I/O HIGH + Session HIGH + SQL 劣化
   | 可能根因: 存储 IO 瓶颈 + 执行计划突变导致连锁反应
   | 排查建议:
   |   1. 检查 2026-08-15 15:00 前后存储 IO 性能（SAN/NAS 延迟）
   |   2. 对比 SQL 9m7787camwh4m 执行计划差异（hash 已变化）
   |   3. 检查该时间点是否有批量任务或应用变更
   |   4. 排查连接数突增来源（连接风暴 vs 连接泄漏）
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与统计分析。
- 不执行任何 DDL/DML、不调整配置，全程可追溯、无高危。
- 不 KILL 会话、不修改参数、不触发告警。

## 功能限制
- 不 KILL 会话/事务（不执行 ALTER SYSTEM KILL SESSION）
- 不修改实例参数（不执行 ALTER SYSTEM SET）
- 不调整表/索引存储参数（不执行 ALTER TABLE/INDEX）
- 不执行 SQL Profile/SPM 操作
- 不调用其它 Skill、不自动修复、仅按需手动触发
- 自包含、单一职责，仅产出异常检测结果与排查建议

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle 历史指标异常检测技能，只读分析（query / db-query），基于 AWR 历史快照（DBA_HIST_SYSMETRIC_SUMMARY、DBA_HIST_SYSTEM_EVENT、DBA_HIST_SQLSTAT 等），使用 Z-Score 统计学方法检测 CPU 异常（Host CPU Utilization、Database CPU Time Ratio、OS Load）、IO 异常（db file sequential/scattered read、log file parallel write 等 IO 等待事件 avg_wait_ms 波动）、等待事件异常（User I/O / System I/O / Concurrency 等等待类累计等待时间突增）、会话数异常（Session Count、Current Logons 突增/突降）、SQL 性能劣化（avg_elapsed_sec、avg_buffer_gets 突变劣化，含执行计划 hash 变化检测），产出结构化异常报告、多维关联分析与根因推断建议。