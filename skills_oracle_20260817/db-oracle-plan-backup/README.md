# Oracle RMAN 备份策略设计

## 能力简介
本技能根据数据库规模、RPO/RTO 需求与业务特征，生成完整 RMAN 备份策略方案：备份类型选型（全量/增量/归档日志）、备份频率与保留策略、备份目标配置（磁盘/FRA/磁带）、备份性能优化（并行度/压缩/加密/多路复用）、备份校验与完整性检查、恢复策略与演练方案、异地容灾与备份归档。本技能为只读方案（query 级），不实际执行备份。自包含、单一职责。

## 适用场景
- 新建 Oracle 数据库时需要制定备份策略
- 现有备份策略评估与优化（RPO/RTO 不达标）
- 备份窗口与性能权衡分析（备份对业务影响评估）
- 备份存储容量规划与成本估算
- 灾备体系中的备份策略制定（本地 + 异地）
- 合规审计要求的备份策略设计（如金融行业日志保留 6 个月）
- 数据库迁移/升级前的备份加固方案
- 备份加密与数据安全策略设计

## 触发话术
- "给 Oracle 生产库出个 RMAN 备份策略"
- "500GB 的 Oracle 库，RPO 1 小时，怎么设计备份方案"
- "评估一下当前的 RMAN 备份策略是否合理"
- "Oracle 备份存储空间怎么规划，保留 30 天要多少容量"
- "设计一个金融行业合规的 Oracle 备份策略，包含异地容灾"
- "Oracle 大库（> 1TB）增量备份方案怎么设计"
- "RMAN 备份窗口太长，怎么优化"
- "备份加密怎么配置，有哪些注意事项"
- "Oracle 备份校验和恢复演练怎么做"
- "出个 Oracle 备份策略，磁盘 + 磁带两级备份"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name） |
| backup_scope | string | 否 | full | 备份策略范围：full（全量+归档）/ full_incr（全量+增量+归档）/ archivelog_only（仅归档日志）/ custom（自定义） |
| rpo_hours | integer | 否 | 1 | 恢复点目标（小时），即最大可容忍数据丢失时间 |
| rto_hours | integer | 否 | 4 | 恢复时间目标（小时），即最大可容忍恢复耗时 |
| data_size_gb | integer | 否 | 0 | 数据库近似大小（GB），为空则自动探测 |
| backup_dest | string | 否 | disk | 备份目标介质：disk（磁盘/FRA）/ tape（磁带库）/ disk_tape（磁盘+磁带两级）/ cloud（云存储） |
| retention_days | integer | 否 | 7 | 备份保留天数 |
| include_offsite | boolean | 否 | false | 是否包含异地容灾备份策略 |
| include_encryption | boolean | 否 | false | 是否包含备份加密策略 |
| daily_change_pct | integer | 否 | 5 | 日均数据变更比例（%），用于评估增量备份大小 |

## 输出示例

```
=== 环境评估 ===
实例: 192.168.1.100:1521/orcl
版本: Oracle Database 19c Enterprise Edition (19.3.0.0.0)
数据库名: ORCL  |  归档模式: ARCHIVELOG  |  闪回: YES
数据库大小: 450 GB  |  数据文件: 12 个
归档日志日均生成: 12.5 GB  |  峰值: 28.3 GB/天
日志切换频率: 约 4 次/小时
FRA 使用: 120GB / 400GB (30%)

=== RPO/RTO 需求分析 ===
RPO: 1 小时 → 归档日志每 30 分钟备份一次（满足 ≤ 1h 数据丢失）
RTO: 4 小时 → 恢复速率需 ≥ 150 GB/h（450GB / 3h 恢复 + 1h 安全余量）
备份窗口: 凌晨 02:00-06:00（4 小时窗口）

=== 备份策略总览 ===

| 备份类型 | 频率 | 时间窗口 | 目标路径 | 压缩 | 保留 |
|---------|------|---------|---------|------|------|
| 全量备份 (LEVEL 0) | 每周日 | 02:00-06:00 (4h) | /backup/full/ | MEDIUM | 14天 |
| 差异增量 (LEVEL 1) | 每天(周一~六) | 02:00-03:00 (1h) | /backup/incr/ | LOW | 14天 |
| 归档日志 | 每30分钟 | 实时 | /backup/arch/ | LOW | 与全量关联 |
| 控制文件 AUTOBACKUP | 每次备份后 | 自动 | /backup/ctl/ | — | 14天 |

=== RMAN 配置建议 ===
（仅输出方案，不实际执行）

CONFIGURE RETENTION POLICY TO RECOVERY WINDOW OF 14 DAYS;
CONFIGURE CONTROLFILE AUTOBACKUP ON;
CONFIGURE BACKUP OPTIMIZATION ON;
CONFIGURE COMPRESSION ALGORITHM 'MEDIUM';
CONFIGURE DEVICE TYPE DISK PARALLELISM 4;
CONFIGURE ARCHIVELOG DELETION POLICY TO BACKED UP 1 TIMES TO DISK;

=== 备份脚本 ===
（详见方案中的完整脚本模板）

■ 全量备份: /backup/scripts/full_backup.sh  (每周日 02:00)
■ 增量备份: /backup/scripts/incr_backup.sh  (每天 02:00)
■ 归档备份: /backup/scripts/arch_backup.sh  (每 30min)

=== 存储容量估算 ===

| 备份类型 | 单次大小 | 压缩后 | 周次数 | 周总量 |
|---------|---------|--------|--------|--------|
| 全量备份 | 450 GB | 150 GB (3x) | 1 | 150 GB |
| 差异增量 | 22.5 GB | 11.3 GB (2x) | 6 | 67.8 GB |
| 归档日志 | 6.25 GB | 3.1 GB (2x) | 336 | — |
| 控制文件 | 50 MB | 16 MB | 7 | 112 MB |

保留 14 天总需求: 约 440 GB (含 20% 安全余量)
建议备份目录大小: ≥ 600 GB

=== 备份校验方案 ===

| 校验类型 | 频率 | 命令 |
|---------|------|------|
| 交叉检查 | 每天 | CROSSCHECK BACKUP; CROSSCHECK ARCHIVELOG ALL; |
| 备份集校验 | 每天 | VALIDATE BACKUPSET <bs_key>; |
| 恢复校验 | 每周 | RESTORE DATABASE VALIDATE; |
| 完整校验 | 每月 | RESTORE VALIDATE CHECK LOGICAL DATABASE; |
| 异机恢复演练 | 每季度 | 独立环境全量恢复 + 业务验证 |

=== 恢复方案 ===

恢复时间预估:
- 全量恢复: 450GB / 150GB/h ≈ 3 小时
- 增量恢复: 11.3GB × 3(最大值) / 150GB/h ≈ 0.2 小时
- 归档应用: 12.5GB × 7(最大值) / 100GB/h ≈ 0.9 小时
- 总计: 约 4.1 小时（满足 RTO 4h 要求）

恢复步骤:
1. STARTUP NOMOUNT
2. RESTORE CONTROLFILE FROM AUTOBACKUP
3. ALTER DATABASE MOUNT
4. RESTORE DATABASE  (自动选择最优恢复链)
5. RECOVER DATABASE
6. ALTER DATABASE OPEN RESETLOGS

=== 监控与告警建议 ===

| 监控项 | 告警阈值 | 检查方式 |
|--------|---------|---------|
| 最近备份时间 | > 24h 无备份 | v$rman_backup_job_details |
| 备份失败 | 任一作业失败 | 日志 ERROR 检查 |
| 归档积压 | > 50 个未备份 | v$archived_log WHERE backed_up='NO' |
| FRA 使用率 | > 80% | v$recovery_file_dest |
| 备份目录空间 | > 80% | df -h /backup |
| 备份超时 | > 预期窗口 | elapsed_seconds 对比 |

风险提示:
- 备份窗口内若有大事务可能导致归档日志暴增，建议高峰前增加临时归档备份
- 启用压缩会增加 CPU 开销，建议在业务低峰期执行全量备份
- 备份集保留策略变更需谨慎，确保不会误删仍需要的归档日志
- 强烈建议定期（至少每季度）执行异机恢复演练，验证备份可恢复性
```

## 安全边界
- 安全等级为 query（只读方案），仅做方案设计。
- 不实际执行 RMAN 备份（BACKUP DATABASE / BACKUP ARCHIVELOG / BACKUP INCREMENTAL）。
- 不修改 RMAN 配置（CONFIGURE ... / ALTER SYSTEM SET）。
- 不恢复数据库（RESTORE DATABASE / RECOVER DATABASE / DUPLICATE）。
- 不删除备份片（DELETE OBSOLETE / DELETE EXPIRED BACKUP）。

## 功能限制
- 不实际执行 RMAN 备份操作
- 不修改 RMAN 持久化配置
- 不恢复数据库
- 不删除备份文件
- 不执行备份校验（RESTORE VALIDATE / BACKUP VALIDATE）
- 性能诊断类需求请用对应诊断类技能，SQL 审核请用 SQL 审核类技能

## 版本记录
- v1.0.0（2026-08-17）：新建。按出厂标准化落地，单一职责「Oracle RMAN 备份策略设计」（query/db-ops），覆盖备份类型选型（全量/增量/归档）、频率与保留策略、备份目标配置（磁盘/FRA/磁带）、性能优化（并行度/压缩/加密/多路复用）、校验与完整性检查、恢复策略与演练、异地容灾与备份归档，不直接执行。