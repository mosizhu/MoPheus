# db-postgres-inspect

PostgreSQL 基础巡检与健康检查技能（只读）。

## 功能概述

对 PostgreSQL 实例执行 12 维度健康指标采集，对照统一阈值表分级评估，输出结构化巡检报告。

## 12 巡检维度

1. 连接使用率
2. 缓冲命中率
3. 锁等待数
4. 长事务数
5. 空闲事务数
6. 死锁次数
7. 复制延迟
8. 慢查询 TOP N
9. 死元组比例
10. 检查点健康度
11. WAL 归档状态
12. 磁盘使用

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instance_host | string | 是 | - | PostgreSQL 实例地址（host:port） |
| db_name | string | 否 | 空 | 目标数据库名（不填则巡检所有数据库） |
| report_format | string | 否 | markdown | 报告格式：markdown/html |
| top_n | integer | 否 | 10 | 各维度 TOP N 条数 |

## 安全级别

`query` - 仅执行只读查询，不修改任何数据或配置。

## 关联技能

- `db-postgres-diagnose-perf` - 综合性能诊断
- `db-postgres-diagnose-deadlock` - 死锁诊断分析
- `db-postgres-diagnose-slow-query` - 慢查询日志深度分析