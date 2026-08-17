# Oracle 数据库迁移方案设计（源端 → 目标）

## 能力简介
本技能针对 Oracle 数据库跨环境/跨版本/跨平台迁移生成完整方案：迁移范围评估（对象清单、数据量、依赖关系）、迁移方式选型（Data Pump expdp/impdp、RMAN 备份恢复/可传输表空间、GoldenGate 实时同步、Data Guard 切换、XTTS 跨平台迁移）、前置检查与准备、分批策略、一致性校验、回滚与割接步骤。本技能为只读方案（query 级），不直接执行。自包含、单一职责。

## 适用场景
- Oracle 跨环境迁移（开发 → 测试 → 生产）
- 跨版本升级迁移（如 11g → 19c、12c → 19c）
- 跨平台迁移（如 AIX → Linux、Solaris → Linux）
- 同城/异地灾备搭建
- 数据整合与迁移（多源归一）
- 机房搬迁 / 存储替换场景下的数据库迁移

## 触发话术
- "把 Oracle 11g 迁到 19c，给出迁移方案"
- "生产库从 AIX 迁到 Linux，怎么设计迁移方案"
- "零停机把 Oracle 迁移到新机房，给个方案"
- "500GB 的 Oracle 库怎么迁移，用什么工具"
- "跨平台迁移 Oracle 有哪些方案"
- "Oracle 迁移需要做哪些前置检查"
- "设计一个 GoldenGate 实时迁移方案"
- "Data Pump 迁移大库怎么分批"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| src_instance | string | 是 | | 源端 Oracle 实例连接串（host:port/service_name） |
| dst_instance | string | 是 | | 目标端 Oracle 实例连接串（host:port/service_name） |
| migration_scope | string | 否 | schema | 迁移范围：full（全库）/ schema（指定 schema）/ tablespace（指定表空间）/ table（指定表） |
| schema_name | string | 否 | | 迁移的 schema 名称（migration_scope=schema 时必填，支持逗号分隔多个） |
| migration_mode | string | 否 | offline | 迁移模式：offline（离线停机迁移）/ online（在线最小停机迁移）/ hybrid（混合模式） |
| src_version | string | 否 | | 源端 Oracle 版本号（如 11.2.0.4 / 19.3.0.0），为空则自动探测 |
| dst_version | string | 否 | | 目标端 Oracle 版本号（如 19.3.0.0），为空则自动探测 |
| src_platform | string | 否 | | 源端操作系统平台（如 Linux x86_64 / AIX），为空则自动探测 |
| dst_platform | string | 否 | | 目标端操作系统平台（如 Linux x86_64），为空则自动探测 |
| parallel_degree | integer | 否 | 4 | 迁移并行度（Data Pump / RMAN 并行通道数） |
| downtime_hours | integer | 否 | 4 | 可接受停机窗口（小时），用于评估方案可行性 |

## 输出示例

```
=== 迁移范围评估 ===
源端: 192.168.1.100:1521/orcl → 目标: 192.168.2.100:1521/orcl19
源端版本: 11.2.0.4 (Linux x86_64) → 目标版本: 19.3.0.0 (Linux x86_64)
字符集: AL32UTF8 → AL32UTF8 (兼容)
数据总量: 8 schema, 共 450 GB

TOP 3 Schema:
  ERP_APP: 320 GB, 1,250 对象
  ERP_RPT: 85 GB, 480 对象
  ERP_CFG: 28 GB, 95 对象

大对象: 3 个大表 > 10GB (最大 85GB: ERP_APP.TRANSACTION_LOG)
分区表: 12 个
物化视图: 8 个
DBLink: 3 个
无效对象: 12 个（需迁移前修复）

=== 迁移方式推荐 ===
主方案: Data Pump (expdp/impdp) + 分批并行
  理由: 同平台跨版本、数据量 450GB、可接受 4h 停机窗口、
        Data Pump 跨版本兼容性最好、工具成熟简单
备选方案: GoldenGate 实时同步
  理由: 如需最小停机（< 30min），OGG 可实现分钟级 RTO，
        但需额外 License 和配置复杂度

=== 前置检查清单 ===
[PASS] 源端归档模式: ARCHIVELOG
[PASS] 字符集兼容: AL32UTF8 → AL32UTF8 (同集)
[PASS] 目标端存储: 可用 800GB > 需求 585GB (450GB × 1.3)
[WARN] 源端补丁: 11.2.0.4.201020 需升级 OJVM 补丁后再迁移
[WARN] DBLink 需重建: 3 个 DBLink 指向源端 IP，需更新为目标端

=== 迁移步骤 ===
阶段1: 源端导出（预计 2h）
  expdp parallel=8 compression=all schemas=ERP_APP,ERP_RPT,ERP_CFG
阶段2: 传输 dump 文件（预计 30min，rsync 同步）
阶段3: 目标端导入（预计 2.5h）
  impdp parallel=8 transform=segment_attributes:n:table
阶段4: 导入后处理（预计 30min）
  编译无效对象 → 收集统计信息 → 重建 DBLink → 刷新物化视图

=== 分批策略 ===
第1批: ERP_CFG (28GB, 小 schema 先行)
第2批: ERP_RPT (85GB)
第3批: ERP_APP 小表 (< 1GB, 约 200 个表)
第4批: ERP_APP 中表 (1~10GB, 约 50 个表)
第5批: ERP_APP 大表 (> 10GB, 3 个表, parallel=16)

=== 一致性校验 ===
对象数量: 双侧对比 object_type 计数
数据量: 双侧对比 num_rows + segment_size
核心表校验: 双侧 ORA_HASH 抽样对比
无效对象: 目标端编译后检查，确保 = 0

=== 割接与回滚 ===
割接时间线:
  T-1h:  通知业务方停写
  T0:    源端应用停服
  T0+5m: 源端置只读，确认无活跃会话
  T0+30m: 最终校验通过
  T1:    切换应用连接串 → 目标端
  T1+30m: 业务验证（功能 + 性能抽检）
  T2:    确认无误，源端保留观察 7 天

回滚方案:
  - 校验失败 → 目标端清理 → 重迁差异
  - 割接后异常 → 切回源端连接串
  - 极端回滚 → 源端完整数据 + 备份，随时恢复

风险提示:
  - 11g → 19c 需关注优化器行为变化（建议导出导入统计信息）
  - 大表分区表需确认分区策略一致
  - DBLink 密码需手动重新配置
  - 物化视图刷新组需在迁移后重新启用
```

## 安全边界
- 安全等级为 query（只读方案），仅做方案设计。
- 不执行任何迁移操作（expdp/impdp/RMAN/OGG/Data Guard 切换）。
- 不修改源端/目标端结构（DDL）、不删除源数据。

## 功能限制
- 不直接执行数据迁移（expdp/impdp/RMAN/OGG 等）
- 不修改源端/目标端结构（表空间、用户、权限）
- 不删除源端数据（迁移完成并校验一致前严禁清理）
- 不执行 Data Guard 切换、OGG 进程启停等操作
- 性能诊断类需求请用对应诊断类技能，SQL 审核请用 SQL 审核类技能

## 版本记录
- v1.0.0（2026-08-17）：新建。按出厂标准化落地，单一职责「Oracle 数据库迁移方案设计（源端 → 目标）」（query/db-ops），覆盖迁移范围评估、方式选型（Data Pump / RMAN / 可传输表空间 / OGG / Data Guard / XTTS）、前置检查、分批策略、一致性校验、割接与回滚，不直接执行。