---
name: "db-oracle-audit-sql"
description: "Oracle SQL 审核技能（规范性 + 性能 + 安全三维一体）。核心能力：(1) 规范性审核：命名规范、SELECT * 检查、隐式类型转换、列上函数、缺失 WHERE/DELETE 无 WHERE、字段类型选型、字符集一致性、注释规范；(2) 性能审核：全表扫描风险、索引使用分析、大偏移分页、OR 滥用、NOT IN 子查询、JOIN 条件与驱动表、排序/GROUP BY 优化、绑定变量检测、统计信息新鲜度；(3) 安全审核：SQL 注入风险（动态拼接/DBMS_SQL/EXECUTE IMMEDIATE）、敏感数据暴露、批量操作无事务、密码明文存储、高危系统包调用（UTL_FILE/UTL_HTTP/UTL_SMTP/DBMS_LOB）检测。适用场景：开发提交 SQL 前的合规审查、应用上线前 SQL 安全评审、性能敏感 SQL 分析与优化建议、定期 SQL 巡检、CI/CD SQL 门禁检查。功能限制：本技能仅产出审核结论与优化建议，不连接数据库执行 DDL/DML、不修改 SQL 文本、不创建/删除索引、不调整参数；性能深层诊断（执行计划/统计信息）请用对应诊断类技能。"
version: "v1.0.0"
tags: db-query
params:
  - name: "instance_host"
    type: "string"
    required: false
    default: ""
    desc: "目标 Oracle 实例连接串（host:port/service_name 或 TNS 别名），可选，提供后可获取表/索引等上下文做更精准的审核"
  - name: "sql_text"
    type: "string"
    required: true
    default: ""
    desc: "待审核的 SQL 语句（支持单条 SQL 或 PL/SQL 块）"
  - name: "audit_scope"
    type: "string"
    required: false
    default: "all"
    desc: "审核范围：all（全部）/ standard（仅规范性）/ performance（仅性能）/ security（仅安全）"
  - name: "business_context"
    type: "string"
    required: false
    default: ""
    desc: "业务上下文提示，如：OLTP 高并发写入 / OLAP 报表查询 / 定时批处理 / 数据迁移，用于调整审核严格度"
  - name: "table_ddl"
    type: "string"
    required: false
    default: ""
    desc: "涉及表的 DDL 语句（可选，提供后可做字段类型匹配、索引可用性等更精准的审核）"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle SQL 审核：规范性 + 性能 + 安全

本技能对给定 SQL 进行三维度综合审核，产出结构化审核报告，包含问题清单、风险等级、优化建议（仅建议，不执行任何变更）。

---

## 核心能力

### 规范性审核
- 命名规范检查（表名、列别名、约束名、索引名）
- SELECT * 检测与列显式化建议
- 隐式类型转换检测（WHERE varchar_col = 123 等）
- 列上函数/运算检测（WHERE UPPER(name) = 'X'、WHERE col + 1 > 100）
- 缺失 WHERE 条件（DELETE/UPDATE 无 WHERE 是高风险）
- 字段类型选型评审（VARCHAR2 长度、NUMBER 精度、DATE vs TIMESTAMP）
- 字符集/排序规则一致性
- 注释规范（表/列 COMMENT 完整性）

### 性能审核
- 全表扫描风险识别（TABLE ACCESS FULL 预测）
- 索引使用分析（潜在索引缺失、冗余索引、低选择性索引）
- 大偏移分页检测（ROWNUM 分页陷阱）
- OR 条件滥用检测（OR 导致索引失效 → 建议 UNION ALL）
- NOT IN 子查询风险（NULL 值陷阱 + 性能差 → 建议 NOT EXISTS）
- JOIN 条件与驱动表审查（笛卡尔积检测、连接列类型匹配）
- 排序与 GROUP BY 优化（排序溢出风险、索引排序利用）
- 绑定变量检测（硬编码值导致硬解析过多）
- 统计信息相关检查（提示统计信息可能过期）

### 安全审核
- SQL 注入风险检测（动态字符串拼接、EXECUTE IMMEDIATE 拼接、DBMS_SQL 拼接）
- 敏感数据暴露（密码字段、身份证号、手机号等明文字段出现在 SELECT 中）
- 批量操作无事务保护（大量 DML 无 SAVEPOINT / 批量 COMMIT）
- 密码明文存储（INSERT/UPDATE 中密码字段赋明文值）
- 高危系统包调用检测（UTL_FILE / UTL_HTTP / UTL_SMTP / UTL_TCP / DBMS_LOB 等）
- 权限提升风险（GRANT / ALTER USER 等 DCL 语句审核）
- UNION 注入风险（UNION SELECT 配合动态拼接）

## 适用场景
- 开发提交 SQL 前的合规审查与自检
- 应用上线前的 SQL 安全评审与性能把关
- 性能敏感 SQL 的分析与优化方向建议
- 定期 SQL 巡检（月度/季度代码审查）
- CI/CD 流水线中 SQL 门禁检查
- 新员工 SQL 编写规范培训参考

## 功能限制 / 安全边界
- 不连接数据库执行任何 DDL/DML/DCL
- 不修改 SQL 文本、不创建/删除索引、不调整参数
- 不收集统计信息（DBMS_STATS）、不执行 SQL Profile/SPM 操作
- 性能深层诊断（执行计划解读、AWR 分析）请用对应诊断类技能
- 不调用其它 Skill、不自动修复、仅按需手动触发
- 仅产出审核结论与优化建议，单次执行耗时 ≤5s，无第三方依赖、无常驻逻辑

---

## 一、推理框架：Oracle SQL 三维审核链

```
输入 SQL 文本
    |
    v
[1] SQL 解析与预处理
    | 识别 SQL 类型（SELECT / INSERT / UPDATE / DELETE / MERGE / PL/SQL）
    | 提取涉及的表、列、JOIN、子查询、条件、函数
    v
[2] 规范性审核
    | 命名规范 → 表名/列别名/约束名
    | SELECT * → 列显式化建议
    | 隐式类型转换 → 索引失效预警
    | 列上函数 → 索引失效预警
    | 缺失 WHERE → DELETE/UPDATE 高危标记
    | 字段类型 → 精度/长度评审
    v
[3] 性能审核
    | 全表扫描 → 索引缺失预测
    | 索引使用 → 冗余/低选择性/缺失
    | 分页方式 → OFFSET/ROWNUM 陷阱
    | OR 条件 → UNION ALL 改写建议
    | NOT IN → NOT EXISTS 改写建议
    | JOIN 条件 → 笛卡尔积/类型匹配
    | 绑定变量 → 硬解析风险
    v
[4] 安全审核
    | SQL 注入 → 动态拼接检测
    | 敏感数据 → 明文暴露检测
    | 批量操作 → 事务保护检查
    | 高危包 → UTL_FILE/UTL_HTTP 等
    | 权限操作 → GRANT/ALTER USER
    v
[5] 综合审核报告
    | 三维度问题汇总（按风险等级排序）
    | 逐项优化建议 + 改写示例
    | 综合风险评分（0~100，越高越安全）
```

---

## 二、规范性审核（只读分析）

### 2.1 命名规范检查清单

| 检查项 | 规则 | 严重等级 |
|--------|------|---------|
| 表名 | 建议 T_ 或业务前缀，全大写或下划线分隔，禁止关键字 | 低 |
| 列别名 | 禁止使用无意义别名（a, b, c, t1, tmp），建议有业务含义 | 低 |
| 约束名 | 建议 PK_/UK_/FK_/CK_ 前缀命名 | 低 |
| 关键字大小写 | Oracle 关键字建议大写，对象名建议统一风格 | 低 |

```sql
-- 关键字清单（Oracle 保留字）
-- TABLE, SELECT, FROM, WHERE, JOIN, GROUP, ORDER, HAVING,
-- UNION, INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP,
-- INDEX, VIEW, SEQUENCE, SYNONYM, TRIGGER, PROCEDURE, FUNCTION,
-- PACKAGE, TYPE, USER, ROLE, GRANT, REVOKE, COMMIT, ROLLBACK,
-- SAVEPOINT, SET, NULL, DEFAULT, PRIMARY, FOREIGN, KEY, CHECK,
-- UNIQUE, CONSTRAINT, REFERENCES, CASCADE, VALUES, INTO, AS,
-- AND, OR, NOT, IN, EXISTS, BETWEEN, LIKE, IS, ANY, ALL, SOME,
-- DISTINCT, CASE, WHEN, THEN, ELSE, END, DECODE, NVL, NVL2,
-- COALESCE, NULLIF, TO_CHAR, TO_DATE, TO_NUMBER, TO_TIMESTAMP,
-- SUBSTR, INSTR, LENGTH, TRIM, UPPER, LOWER, REPLACE, TRANSLATE,
-- ROUND, TRUNC, MOD, ABS, SIGN, CEIL, FLOOR, POWER, SQRT,
-- SYSDATE, SYSTIMESTAMP, CURRENT_DATE, CURRENT_TIMESTAMP,
-- ROWNUM, ROWID, LEVEL, CONNECT_BY, START WITH, PRIOR,
-- PARTITION, SUBPARTITION, TABLESPACE, STORAGE, PCTFREE, PCTUSED
```

### 2.2 SELECT * 检测

```sql
-- 问题示例：SELECT *
SELECT * FROM orders WHERE order_id = 1001;

-- 风险：
-- 1. 返回冗余列，增加网络传输与内存开销
-- 2. 无法利用覆盖索引（INDEX FAST FULL SCAN 不如 INDEX RANGE SCAN）
-- 3. 表结构变更（加列）可能导致应用层解析异常
-- 4. 违反 SQL 编码规范

-- 建议改写：显式列出所需列
SELECT order_id, user_id, amount, status, create_time
FROM orders
WHERE order_id = 1001;
```

### 2.3 隐式类型转换检测

| 问题模式 | 示例 | 风险 | 建议 |
|----------|------|------|------|
| 字符串列与数字比较 | `WHERE varchar_col = 123` | TO_NUMBER(varchar_col) 导致索引失效 | 使用字符串常量 `WHERE varchar_col = '123'` |
| 数字列与字符串比较 | `WHERE number_col = '123'` | Oracle 自动转换，通常无问题 | 保持类型一致更规范 |
| 日期列与字符串比较 | `WHERE date_col = '2024-01-01'` | 依赖 NLS 设置，可能转换失败 | 使用 TO_DATE 显式转换 |
| 日期列隐式转换 | `WHERE TRUNC(date_col) = DATE '2024-01-01'` | 列上函数导致索引失效 | 使用范围查询 |

```sql
-- 隐式转换检测模式（正则）
-- 数字列名 + 字符串常量：WHERE int_col = '123'
-- 字符串列名 + 数字常量：WHERE varchar_col = 123
-- 日期列名 + 字符串常量（无 TO_DATE）：WHERE date_col = '2024-01-01'

-- 建议改写示例
-- 原：WHERE order_status = 1         -- order_status 是 VARCHAR2
-- 改：WHERE order_status = '1'
-- 原：WHERE create_time = '2024-01-01'  -- create_time 是 DATE
-- 改：WHERE create_time >= TO_DATE('2024-01-01', 'YYYY-MM-DD')
--       AND create_time < TO_DATE('2024-01-02', 'YYYY-MM-DD')
```

### 2.4 列上函数/运算检测

| 问题模式 | 示例 | 改写建议 |
|----------|------|---------|
| 列上函数 | `WHERE UPPER(name) = 'ABC'` | → 确保数据存入时已统一大小写，或建函数索引 |
| 列上运算 | `WHERE amount * 1.1 > 1000` | → `WHERE amount > 1000 / 1.1`（运算移到常量侧） |
| 日期截断 | `WHERE TRUNC(create_time) = :dt` | → `WHERE create_time >= :dt AND create_time < :dt + 1` |
| 字符拼接 | `WHERE col1 \|\| col2 = 'AB'` | → 分别比较 `WHERE col1 = 'A' AND col2 = 'B'` |
| NVL/WRAP | `WHERE NVL(col, 0) = 100` | → `WHERE col = 100`（col 为 NULL 时不会等于 100） |

### 2.5 缺失 WHERE 条件

```sql
-- 高风险：DELETE/UPDATE 无 WHERE 条件
DELETE FROM orders;                        -- 🔴 高危：全表删除
UPDATE orders SET status = 'CLOSED';       -- 🔴 高危：全表更新

-- 中风险：SELECT 无 WHERE + 大表
SELECT * FROM order_items;                 -- 🟡 中危：大表全量查询

-- 建议：
-- 1. DELETE/UPDATE 必须带 WHERE 条件（除非明确要全表操作）
-- 2. 大表 SELECT 必须带 WHERE + ROWNUM/FETCH FIRST 限制
-- 3. 使用 MERGE 替代 UPDATE + INSERT 组合
```

### 2.6 字段类型选型评审

| 字段类型 | 问题 | 建议 |
|----------|------|------|
| VARCHAR2(4000) 存短字符串 | 浪费空间 | 根据实际长度设置，如 VARCHAR2(50) |
| NUMBER 无精度 | 数值精度不可控 | 使用 NUMBER(p, s) 明确精度 |
| FLOAT / BINARY_FLOAT 存金额 | 浮点精度丢失 | 金额用 NUMBER(18, 2) 或 NUMBER(18, 4) |
| DATE 存毫秒 | 精度丢失 | 使用 TIMESTAMP(3) |
| CLOB 存短文本 | 性能开销大 | < 4000 字节用 VARCHAR2(4000) |
| CHAR 存变长字符串 | 空格填充浪费 | 使用 VARCHAR2 |

---

## 三、性能审核（只读分析）

### 3.1 全表扫描风险识别

```sql
-- 全表扫描高风险模式检测
-- 1. 查询条件列无索引 → 预测全表扫描
-- 2. WHERE 中使用 != / <> / NOT IN → 索引失效
-- 3. WHERE 中使用 IS NULL / IS NOT NULL → B-Tree 索引可能失效
-- 4. LIKE '%xxx' 前导模糊 → 索引失效
-- 5. WHERE 条件使用 OR 连接不同列 → 索引失效

-- 检查清单
-- ① WHERE 条件列是否在索引中？
-- ② 是否使用了前导 % 模糊匹配？
-- ③ 是否使用了不等于操作符？
-- ④ 是否对索引列使用了函数或运算？
-- ⑤ 复合索引是否满足最左前缀原则？
```

### 3.2 索引使用分析

```sql
-- 潜在缺失索引检测
-- 规则：WHERE / JOIN / ORDER BY / GROUP BY 中出现的列，检查是否已有索引

-- 低选择性索引警告
-- 规则：性别、状态（< 5 个值）、布尔标志等列单独建索引 → 选择性低，通常无效
-- 建议：低选择性列放在复合索引末尾，或使用位图索引（OLAP 场景）

-- 冗余索引检测
-- 规则：已有 (A, B, C) 复合索引，再建 (A) 或 (A, B) 索引 → 冗余
-- 例外：如果 (A) 是唯一约束的主键，保留

-- 索引列顺序建议
-- 规则：等值条件列在前 → 范围条件列在后 → 排序/分组列在最后
-- 示例：WHERE status = 'ACTIVE' AND create_time > :dt ORDER BY user_id
--   → 建议索引：(status, create_time, user_id)
```

### 3.3 大偏移分页检测

```sql
-- 问题模式：ROWNUM 分页
SELECT *
FROM (
    SELECT a.*, ROWNUM rn
    FROM (
        SELECT * FROM orders ORDER BY order_id
    ) a
    WHERE ROWNUM <= 100010
)
WHERE rn >= 100001;

-- 风险：需要扫描并丢弃前 100000 行，偏移越大越慢
-- 建议：使用延迟关联（先取主键再回表）或 keyset 分页（记录上次位置）

-- 改写建议（Oracle 12c+）
SELECT order_id, user_id, amount, create_time
FROM orders
WHERE order_id > :last_order_id   -- 上次分页的最后一条 ID
ORDER BY order_id
FETCH FIRST 10 ROWS ONLY;

-- 改写建议（Oracle 12c+ 标准分页）
SELECT order_id, user_id, amount, create_time
FROM orders
ORDER BY order_id
OFFSET 100000 ROWS FETCH NEXT 10 ROWS ONLY;
-- 注意：OFFSET 方式仍会扫描前 100000 行，大偏移量仍建议 keyset 方式
```

### 3.4 OR 条件滥用检测

```sql
-- 问题模式：OR 连接不同列
SELECT * FROM t WHERE a = 1 OR b = 2;

-- 风险：优化器通常无法合并两个不同列的索引，导致全表扫描或 INDEX FULL SCAN
-- 建议：改为 UNION ALL（前提是两结果集不重复）

-- 改写：
SELECT * FROM t WHERE a = 1
UNION ALL
SELECT * FROM t WHERE b = 2 AND a <> 1;

-- 注：如果 a 和 b 在同一复合索引中，OR 可转为 IN 或范围查询
SELECT * FROM t WHERE (a, b) IN ((1, 1), (1, 2), (1, 3));
```

### 3.5 NOT IN 子查询风险

```sql
-- 问题模式：NOT IN + 子查询
SELECT * FROM orders
WHERE user_id NOT IN (SELECT user_id FROM blacklist);

-- 风险：
-- 1. 子查询返回 NULL 时，整个 NOT IN 返回空（NULL 陷阱）
-- 2. 大集合 NOT IN 性能差，NOT IN 对每一行都要扫描子查询结果

-- 建议：改写为 NOT EXISTS
SELECT * FROM orders o
WHERE NOT EXISTS (
    SELECT 1 FROM blacklist b WHERE b.user_id = o.user_id
);

-- 或改写为 LEFT JOIN + IS NULL（视情况）
SELECT o.* FROM orders o
LEFT JOIN blacklist b ON o.user_id = b.user_id
WHERE b.user_id IS NULL;
```

### 3.6 JOIN 条件与驱动表审查

```sql
-- JOIN 审核检查清单
-- ① 是否存在笛卡尔积（CROSS JOIN / 无 ON 条件的逗号连接）？
-- ② JOIN 列数据类型是否一致（隐式转换导致索引失效）？
-- ③ JOIN 列字符集是否一致？
-- ④ 外连接方向是否合理？
-- ⑤ 驱动表选择是否合理（小表驱动大表）？

-- 笛卡尔积检测
SELECT * FROM orders o, users u;  -- 缺少 o.user_id = u.id → 笛卡尔积

-- 连接列类型不一致
SELECT * FROM orders o
JOIN users u ON o.user_id = u.id;  -- 如果 user_id 是 VARCHAR2, id 是 NUMBER
-- → 隐式转换 TO_NUMBER(o.user_id) 导致 orders 表索引失效

-- 外连接合理性
SELECT * FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE u.status = 'ACTIVE';  -- 对右表过滤 → LEFT JOIN 退化为 INNER JOIN
-- 建议：将右表过滤条件移到 ON 子句中
```

### 3.7 排序与 GROUP BY 优化

```sql
-- 排序审核
-- ① ORDER BY 列是否在索引中？（可利用索引排序避免文件排序）
-- ② 是否排序大量数据且无 LIMIT？（内存排序溢出风险）
-- ③ DISTINCT + ORDER BY 是否可优化？

-- GROUP BY 审核
-- ① GROUP BY 列是否在索引中？
-- ② HAVING 过滤是否能提前到 WHERE 中？
-- ③ 聚合列是否合理（避免 COUNT(列) 替代 COUNT(*) 除非必要）？

-- 示例：HAVING 提前到 WHERE
-- 原：
SELECT dept_id, COUNT(*) FROM employees
GROUP BY dept_id
HAVING dept_id > 10;
-- 改：
SELECT dept_id, COUNT(*) FROM employees
WHERE dept_id > 10
GROUP BY dept_id;
```

### 3.8 绑定变量检测

```sql
-- 硬编码值检测（可能导致硬解析过多）
-- 问题模式：SQL 中直接嵌入常量值，而非使用绑定变量
SELECT * FROM orders WHERE user_id = 1001;
SELECT * FROM orders WHERE user_id = 1002;  -- 视为不同 SQL，各需硬解析一次

-- 在 PL/SQL 中应使用绑定变量
-- 原：
EXECUTE IMMEDIATE 'SELECT * FROM orders WHERE user_id = ' || v_user_id;
-- 改：
EXECUTE IMMEDIATE 'SELECT * FROM orders WHERE user_id = :1' USING v_user_id;

-- 审核规则：
-- ① 多个结构相同但值不同的 SQL → 硬解析风险
-- ② EXECUTE IMMEDIATE 中拼接变量值 → 绑定变量改写建议
-- ③ 批次循环中的单条执行 → 建议 FORALL + BULK COLLECT
```

### 3.9 统计信息相关检查

```sql
-- 统计信息过期风险提示
-- 如果提供 instance_host 参数，可查询统计信息新鲜度
SELECT owner, table_name, num_rows, last_analyzed,
       ROUND(SYSDATE - last_analyzed) AS days_stale
FROM dba_tab_statistics
WHERE owner NOT IN ('SYS', 'SYSTEM', 'DBSNMP')
  AND stale_stats = 'YES'
ORDER BY days_stale DESC;

-- 审核提示：
-- ① 涉及的表 last_analyzed > 7 天 → 统计信息可能过期
-- ② 表数据变更 > 10% → 建议收集统计信息
-- ③ 提示中标记"统计信息可能过期，建议收集后重新评估执行计划"
```

---

## 四、安全审核（只读分析）

### 4.1 SQL 注入风险检测

```sql
-- SQL 注入高风险模式检测
-- ① 动态字符串拼接（|| 操作符拼接变量）
-- ② EXECUTE IMMEDIATE 拼接用户输入
-- ③ DBMS_SQL.PARSE 拼接用户输入
-- ④ 应用层字符串模板注入（PL/SQL 中 & 替代变量）

-- 检测模式 1：字符串拼接
v_sql := 'SELECT * FROM users WHERE name = ''' || p_name || '''';
-- 🔴 高危：p_name 为 "x' OR '1'='1" 时导致注入
-- 建议：使用绑定变量
v_sql := 'SELECT * FROM users WHERE name = :1';
EXECUTE IMMEDIATE v_sql USING p_name;

-- 检测模式 2：EXECUTE IMMEDIATE 拼接
EXECUTE IMMEDIATE 'DELETE FROM ' || p_table || ' WHERE id = ' || p_id;
-- 🔴 高危：p_table 可控导致任意表删除
-- 建议：
-- 1. 表名使用白名单校验
-- 2. 使用 DBMS_ASSERT.SQL_OBJECT_NAME 校验
-- 3. id 使用绑定变量

-- 检测模式 3：DBMS_SQL 拼接
DBMS_SQL.PARSE(cur, 'SELECT * FROM ' || p_table, DBMS_SQL.NATIVE);
-- 🔴 高危：同上

-- 检测模式 4：替代变量（SQL*Plus / SQLcl）
SELECT * FROM orders WHERE user_id = &user_id;
-- 🟡 中危：交互式环境中的替代变量
-- 建议：应用代码中禁止使用 & 替代变量

-- 安全改写模板
-- 原（高危）：
v_sql := 'SELECT * FROM ' || p_table || ' WHERE ' || p_col || ' = ''' || p_val || '''';
EXECUTE IMMEDIATE v_sql;

-- 改（安全）：
v_sql := 'SELECT * FROM ' || DBMS_ASSERT.SQL_OBJECT_NAME(p_table)
      || ' WHERE ' || DBMS_ASSERT.SIMPLE_SQL_NAME(p_col) || ' = :1';
EXECUTE IMMEDIATE v_sql USING p_val;
```

### 4.2 敏感数据暴露检测

```sql
-- 敏感列检测清单
-- ① 密码字段：password, passwd, pwd, secret, credential
-- ② 身份证号：id_card, identity_card, idcard, ssn
-- ③ 手机号：phone, mobile, tel, telephone
-- ④ 银行卡号：bank_card, card_no, credit_card
-- ⑤ 邮箱：email, mail
-- ⑥ 地址：address, addr, location
-- ⑦ 真实姓名：real_name, full_name（与昵称区分）

-- 审核规则：
-- ① SELECT 中直接出现敏感列 → 🟡 中危：建议脱敏（SUBSTR / MASK / '*' 替换）
-- ② INSERT/UPDATE 中密码字段赋明文值 → 🔴 高危：建议使用哈希存储
-- ③ 日志中打印敏感字段 → 🟡 中危：建议脱敏后输出

-- 脱敏示例
-- 原：
SELECT user_id, password, phone FROM users;
-- 改：
SELECT user_id,
       '***' AS password,                        -- 密码脱敏
       SUBSTR(phone, 1, 3) || '****' || SUBSTR(phone, -4) AS phone  -- 手机号脱敏
FROM users;
```

### 4.3 批量操作无事务保护

```sql
-- 批量 DML 无事务保护检测
-- ① 大量 DELETE/UPDATE 无 WHERE 限制 → 🔴 高危
-- ② 循环中逐条 COMMIT 或完全不 COMMIT → 🟡 中危
-- ③ 批量操作无 SAVEPOINT → 🟡 中危

-- 审核规则：
-- ① 批量操作建议分批 COMMIT（如每 5000 行 COMMIT 一次）
-- ② 大批量操作前设置 SAVEPOINT
-- ③ 异常处理中 ROLLBACK 到 SAVEPOINT

-- 建议范式
BEGIN
    SAVEPOINT batch_start;
    FOR rec IN (SELECT rowid FROM large_table WHERE condition) LOOP
        DELETE FROM large_table WHERE rowid = rec.rowid;
        v_count := v_count + 1;
        IF MOD(v_count, 5000) = 0 THEN
            COMMIT;
            SAVEPOINT batch_start;
        END IF;
    END LOOP;
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK TO batch_start;
        RAISE;
END;
```

### 4.4 高危系统包调用检测

```sql
-- 高危系统包检测清单
-- ① UTL_FILE  → 文件读写（可能读取敏感文件或写入恶意脚本）
-- ② UTL_HTTP  → HTTP 请求（可能 SSRF 攻击）
-- ③ UTL_SMTP  → 邮件发送（可能发送垃圾邮件或泄露数据）
-- ④ UTL_TCP   → TCP 连接（可能建立后门通道）
-- ⑤ UTL_MAIL  → 邮件发送（同上）
-- ⑥ DBMS_LOB  → 大对象操作（可能被用于读取文件）
-- ⑦ DBMS_SCHEDULER → 任务调度（可能创建恶意定时任务）
-- ⑧ DBMS_ADVISOR → 可能被用于提权

-- 审核规则：
-- ① 调用 UTL_FILE.FOPEN  → 🟡 中危：检查文件路径是否可控
-- ② 调用 UTL_HTTP.REQUEST → 🟡 中危：检查 URL 是否可控
-- ③ 调用 UTL_SMTP / UTL_MAIL → 🟡 中危：检查收件人和内容是否可控
-- ④ 调用 UTL_TCP.OPEN_CONNECTION → 🔴 高危：检查 IP/端口是否可控
-- ⑤ 调用 DBMS_LOB.LOADFROMFILE → 🟡 中危：检查文件路径是否可控

-- 安全建议：
-- ① 文件路径使用白名单校验
-- ② URL 使用白名单校验（禁止内网地址）
-- ③ 邮件内容禁止包含用户输入
-- ④ 对高危包调用添加审计日志
```

### 4.5 权限操作检测

```sql
-- 权限相关 DCL 语句检测
-- ① GRANT DBA / ALL PRIVILEGES TO → 🔴 高危
-- ② GRANT SELECT ANY TABLE TO → 🔴 高危
-- ③ ALTER USER xxx IDENTIFIED BY → 🟡 中危（可能是密码修改）
-- ④ CREATE USER xxx IDENTIFIED BY → 🟡 中危（可能是创建后门账户）
-- ⑤ REVOKE ... FROM → 🟡 中危（可能是权限破坏）

-- 审核规则：
-- ① GRANT ALL PRIVILEGES / DBA → 标记高风险，建议细化权限
-- ② SELECT ANY TABLE / EXECUTE ANY PROCEDURE → 标记高风险
-- ③ 动态 GRANT/REVOKE → 标记中风险，检查是否可被用户控制
```

### 4.6 UNION 注入风险

```sql
-- UNION 注入风险检测
-- ① 动态拼接 SQL + UNION SELECT → 🔴 高危
-- ② 动态拼接 SQL 结尾 + 用户输入 → 可能被追加 UNION SELECT

-- 示例：高危模式
v_sql := 'SELECT name, age FROM users WHERE id = ' || p_id;
-- 攻击者输入 p_id = "1 UNION SELECT password, NULL FROM admin_users"
-- 结果返回密码

-- 建议：
-- 1. 使用绑定变量（根本解决）
-- 2. 对输入做类型校验（数字列只接受数字）
-- 3. 使用白名单校验列名和表名
```

---

## 五、审核报告输出格式

```markdown
=== Oracle SQL 审核报告 ===
SQL 类型: SELECT / INSERT / UPDATE / DELETE / MERGE / PL/SQL
审核范围: all / standard / performance / security
业务场景: OLTP 高并发写入 / OLAP 报表查询 / 定时批处理
审核时间: 2026-08-17 12:00:00

--- 综合风险评分: 62 / 100（越高越安全）---

=== 一、规范性审核 ===
[高] 共 1 项
  [高-1] DELETE 语句无 WHERE 条件 → 全表删除风险，建议添加 WHERE 条件
[中] 共 2 项
  [中-1] SELECT * 返回冗余列，表有 25 列，实际使用 4 列 → 建议显式列出所需列
  [中-2] WHERE 子句隐式类型转换：varchar_col user_id 与数字 1001 比较 → 索引失效
[低] 共 1 项
  [低-1] 列别名 t1 无业务含义 → 建议使用有意义的别名

=== 二、性能审核 ===
[高] 共 1 项
  [高-1] 大表 orders(1000万行) 全表扫描风险 → WHERE 条件列 order_status 无索引
[中] 共 3 项
  [中-1] OR 条件连接不同列 → 建议改为 UNION ALL
  [中-2] NOT IN 子查询（blacklist 表）→ 建议改为 NOT EXISTS
  [中-3] 硬编码值 user_id=1001 → 硬解析风险，建议使用绑定变量
[低] 共 1 项
  [低-1] 复合索引 idx_a_b_c 已包含 idx_a_b → 建议删除冗余索引 idx_a_b

=== 三、安全审核 ===
[高] 共 1 项
  [高-1] EXECUTE IMMEDIATE 拼接用户输入 p_table → 表名注入风险，建议使用 DBMS_ASSERT
[中] 共 2 项
  [中-1] SELECT 中包含 password 字段 → 敏感数据暴露，建议脱敏处理
  [中-2] 调用了 UTL_FILE.FOPEN → 文件路径需白名单校验
[低] 共 0 项

=== 四、优化建议汇总 ===
规范性：
  1. DELETE 添加 WHERE 条件
  2. SELECT * 改为显式列名
  3. 统一 user_id 比较类型为字符串
性能：
  4. 为 orders.order_status 创建索引
  5. OR 条件改为 UNION ALL
  6. NOT IN 改为 NOT EXISTS
  7. 使用绑定变量替代硬编码
安全：
  8. 使用 DBMS_ASSERT.SQL_OBJECT_NAME 校验 p_table
  9. password 字段脱敏输出
  10. UTL_FILE 路径添加白名单校验

=== 五、改写示例（建议，不执行） ===
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

---

## 六、风险等级判定标准

| 风险等级 | 标识 | 判定标准 | 示例 |
|----------|------|---------|------|
| 高 | 🔴 | 可能导致数据丢失、安全漏洞、严重性能问题 | DELETE 无 WHERE、SQL 注入拼接、全表扫描大表 |
| 中 | 🟡 | 可能导致性能下降、维护困难、潜在风险 | 隐式类型转换、OR 滥用、敏感数据暴露 |
| 低 | 🟢 | 规范性问题，不影响功能但影响可维护性 | 命名不规范、SELECT * 小表查询、注释缺失 |

## 七、业务场景审核策略

| 业务场景 | 策略调整 |
|----------|---------|
| OLTP 高并发写入 | 严格检查绑定变量、索引使用、锁风险；允许短事务频繁提交 |
| OLAP 报表查询 | 放宽全表扫描检查（大表分析可能不可避免）；关注并行度、PGA 排序 |
| 定时批处理 | 关注批量操作事务保护、分批 COMMIT；允许长事务 |
| 数据迁移 | 放宽规范检查；重点关注批量操作安全、回滚策略 |
| 接口 SQL | 严格检查 SQL 注入、敏感数据、绑定变量 |
| 管理脚本 | 严格检查 DDL/DCL 安全性、高危系统包调用 |

---

## 异常处理
- SQL 解析失败时返回明确的结构化错误提示，不暴露底层异常栈。
- 单条 SQL 审核耗时 ≤5s，批量审核建议逐条提交。
- 实例连接失败不影响纯文本审核，仅标记"无法获取表/索引上下文，审核结果可能不够精准"。
- 本技能仅做只读分析与建议，不执行任何 DDL/DML/DCL，无第三方依赖、无常驻逻辑。

## 输出格式
- 结构化输出：综合风险评分 + 三维度问题清单（按风险等级排序）+ 逐项优化建议 + 改写示例（仅建议）。