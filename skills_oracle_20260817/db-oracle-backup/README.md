# Oracle RMAN 备份执行

## 能力简介
本技能执行 Oracle RMAN 备份操作：全量备份（FULL/LEVEL 0）、增量备份（差异增量/累积增量 LEVEL 1）、归档日志备份、备份校验与交叉检查、备份集删除清理、备份状态查询。本技能为 danger 级操作技能，实际执行 RMAN 命令，使用前需确认备份策略与窗口。

## 适用场景
- 日常定时备份执行（全量/增量/归档日志）
- 数据库变更前（升级/迁移/DDL）的临时全量备份
- 备份策略调整后的首次基准备份
- 归档日志积压时的紧急备份清理
- 备份校验与交叉检查（定期验证备份可恢复性）
- 备份集过期清理与空间回收
- 备份作业状态查询与历史回溯

## 触发话术
- "对 Oracle 生产库执行一次全量备份"
- "给 orcl 实例做个增量 LEVEL 0 基准备份"
- "执行归档日志备份，备份后删除原文件"
- "交叉检查一下最近的备份集是否完整"
- "验证一下备份集能否恢复"
- "清理过期的 Oracle 备份"
- "查一下最近 7 天的备份状态"
- "对 Oracle 做差异增量备份"
- "执行累积增量备份，减少恢复步骤"
- "备份到磁带，用于异地归档"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name） |
| backup_type | string | 否 | full | 备份类型：full（全量备份）/ incr0（增量 LEVEL 0 基准）/ incr1_diff（差异增量 LEVEL 1）/ incr1_cuml（累积增量 LEVEL 1）/ archivelog（仅归档日志备份）/ validate（仅校验备份）/ crosscheck（交叉检查）/ status（仅查询备份状态） |
| backup_dest | string | 否 | disk | 备份目标介质：disk（磁盘）/ tape（磁带） |
| backup_path | string | 否 | /backup | 磁盘备份路径 |
| parallelism | integer | 否 | 4 | 备份并行通道数 |
| compression | string | 否 | | 压缩算法：BASIC/LOW/MEDIUM/HIGH，为空则不压缩 |
| tag | string | 否 | | 备份集标签（TAG），为空则自动生成 |
| include_archivelog | boolean | 否 | true | 全量/增量备份时是否同时备份归档日志 |
| delete_obsolete | boolean | 否 | false | 备份完成后是否清理过期备份（需确认） |
| duration_minutes | integer | 否 | 0 | 备份窗口限制（分钟），0 表示不限制 |
| rate_limit_mb | integer | 否 | 0 | 备份速率限制（MB/s），0 表示不限制 |

## 输出示例

```
=== 前置检查 ===
实例: 192.168.1.100:1521/orcl
数据库名: ORCL | 版本: 19.3.0.0.0
状态: OPEN | 归档模式: ARCHIVELOG
备份路径: /backup | 可用空间: 850 GB
最近备份: 2026-08-16 02:05:23 (全量备份, 耗时 45min)
未备份归档日志: 12 个 (约 380 MB)

=== 备份执行 ===
备份类型: 全量备份 (FULL)
开始时间: 2026-08-17 02:00:15
结束时间: 2026-08-17 02:48:32
耗时: 48 分 17 秒
状态: SUCCESS

=== 备份集详情 ===
备份集号: 2456
输入大小: 450 GB
输出大小: 148 GB
压缩比: 3.04x
备份片: /backup/full/ORCL_FULL_20260817_2456_1.bak ~ _4.bak
TAG: FULL_BACKUP_20260817

=== 后处理 ===
交叉检查: 完成 (2456 个备份集全部有效)
归档日志备份: 12 个归档日志已备份并删除
过期备份清理: 未启用 (delete_obsolete=false)

=== 备份状态汇总 ===
最近备份: 2026-08-17 02:48:32 (全量备份, SUCCESS)
最近 7 天备份成功率: 100% (7/7)
未备份归档日志: 0 个
```

## 安全边界
- 安全等级为 danger（实际执行操作），执行 RMAN 备份命令。
- 不执行数据库恢复（RESTORE DATABASE / RECOVER DATABASE / DUPLICATE）。
- 不修改非备份相关 RMAN 配置（加密/压缩策略由 db-oracle-plan-backup 方案确定）。
- 不执行 DDL/DML 操作。
- DELETE OBSOLETE / DELETE EXPIRED BACKUP 需明确设置 `delete_obsolete=true` 才执行。

## 功能限制
- 不执行数据库恢复操作
- 不修改非备份相关 RMAN 持久化配置
- 不执行 DDL/DML
- 不 KILL 会话、不修改数据库参数
- 大库备份可能耗时数小时，需关注备份窗口

## 版本记录
- v1.0.0（2026-08-17）：新建。按出厂标准化落地，单一职责「Oracle RMAN 备份执行」（danger/db-ops），覆盖全量/增量/归档日志备份、备份校验与交叉检查、备份集清理、备份状态查询，实际执行 RMAN 命令。