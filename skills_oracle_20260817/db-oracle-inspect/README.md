# Oracle 数据库健康巡检 说明文档

## 能力简介
本技能为只读巡检技能，从 Oracle 数据字典（DBA_*/V$ 视图）全面采集数据库健康指标，涵盖实例基础信息、配置参数、表空间存储、性能基线、等待事件、会话负载、备份状态、DG 同步、对象状态、告警日志等 10 大维度，产出结构化健康报告与综合评分（不执行任何变更）。

## 适用场景
- 定期数据库健康巡检（建议每周/每月执行）
- 新实例上线前环境验收
- 故障排查前的全面体检
- 运维交接时环境盘点
- 合规审计前的数据库状态自检
- 容量规划基础数据采集
- 数据库迁移/升级前状态基线

## 触发话术
- "对 orcl 做一次全面巡检"
- "帮我检查一下数据库的健康状态"
- "生成一份数据库健康报告"
- "巡检一下数据库看看有没有问题"
- "检查所有表空间的使用率"
- "看看最近备份有没有正常执行"
- "数据库上线前做一次环境验收"
- "帮我看看数据库的各项性能指标"
- "检查一下有没有无效对象和慢查询"
- "扫描一下最近 7 天的告警日志"
- "对 192.168.1.100:1521/orcl 做一次完整巡检"
- "只巡检表空间和备份状态"
- "帮我看看数据库的各项命中率"
- "检查 DG 备库同步有没有延迟"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名） |
| inspect_scope | string | 否 | full | 巡检范围：full（全面巡检）/ basic（基础信息+表空间+性能）/ perf（仅性能指标）/ storage（仅存储与表空间）/ backup（仅备份与 DG）/ security（仅对象状态与安全） |
| alert_log_days | integer | 否 | 7 | 告警日志扫描天数，默认最近 7 天 |
| tablespace_alert_pct | integer | 否 | 80 | 表空间使用率告警阈值（%），超过此阈值标记为告警 |
| top_n | integer | 否 | 10 | 返回 TOP N 条等待事件 / SQL |
| include_asm | boolean | 否 | true | 是否包含 ASM 磁盘组巡检 |
| include_dg | boolean | 否 | true | 是否包含 DataGuard 备库同步状态检查 |

## 输出示例

### 全面巡检输出（inspect_scope=full）

```
╔══════════════════════════════════════════════════════════════════╗
║                   Oracle 数据库健康巡检报告                        ║
╠══════════════════════════════════════════════════════════════════╣
║ 巡检时间: 2026-08-17 10:00:00                                    ║
║ 巡检范围: full（全面巡检）                                        ║
╚══════════════════════════════════════════════════════════════════╝

=== 一、实例基础信息 ===
数据库名:       ORCL
实例名:         orcl1
主机名:         db-server-01
版本:           19.19.0.0.0
运行时间:       45.32 天
归档模式:       ARCHIVELOG
数据库角色:     PRIMARY
Open Mode:      READ WRITE
闪回:           ON
强制日志:       YES
字符集:         AL32UTF8
平台:           Linux x86 64-bit

=== 二、配置参数摘要 ===
memory_target:         8.00 GB
sga_target:            0.00 GB（使用 memory_target 自动管理）
pga_aggregate_target:  0.00 GB（使用 memory_target 自动管理）
processes:             1500
sessions:              2272
open_cursors:          2000
db_block_size:         8192 Bytes
undo_retention:        900 秒
REDO 日志组数:         4
REDO 日志大小:         2048 MB × 4 组

=== 三、表空间使用率 ===
表空间名              总大小(MB)    已用(MB)    空闲(MB)    使用率(%)    状态
SYSAUX                 1,280.00      1,100.00      180.00      85.94     WARNING
USERS                 50,000.00     42,500.00    7,500.00      85.00     WARNING
UNDOTBS1              10,240.00      3,200.00    7,040.00      31.25     OK
SYSTEM                 1,024.00        680.00      344.00      66.41     OK
TEMP                   5,120.00      3,800.00    1,320.00      74.22     OK

⚠ 告警表空间:
  - SYSAUX: 85.94%（使用中，建议扩展）
  - USERS: 85.00%（使用中，建议扩展）

表空间增长趋势（最近 30 天）:
  - USERS: +2,500 MB（日均 +83.33 MB）
  - SYSAUX: +120 MB（日均 +4.00 MB）

ASM 磁盘组:
  DG_NAME   总大小(GB)   已用(GB)   空闲(GB)   使用率(%)   状态
  DATA          500.00     320.00     180.00      64.00     MOUNTED
  FRA           200.00     120.00      80.00      60.00     MOUNTED

=== 四、性能基线 ===
指标名称                    当前值(%)    状态      健康阈值
Buffer Cache Hit Ratio       98.52       OK        > 95%
Library Cache Hit Ratio      97.80       OK        > 95%
Soft Parse Ratio             94.20       WARNING   > 95%
Memory Sorts Ratio           99.50       OK        > 95%
Row Cache Hit Ratio          92.30       OK        > 90%
Latch Hit Ratio              99.85       OK        > 99%

⚠ 注意: Soft Parse Ratio 偏低(94.20%)，建议检查绑定变量使用情况

=== 五、等待事件 TOP 5 ===
当前实时等待:
  等待事件                             等待类        会话数    占比
  db file sequential read             User I/O        12    35.3%
  log file sync                       Commit           6    17.6%
  db file scattered read              User I/O         4    11.8%
  SQL*Net message from client         Network          3     8.8%
  enq: TX - row lock contention       Application      2     5.9%

等待类分布（自启动累计）:
  User I/O:      45.2% (12,850.50 秒)
  System I/O:    18.5% (5,260.30 秒)
  Commit:        12.3% (3,498.20 秒)
  Concurrency:    8.1% (2,302.10 秒)
  Network:        5.5% (1,564.80 秒)

=== 六、会话负载 ===
会话统计:
  状态          类型      数量
  ACTIVE       USER        18
  INACTIVE     USER       142
  ACTIVE       BACKGROUND  35
  INACTIVE     BACKGROUND   5

活动会话 TOP 用户:
  APP_USER:     12 个活跃会话
  DBA_USER:      3 个活跃会话
  REPORT_USER:   2 个活跃会话

连接来源 TOP 3:
  app-server-01:  85 个连接 (53.1%)
  app-server-02:  45 个连接 (28.1%)
  report-server:  20 个连接 (12.5%)

资源使用率:
  会话数: 200 / 2272 (8.8%)
  进程数: 185 / 1500 (12.3%)
  打开游标: 850 / 2000 (42.5%)

阻塞会话: 1 个
  SID 128 (APP_USER) 被 SID 45 (APP_USER) 阻塞:
    等待事件: enq: TX - row lock contention
    等待时间: 120 秒
    SQL_ID: 9m7787camwh4m

长时间运行 SQL（> 5 分钟）:
  SID  | 用户       | 运行时间 | 等待事件                      | SQL_ID
  56   | APP_USER   | 18 分钟  | db file scattered read       | 5k6234abc1234
  128  | APP_USER   | 12 分钟  | enq: TX - row lock contention| 9m7787camwh4m

=== 七、备份状态 ===
最近备份记录:
  备份类型          状态      开始时间             完成时间             耗时     大小
  DB FULL          COMPLETED  2026-08-16 02:00:00  2026-08-16 02:45:32  45.5min  48.2GB
  ARCHIVELOG       COMPLETED  2026-08-17 00:00:00  2026-08-17 00:02:15  2.2min   0.5GB
  DB INCR LEVEL1   COMPLETED  2026-08-17 02:00:00  2026-08-17 02:12:30  12.5min  5.8GB

归档日志连续性:
  Thread 1: 序列号 45210 ~ 45320, 无 GAP ✓

闪回恢复区:
  空间限制: 200.00 GB
  已使用:   120.00 GB (60.0%)
  可回收:    15.00 GB
  文件数:    245

=== 八、DG 同步状态 ===
归档目标: dest_2 (ORCL_STBY)
  状态:          VALID
  同步模式:      SYNCHRONIZING
  GAP:           NO GAP

传输延迟: 0 秒
应用延迟: 0 秒

=== 九、无效对象 ===
无效对象: 3 个
  对象类型      所有者        数量
  PROCEDURE     APP_USER      2
  PACKAGE BODY  APP_USER      1

详情:
  所有者      对象名               对象类型        最后 DDL 时间
  APP_USER    PROC_UPDATE_ORDER   PROCEDURE       2026-08-10 15:30:00
  APP_USER    PROC_IMPORT_DATA    PROCEDURE       2026-08-12 09:00:00
  APP_USER    PKG_REPORT_UTIL     PACKAGE BODY    2026-08-08 14:00:00

不可用索引: 0 个 ✓

统计信息陈旧对象（> 30 天未更新）: 12 个表

=== 十、告警日志 ===
最近 7 天 ORA- 错误统计:
  错误代码        出现次数      首次出现              最后出现
  ORA-00060        5 次         2026-08-15 14:22:00   2026-08-17 08:15:00
  ORA-01555        3 次         2026-08-13 10:00:00   2026-08-16 16:45:00
  ORA-00001        2 次         2026-08-16 11:00:00   2026-08-16 11:05:00

⚠ ORA-00060（死锁检测）: 出现 5 次，建议检查死锁详情
⚠ ORA-01555（快照过旧）: 出现 3 次，建议增大 UNDO_RETENTION 或优化长查询

=== 十一、综合健康评分 ===
┌──────────────┬──────┬──────────┬────────────────────────────────┐
│ 维度          │ 权重 │ 得分     │ 说明                           │
├──────────────┼──────┼──────────┼────────────────────────────────┤
│ 表空间        │ 20   │ 16 / 20  │ 2 个表空间 WARNING 扣 4 分    │
│ 性能          │ 25   │ 20 / 25  │ Soft Parse 不达标扣 5 分      │
│ 会话          │ 10   │ 10 / 10  │ 正常                          │
│ 备份          │ 15   │ 15 / 15  │ 备份正常                      │
│ DG            │ 10   │ 10 / 10  │ 同步正常                      │
│ 对象          │ 10   │  7 / 10  │ 3 个无效对象扣 3 分            │
│ 告警          │ 10   │  5 / 10  │ 存在 ORA-00060 错误扣 5 分    │
├──────────────┼──────┼──────────┼────────────────────────────────┤
│ 总分          │ 100  │ 83 / 100 │ 健康等级: B（良好）           │
└──────────────┴──────┴──────────┴────────────────────────────────┘

健康等级:
  A（优秀）: ≥ 90 分
  B（良好）: 80 ~ 89 分
  C（一般）: 60 ~ 79 分
  D（较差）: < 60 分

=== 风险项汇总 ===
1. [中] 表空间 SYSAUX 使用率 85.94%，建议扩展
2. [中] 表空间 USERS 使用率 85.00%，建议扩展
3. [中] Soft Parse Ratio 偏低(94.20%)，建议检查绑定变量使用
4. [低] 存在 3 个无效对象，建议重新编译
5. [低] 存在 ORA-00060 死锁错误，建议分析死锁原因
6. [低] 存在 ORA-01555 快照过旧错误，建议增大 UNDO_RETENTION

=== 修复建议 ===
1. 扩展表空间: ALTER TABLESPACE SYSAUX ADD DATAFILE SIZE 2G;
2. 编译无效对象: EXEC DBMS_UTILITY.COMPILE_SCHEMA('APP_USER');
3. 检查绑定变量: 分析 v$sql 中 FORCE_MATCHING_SIGNATURE 重复的 SQL
4. 死锁分析: 使用 db-oracle-diagnose-deadlock 技能分析死锁详情
5. UNDO 优化: ALTER SYSTEM SET UNDO_RETENTION=1800;
```

### 基础巡检输出（inspect_scope=basic）

```
=== 巡检概览 ===
数据库: ORCL (19.19.0.0.0) | 运行: 45.32 天 | 归档模式: ARCHIVELOG

=== 表空间使用率 ===
SYSAUX: 85.94% ⚠ WARNING
USERS:  85.00% ⚠ WARNING
其他表空间正常

=== 性能基线 ===
Buffer Cache Hit: 98.52% OK
Library Cache Hit: 97.80% OK
Soft Parse Ratio: 94.20% ⚠ WARNING

=== 综合评分 ===
基础巡检得分: 70 / 80（跳过 DG/备份/对象/告警维度）
```

## 安全边界
- 安全等级为 query（只读安全），仅做查询与参考
- 不执行任何 DDL/DML、不调整配置、不 KILL 会话
- 全程可追溯、无高危操作

## 功能限制
- 纯只读巡检，不执行任何变更操作
- 不修改数据库参数、不执行备份恢复
- 不生成 AWR 快照、不收集统计信息
- 不调用其他 Skill、不自动修复
- 告警日志扫描依赖数据库版本（12c+ 支持 v$diag_alert_ext，11g 需外部表）
- ASM 和 DG 检查在非 ASM/DG 环境中自动跳过

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle 数据库健康巡检技能，query 安全等级，覆盖 10 大巡检维度：实例基础信息、配置参数、表空间存储、性能基线、等待事件、会话负载、备份状态、DG 同步、对象状态、告警日志，产出结构化健康报告与综合评分（A/B/C/D 四级），支持 full/basic/perf/storage/backup/security 六种巡检范围。