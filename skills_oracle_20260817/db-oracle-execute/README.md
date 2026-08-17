# Oracle 普通 DDL/DML 执行（带自动回滚）

## 能力简介
本技能执行 Oracle DDL/DML 操作，核心特征：**所有变更操作自动记录回滚所需信息，DML 失败自动回滚到 SAVEPOINT，DDL 产出反向 DDL 以便回退**。轻量化、自包含、不依赖其他 Skill。

## 适用场景
- 表结构变更：添加/删除/修改列、重命名表/列、修改约束
- 索引维护：创建/删除普通索引
- 数据订正：少量 UPDATE/DELETE 数据修正
- 批量数据操作：大批量 INSERT/UPDATE/DELETE（分批提交）
- 开发/测试环境快速变更与回退
- 变更前的安全试运行（dry_run 模式）

## 触发话术
- "在 Oracle 生产库的 orders 表加一个 remark 列"
- "给 orcl 实例的 users 表批量更新 status 字段"
- "安全删除 orders 表中 90 天前的日志数据"
- "先试运行看看这个 ALTER TABLE 的影响"
- "对 Oracle 执行这个 DDL，帮我生成回滚 SQL"
- "批量 INSERT 数据，每 5000 行提交一次"
- "删除这个索引，保留回滚 DDL"
- "DROP TABLE 用回收站恢复的方式"
- "执行 MERGE 同步两表数据"
- "TRUNCATE 这张表（我知道不可回滚，确认执行）"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 是 | | 目标 Oracle 实例连接串（host:port/service_name） |
| sql_text | string | 是 | | 待执行的 SQL 语句（支持单条 DDL 或 DML） |
| execute_type | string | 否 | auto | 执行类型：auto（自动识别）/ ddl（强制 DDL 模式）/ dml（强制 DML 模式） |
| auto_rollback | boolean | 否 | true | DML 执行后是否自动回滚（默认 true，验证无误后需再次设 false 提交） |
| dry_run | boolean | 否 | false | 是否为试运行模式，true 时仅解析并输出回滚方案 |
| commit_batch_size | integer | 否 | 0 | DML 分批提交行数（0 表示不分批），建议 5000~10000 |
| timeout_seconds | integer | 否 | 300 | DML 执行超时时间（秒），超时自动回滚 |

## 输出示例

### DDL 执行示例（ALTER TABLE 加列）

```
=== SQL 解析 ===
SQL 类型: DDL (ALTER TABLE)
操作对象: SCHEMA.ORDERS
操作内容: ADD COLUMN (remark VARCHAR2(500) DEFAULT NULL)

=== 前置检查 ===
实例: 192.168.1.100:1521/orcl
数据库: ORCL | 版本: 19.3.0.0.0 | 状态: OPEN
表大小: 2.5 GB (8,500,000 行)
回收站: ON
权限: ALTER TABLE 权限 OK

=== 回滚信息 ===
备份 DDL: 已保存原始表 DDL
回滚命令: ALTER TABLE SCHEMA.ORDERS DROP COLUMN remark;

=== 执行结果 ===
状态: SUCCESS
耗时: 0.3 秒

=== 验证 ===
DESC SCHEMA.ORDERS: remark 列已添加，类型 VARCHAR2(500)
表状态: VALID
```

### DML 执行示例（分批 UPDATE）

```
=== SQL 解析 ===
SQL 类型: DML (UPDATE)
操作对象: SCHEMA.USERS
操作内容: UPDATE status = 'ARCHIVED' WHERE last_login < DATE '2025-01-01'

=== 前置检查 ===
实例: 192.168.1.100:1521/orcl
受影响行数预估: 125,000 行
分批设置: 每批 5000 行，预计 25 批
活跃事务: 3

=== 回滚信息 ===
备份表: SCHEMA.USERS_UPD_BAK_20260817_143000（已保存受影响行原始数据）
回滚方案: 从备份表恢复原始数据

=== 执行结果 ===
状态: SUCCESS (auto_rollback=true，已回滚验证)
批次 1/25: 5000 行 (0.8s)
批次 2/25: 5000 行 (0.7s)
...
批次 25/25: 5000 行 (0.7s)
总耗时: 18.5 秒
总行数: 125,000

=== 验证 ===
SELECT COUNT(*) FROM SCHEMA.USERS WHERE status='ARCHIVED': 0 (已回滚)
备份表数据: 125,000 行（可用于正式执行后的恢复）

=== 提示 ===
auto_rollback=true 模式下数据已回滚，确认无误后请设置 auto_rollback=false 重新执行以提交变更。
```

### Dry Run 示例

```
=== Dry Run 报告 ===
SQL 类型: DDL (CREATE INDEX)
操作对象: SCHEMA.ORDERS
操作内容: CREATE INDEX idx_orders_status ON ORDERS(status)

--- 前置检查 ---
表存在: YES
表大小: 2.5 GB (8,500,000 行)
索引列选择性: status 列有 5 个唯一值，选择性 0.00006%（极低）
表空间余量: USERS 表空间剩余 120 GB

--- 影响评估 ---
预估耗时: 约 45 秒（在线创建索引）
锁级别: 表级共享锁（允许 DML，阻塞 DDL）
风险等级: 低

--- 回滚方案 ---
DROP INDEX SCHEMA.idx_orders_status;

--- 建议 ---
1. 索引列选择性极低（5 个唯一值 / 850 万行），B-Tree 索引可能无效，建议使用位图索引（OLAP 场景）或评估是否需要此索引
2. 建议在业务低峰期执行
3. 可添加 ONLINE 关键字减少锁影响：CREATE INDEX ... ONLINE
```

## 安全边界
- 安全等级为 modify（可控轻量变更），执行 DDL/DML 操作。
- 不执行 DCL（GRANT/REVOKE/ALTER USER），不修改系统/会话参数。
- 不执行 DROP TABLESPACE / DROP DATABASE / ALTER SYSTEM 等破坏性操作。
- TRUNCATE TABLE 不可回滚，需二次确认后执行。
- DDL 自动提交（Oracle 特性），无法通过 SAVEPOINT 回滚，仅支持反向 DDL 回退。
- DELETE 操作前自动备份受影响数据到备份表。

## 功能限制
- 不执行 DCL 操作（GRANT/REVOKE/ALTER USER）
- 不修改系统参数（ALTER SYSTEM/SESSION）
- 不执行 DROP TABLESPACE / DROP DATABASE
- 不执行 DDL 的同时修改数据（如 CTAS 带数据）
- 不调用其他 Skill
- 大批量 DML 建议使用 commit_batch_size 分批提交，避免 undo 耗尽

## 版本记录
- v1.0.0（2026-08-17）：新建。按出厂标准化落地，单一职责「Oracle 普通 DDL/DML 执行（带自动回滚）」（modify/db-modify），覆盖 DDL（CREATE TABLE/ALTER TABLE/DROP TABLE/CREATE INDEX/DROP INDEX/TRUNCATE）与 DML（INSERT/UPDATE/DELETE/MERGE），DML 通过 SAVEPOINT 自动回滚，DDL 通过反向 DDL 回退，支持 dry_run 试运行与分批提交。