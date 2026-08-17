# Oracle SQL 审核（规范性 + 性能 + 安全）说明文档

## 能力简介
本技能对给定 SQL 进行三维度（规范性 / 性能 / 安全）综合审核，产出结构化审核报告，包含问题清单、风险等级、优化建议与改写示例（仅建议，不执行任何变更）。

## 适用场景
- 开发提交 SQL 前的合规审查与自检
- 应用上线前的 SQL 安全评审与性能把关
- 性能敏感 SQL 的分析与优化方向建议
- 定期 SQL 巡检（月度/季度代码审查）
- CI/CD 流水线中 SQL 门禁检查
- 新员工 SQL 编写规范培训参考

## 触发话术
- "帮我审核这条 SQL，看看有没有规范、性能和安全问题"
- "审查一下这条 Oracle SQL 的规范性"
- "这条 SQL 性能怎么样，有没有优化空间"
- "检查一下这个 SQL 有没有注入风险"
- "帮我做一次 SQL 安全审计"
- "上线前全面审查一下这些 SQL"
- "这个 PL/SQL 块有没有安全问题"
- "帮我审核这条 SQL，从规范性、性能、安全三个维度分析"

## 入参说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| instance_host | string | 否 | | 目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名），提供后可获取表/索引等上下文做更精准的审核 |
| sql_text | string | 是 | | 待审核的 SQL 语句（支持单条 SQL 或 PL/SQL 块） |
| audit_scope | string | 否 | all | 审核范围：all（全部）/ standard（仅规范性）/ performance（仅性能）/ security（仅安全） |
| business_context | string | 否 | | 业务上下文提示，如：OLTP 高并发写入 / OLAP 报表查询 / 定时批处理 / 数据迁移，用于调整审核严格度 |
| table_ddl | string | 否 | | 涉及表的 DDL 语句（可选，提供后可做字段类型匹配、索引可用性等更精准的审核） |

## 输出示例

```
=== Oracle SQL 审核报告 ===
SQL 类型: SELECT
审核范围: all
审核时间: 2026-08-17 12:00:00

--- 综合风险评分: 62 / 100（越高越安全）---

=== 一、规范性审核 ===
[高] DELETE 语句无 WHERE 条件 → 全表删除风险
[中] SELECT * 返回冗余列 → 建议显式列出所需列
[中] WHERE 隐式类型转换：user_id 与数字比较 → 索引失效
[低] 列别名 a, b 无业务含义 → 建议使用有意义的别名

=== 二、性能审核 ===
[高] 大表 orders(1000万行) 全表扫描风险 → WHERE 条件列 order_status 无索引
[中] OR 条件连接不同列 → 建议改为 UNION ALL
[中] NOT IN 子查询 → 建议改为 NOT EXISTS
[中] 硬编码值 → 硬解析风险，建议使用绑定变量

=== 三、安全审核 ===
[高] EXECUTE IMMEDIATE 拼接用户输入 → 表名注入风险
[中] SELECT 中包含 password 字段 → 敏感数据暴露
[中] 调用了 UTL_FILE.FOPEN → 文件路径需白名单校验

=== 四、改写示例（建议，不执行） ===
-- 原 SQL：
SELECT * FROM orders
WHERE (user_id = 1001 OR product_id = 5002)
  AND order_id NOT IN (SELECT order_id FROM cancelled_orders)
ORDER BY create_time DESC;

-- 改写后：
SELECT order_id, user_id, product_id, amount, create_time
FROM orders
WHERE order_id NOT IN (SELECT order_id FROM cancelled_orders)
  AND user_id = 1001
UNION ALL
SELECT order_id, user_id, product_id, amount, create_time
FROM orders
WHERE order_id NOT IN (SELECT order_id FROM cancelled_orders)
  AND product_id = 5002
  AND user_id <> 1001
ORDER BY create_time DESC;
```

## 审核维度详情

### 规范性审核（10+ 规则）
- 命名规范（表名、列别名、约束名）
- SELECT * 检测
- 隐式类型转换检测
- 列上函数/运算检测
- 缺失 WHERE 条件（DELETE/UPDATE 高危）
- 字段类型选型评审
- 字符集一致性
- 注释规范

### 性能审核（12+ 规则）
- 全表扫描风险识别
- 索引使用分析（缺失/冗余/低选择性）
- 大偏移分页检测
- OR 条件滥用检测
- NOT IN 子查询风险
- JOIN 条件与驱动表审查
- 排序与 GROUP BY 优化
- 绑定变量检测
- 统计信息新鲜度

### 安全审核（10+ 规则）
- SQL 注入检测（动态拼接/EXECUTE IMMEDIATE/DBMS_SQL）
- 敏感数据暴露检测
- 批量操作无事务保护
- 密码明文存储
- 高危系统包调用（UTL_FILE / UTL_HTTP / UTL_SMTP 等）
- 权限操作审计（GRANT / ALTER USER）
- UNION 注入风险

## 风险等级

| 等级 | 标识 | 说明 |
|------|------|------|
| 高 | 🔴 | 可能导致数据丢失、安全漏洞、严重性能问题 |
| 中 | 🟡 | 可能导致性能下降、维护困难、潜在风险 |
| 低 | 🟢 | 规范性问题，不影响功能但影响可维护性 |

## 安全边界
- 安全等级为 query（只读安全），仅做分析与建议
- 不执行任何 DDL/DML/DCL
- 不修改 SQL 文本、不创建/删除索引、不调整参数
- 不收集统计信息（DBMS_STATS）、不执行 SQL Profile/SPM 操作

## 功能限制
- 性能深层诊断（执行计划解读、AWR 分析）请用对应诊断类技能
- 索引设计建议请用对应索引设计类技能
- 不调用其它 Skill、不自动修复、仅按需手动触发

## 版本记录
- v1.0.0（2026-08-17）：新建。Oracle SQL 审核技能，纯文本分析（query / db-query），覆盖规范性审核（命名规范、SELECT *、隐式类型转换、列上函数、缺失 WHERE、字段类型）、性能审核（全表扫描、索引分析、分页、OR 优化、NOT IN 改写、JOIN 审查、排序优化、绑定变量、统计信息）、安全审核（SQL 注入、敏感数据暴露、批量操作事务、高危系统包、权限操作、UNION 注入）三维度，产出结构化审核报告与优化建议。