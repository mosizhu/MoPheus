# Oracle DataGuard 主备切换（SWITCHOVER）

## 能力简介
本技能执行 Oracle DataGuard 计划内主备角色切换，核心特征：**双人审批（双签）门禁 + 完整前置校验链 + 切换执行 + 切换后验证**。切换操作不可逆，影响数据库服务连续性，执行前必须完成双签确认与前置校验。

## 适用场景
- 计划内硬件维护（主库服务器需停机维护，提前切换至备库）
- 系统升级/补丁应用（先切换后对原主库进行升级）
- 灾备演练（定期验证主备切换能力与 RTO/RPO）
- 负载均衡（主备角色互换以分散负载）
- 数据中心迁移（配合 DG 实现最小停机迁移）
- 控制文件损坏修复后的主备重新对齐
- DG 配置调整后的角色同步验证

## 触发话术
- "对 Oracle DG 执行主备切换"
- "把 orcl 主库切换到备库 orcl_stby"
- "先校验一下 DG 切换的前置条件"
- "通过 DataGuard Broker 执行主备切换"
- "灾备演练，执行主备切换并验证"
- "检查 DG 同步状态，确认是否可以切换"
- "双签审批通过，执行主备角色互换"
- "切换前等待备库追上主库，超时 10 分钟"
- "主库硬件维护，需要先切换到备库"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 当前主库 Oracle 实例连接串（host:port/service_name） |
| switchover_type | string | 否 | switchover | 切换类型：switchover（标准切换）/ validate（仅校验）/ dg_broker（Broker 切换） |
| standby_host | string | 否 | | 备库实例连接串，switchover 模式下必填 |
| standby_unique_name | string | 否 | | 备库 DB_UNIQUE_NAME，不填则自动识别 |
| primary_unique_name | string | 否 | | 主库 DB_UNIQUE_NAME，不填则自动识别 |
| max_lag_seconds | integer | 否 | 30 | 允许的最大备库延迟（秒），超过阈值终止切换 |
| max_lag_mb | integer | 否 | 100 | 允许的最大备库延迟（MB），超过阈值终止切换 |
| validate_only | boolean | 否 | true | 是否仅做前置校验（默认 true），设为 false 且双签通过后才实际执行 |
| wait_timeout_seconds | integer | 否 | 600 | 等待备库追上主库的超时时间（秒） |
| approver_one | string | 否 | | 第一审批人标识（双签第一签，高危操作必填） |
| approver_two | string | 否 | | 第二审批人标识（双签第二签，高危操作必填） |
| skip_checks | boolean | 否 | false | 是否跳过前置校验（不推荐，仅极端紧急场景） |

## 输出示例

### 前置校验输出（validate_only=true，默认模式）

```
=== 双签审批记录 ===
第一审批人: zhang.san
第二审批人: li.si
审批时间: 2026-08-17 15:30:00
审批结果: 通过

=== 前置校验报告 ===
主库: 192.168.1.100:1521/orcl
备库: 192.168.1.101:1521/orcl_stby

[通过] 主库角色: PRIMARY (ORCL)
[通过] 备库角色: PHYSICAL STANDBY (ORCL_STBY)
[通过] 主库 Switchover 就绪: TO STANDBY
[通过] 备库 Switchover 就绪: TO PRIMARY
[通过] 归档传输状态: VALID
[通过] GAP 检查: NO GAP
[通过] 同步延迟: apply lag = 0 秒 (SCN gap = 0)
[通过] 数据文件数量: 主备一致 (45 个)
[通过] 数据文件状态: 全部 ONLINE
[通过] 监听可达性: 可达
[通过] SRL 配置: 8 组 (在线 REDO 4 组 + 1 = 5，满足)
[通过] SRL 大小: 与在线 REDO 一致 (512 MB)
[警告] FRA 空间: 主库 72% / 备库 65% (正常)

=== 校验结论 ===
结果: 通过 (10/10 通过，0 阻断，1 告警)
建议: 所有关键检查项均已通过，可以执行切换。

=== 切换窗口预估 ===
预计切换耗时: 2-5 分钟
服务中断窗口: 约 2-5 分钟（主库切换 → 备库接管 → 新主库 OPEN）
风险等级: 低（计划内切换，同步零延迟）

=== 下一步 ===
确认校验结果无误后，设置 validate_only=false 并确认双签信息，执行实际切换。
```

### 切换执行输出（validate_only=false，双签通过）

```
=== 双签审批记录 ===
第一审批人: zhang.san
第二审批人: li.si
审批时间: 2026-08-17 15:32:00
审批结果: 通过（执行授权）

=== 切换执行 ===
开始时间: 2026-08-17 15:33:00

[步骤 1] 主库切换为备库...
  主库 SWITCHOVER TO PHYSICAL STANDBY: 成功
  原主库 SHUTDOWN: 成功
  原主库 STARTUP MOUNT: 成功
  耗时: 45 秒

[步骤 2] 备库切换为主库...
  备库 SWITCHOVER TO PRIMARY: 成功
  新主库 OPEN: 成功
  耗时: 38 秒

[步骤 3] 新备库启动 MRP...
  MRP 启动: 成功 (实时应用模式)
  耗时: 12 秒

=== 切换前后状态对比 ===
                                    切换前                    切换后
  主库角色 (192.168.1.100)          PRIMARY →                 PHYSICAL STANDBY
  备库角色 (192.168.1.101)          PHYSICAL STANDBY →         PRIMARY
  主库 OPEN_MODE                    READ WRITE →               MOUNTED
  备库 OPEN_MODE                    READ ONLY WITH APPLY →     READ WRITE
  归档传输方向                      .100 → .101 →             .101 → .100

=== 切换后验证 ===
[通过] 新主库角色: PRIMARY (ORCL_STBY @ 192.168.1.101)
[通过] 新备库角色: PHYSICAL STANDBY (ORCL @ 192.168.1.100)
[通过] 新主库读写验证: 成功
[通过] 新备库 MRP: 运行中 (实时应用)
[通过] 归档传输: VALID (新主库 → 新备库)
[通过] 同步延迟: apply lag = 0 秒
[通过] 数据文件一致性: 全部 ONLINE

总耗时: 1 分 35 秒
服务中断: 约 1 分 15 秒
切换结果: 成功

=== 回退方案 ===
如需回退，执行反向 SWITCHOVER：
1. 新主库 (192.168.1.101) 切换为备库
2. 新备库 (192.168.1.100) 切换为主库
3. 新备库启动 MRP
注：回退操作同样需要双签审批。
```

## 安全边界
- 安全等级为 danger（高危操作），执行 DataGuard 主备角色切换，需双人审批（双签）。
- **不执行 Failover**（强制故障切换，不可逆），仅支持计划内 SWITCHOVER。
- 不修改 DG 配置参数（LOG_ARCHIVE_DEST_n / FAL_SERVER / FAL_CLIENT 等）。
- 不修改 DataGuard Broker 配置。
- 不执行数据库备份/恢复、不执行 DDL/DML。
- 切换过程中主备库均不可提供读写服务（短暂中断），业务需提前感知。
- 切换前必须完成双签与前置校验，默认仅校验模式（validate_only=true）。

## 功能限制
- 不执行 Failover（强制故障切换）
- 不修改 DG 配置参数
- 不修改 Broker 配置
- 不执行备份/恢复
- 不执行 DDL/DML
- 不调用其他 Skill
- SWITCHOVER 操作不可逆，切换后需执行反向 SWITCHOVER 才能恢复原角色
- 切换期间存在短暂服务中断，需提前通知业务方

## 版本记录
- v1.0.0（2026-08-17）：新建。按出厂标准化落地，单一职责「Oracle DataGuard 主备切换（SWITCHOVER）」（danger/db-ops），双人审批（双签）门禁 + 完整前置校验链（DG 配置/同步延迟/归档连续性/SRL 配置/FRA 空间/数据文件一致性/监听可达性）+ 支持 SQL*Plus 与 Broker 两种切换模式 + 切换后自动验证 + 回退方案，覆盖计划内主备角色互换场景。