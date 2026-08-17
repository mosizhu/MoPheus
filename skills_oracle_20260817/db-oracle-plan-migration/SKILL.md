---
name: "db-oracle-plan-migration"
description: "Oracle 数据库迁移方案设计技能（源端 → 目标，只读方案）。核心能力：针对 Oracle 数据库跨环境/跨版本/跨平台迁移生成完整方案——迁移范围评估（对象清单、数据量、依赖关系）、迁移方式选型（Data Pump expdp/impdp、RMAN 备份恢复/可传输表空间、GoldenGate 实时同步、Data Guard 切换、XTTS 跨平台迁移）、前置检查与准备、分批策略、一致性校验、回滚与割接步骤。适用场景：Oracle 跨环境迁移（开发→测试→生产）、跨版本升级迁移（如 11g→19c）、跨平台迁移（如 AIX→Linux）、同城/异地灾备搭建、数据整合与迁移。功能限制：仅输出方案与步骤，不直接执行迁移操作（不执行 expdp/impdp/RMAN/OGG 等）、不修改源端/目标端结构、不删除源数据；迁移执行由 DBA 在维护窗口内完成。"
version: "v1.0.0"
tags: db-ops
params:
  - name: "src_instance"
    type: "string"
    required: true
    default: ""
    desc: "源端 Oracle 实例连接串（host:port/service_name）"
  - name: "dst_instance"
    type: "string"
    required: true
    default: ""
    desc: "目标端 Oracle 实例连接串（host:port/service_name）"
  - name: "migration_scope"
    type: "string"
    required: false
    default: "schema"
    desc: "迁移范围：full（全库）/ schema（指定 schema）/ tablespace（指定表空间）/ table（指定表）"
  - name: "schema_name"
    type: "string"
    required: false
    default: ""
    desc: "迁移的 schema 名称（migration_scope=schema 时必填，支持逗号分隔多个）"
  - name: "migration_mode"
    type: "string"
    required: false
    default: "offline"
    desc: "迁移模式：offline（离线停机迁移）/ online（在线最小停机迁移，如 OGG 实时同步）/ hybrid（混合模式，全量+增量）"
  - name: "src_version"
    type: "string"
    required: false
    default: ""
    desc: "源端 Oracle 版本号（如 11.2.0.4 / 19.3.0.0），为空则自动探测"
  - name: "dst_version"
    type: "string"
    required: false
    default: ""
    desc: "目标端 Oracle 版本号（如 19.3.0.0），为空则自动探测"
  - name: "src_platform"
    type: "string"
    required: false
    default: ""
    desc: "源端操作系统平台（如 Linux x86_64 / AIX / Solaris / Windows），为空则自动探测"
  - name: "dst_platform"
    type: "string"
    required: false
    default: ""
    desc: "目标端操作系统平台（如 Linux x86_64），为空则自动探测"
  - name: "parallel_degree"
    type: "integer"
    required: false
    default: 4
    desc: "迁移并行度（Data Pump / RMAN 并行通道数），默认 4"
  - name: "downtime_hours"
    type: "integer"
    required: false
    default: 4
    desc: "可接受停机窗口（小时），用于评估方案可行性，默认 4"
support_db: oracle
safe_level: "query"
author: "团队出厂预置"
update_time: "2026-08-17"
---

# Oracle 数据库迁移方案设计（源端 → 目标）

> 针对 Oracle 数据库跨环境/跨版本/跨平台迁移生成完整方案：迁移范围评估、迁移方式选型、前置检查、分批策略、一致性校验、回滚与割接步骤。本技能为 query 级方案，不直接执行。自包含。

## 核心能力
- 单一职责：Oracle 数据库迁移方案设计（评估 → 选型 → 方案 → 校验 → 回滚）。

## 适用场景
- Oracle 跨环境迁移（开发 → 测试 → 生产）
- 跨版本升级迁移（如 11g → 19c、12c → 19c）
- 跨平台迁移（如 AIX → Linux、Solaris → Linux）
- 同城/异地灾备搭建
- 数据整合与迁移（多源归一）
- 机房搬迁 / 存储替换场景下的数据库迁移

## 功能限制 / 安全边界
- 不直接执行迁移操作（不执行 expdp/impdp、RMAN 备份恢复、OGG 配置、Data Guard 切换等）
- 不修改源端/目标端结构（不执行 DDL，如表空间、用户、权限变更）
- 不删除源端数据（迁移完成并校验一致前，源端数据严禁清理）
- 仅输出方案与步骤，由 DBA 在维护窗口内、有全量备份前提下执行；单次生成耗时 ≤3s

---

## 一、推理框架：迁移方案设计链

```
用户提出 Oracle 迁移需求（源端 → 目标）
    |
    v
[1] 迁移范围评估（前置分析）
    | 源端环境信息采集（版本/平台/补丁）
    | 数据规模评估（总量/大对象/大表）
    | 对象清单统计（表/索引/视图/存储过程/包/序列/同义词/DBLink/物化视图/触发器/Job）
    | 无效对象与依赖关系检查
    | 特殊对象识别（加密表空间/TDE、分区表、LOB/SecureFile、XMLType、自定义类型）
    v
[2] 迁移方式选型
    | 场景匹配（同版本/跨版本/跨平台/在线/离线）
    | 方式对比（Data Pump / RMAN / 可传输表空间 / GoldenGate / Data Guard / XTTS）
    | 推荐方案 + 备选方案
    v
[3] 前置检查清单
    | 源端检查（归档模式、闪回、字符集、国家字符集、补丁级）
    | 目标端检查（存储空间、字符集兼容、版本兼容、补丁匹配）
    | 网络与存储（带宽、端口、防火墙）
    v
[4] 迁移步骤设计
    | 全量迁移（离线）或 全量+增量同步（在线）
    | 分批策略（按 schema / 表空间 / 大小分批）
    | 并行通道配置
    | 特殊对象迁移顺序
    v
[5] 一致性校验
    | 对象数量校验（表/索引/视图/存储过程计数）
    | 数据量校验（行数 / 数据大小）
    | 数据内容校验（CHECKSUM / 外键关联完整性）
    | 无效对象复检
    v
[6] 回滚与割接
    | 迁移前全量备份
    | 割接步骤（停写 → 终次同步 → 校验 → 切换）
    | 回滚方案（切回源端，保留源数据不删）
    | 业务验证清单
```

---

## 二、迁移范围评估（前置分析，只读 SQL）

### 2.1 源端环境信息采集

```sql
-- 数据库版本与平台
SELECT banner_full AS full_version,
       banner AS edition,
       BANNER_LEGACY
FROM v$version;

-- 数据库平台信息
SELECT platform_id,
       platform_name
FROM v$database;

-- 数据库名称与字符集
SELECT name AS db_name,
       created,
       log_mode,
       flashback_on,
       open_mode,
       cdb
FROM v$database;

-- 字符集信息
SELECT parameter, value
FROM nls_database_parameters
WHERE parameter IN (
    'NLS_CHARACTERSET',
    'NLS_NCHAR_CHARACTERSET',
    'NLS_LANGUAGE',
    'NLS_TERRITORY',
    'NLS_RDBMS_VERSION'
);
```

### 2.2 数据规模评估

```sql
-- 按 schema 统计数据量
SELECT owner,
       COUNT(*) AS "object_count",
       ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) AS "total_gb"
FROM dba_segments
WHERE owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'DBSNMP', 'APPQOSSYS', 'GSMADMIN_INTERNAL',
                     'ORACLE_OCM', 'OUTLN', 'WMSYS', 'OJVMSYS', 'CTXSYS', 'ORDDATA',
                     'ORDPLUGINS', 'SI_INFORMTN_SCHEMA', 'MDSYS', 'OLAPSYS', 'LBACSYS',
                     'DVSYS', 'AUDSYS')
GROUP BY owner
ORDER BY total_gb DESC;

-- 大对象识别（> 10GB 的表）
SELECT owner,
       segment_name,
       segment_type,
       ROUND(bytes / 1024 / 1024 / 1024, 2) AS size_gb
FROM dba_segments
WHERE owner NOT IN ('SYS', 'SYSTEM')
  AND segment_type = 'TABLE'
  AND bytes > 10 * 1024 * 1024 * 1024
ORDER BY size_gb DESC;

-- 大 LOB 段识别
SELECT owner,
       table_name,
       column_name,
       segment_name,
       ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) AS lob_size_gb
FROM dba_lobs l
JOIN dba_segments s ON l.segment_name = s.segment_name AND l.owner = s.owner
WHERE l.owner NOT IN ('SYS', 'SYSTEM')
GROUP BY owner, table_name, column_name, segment_name
HAVING SUM(bytes) > 5 * 1024 * 1024 * 1024
ORDER BY lob_size_gb DESC;
```

### 2.3 对象清单统计

```sql
-- 按对象类型统计数量
SELECT owner,
       object_type,
       COUNT(*) AS object_count
FROM dba_objects
WHERE owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'DBSNMP', 'PUBLIC', 'APPQOSSYS',
                     'GSMADMIN_INTERNAL', 'ORACLE_OCM', 'OUTLN')
  AND owner = NVL('&schema_name', owner)
  AND object_type NOT IN ('INDEX PARTITION', 'TABLE PARTITION', 'LOB PARTITION')
GROUP BY owner, object_type
ORDER BY owner, object_count DESC;

-- 无效对象检查
SELECT owner,
       object_type,
       object_name,
       status
FROM dba_objects
WHERE owner NOT IN ('SYS', 'SYSTEM', 'PUBLIC')
  AND status = 'INVALID'
  AND owner = NVL('&schema_name', owner)
ORDER BY owner, object_type, object_name;

-- 依赖关系检查（跨 schema 引用）
SELECT owner,
       name,
       type,
       referenced_owner,
       referenced_name,
       referenced_type
FROM dba_dependencies
WHERE owner = NVL('&schema_name', owner)
  AND referenced_owner NOT IN ('SYS', 'SYSTEM', 'PUBLIC')
  AND referenced_owner != owner
ORDER BY owner, referenced_owner, name;
```

### 2.4 特殊对象识别

```sql
-- TDE 加密表空间检查
SELECT ts.name AS tablespace_name,
       e.encryptionalg AS algorithm,
       e.encryptedts
FROM v$tablespace ts
JOIN v$encrypted_tablespaces e ON ts.ts# = e.ts#
WHERE e.encryptedts = 'YES';

-- 分区表统计
SELECT owner,
       COUNT(DISTINCT table_name) AS partitioned_table_count
FROM dba_tab_partitions
WHERE owner = NVL('&schema_name', owner)
  AND owner NOT IN ('SYS', 'SYSTEM')
GROUP BY owner;

-- 物化视图与刷新组
SELECT owner,
       mview_name,
       refresh_mode,
       refresh_method,
       fast_refreshable,
       last_refresh_type,
       staleness
FROM dba_mviews
WHERE owner = NVL('&schema_name', owner)
  AND owner NOT IN ('SYS', 'SYSTEM')
ORDER BY owner, mview_name;

-- DBLink 清单
SELECT owner,
       db_link,
       username,
       host,
       created
FROM dba_db_links
WHERE owner = NVL('&schema_name', owner)
   OR owner = 'PUBLIC'
ORDER BY owner, db_link;

-- 调度 Job 清单
SELECT owner,
       job_name,
       job_type,
       job_action,
       state,
       enabled,
       last_start_date,
       next_run_date
FROM dba_scheduler_jobs
WHERE owner = NVL('&schema_name', owner)
  AND owner NOT IN ('SYS', 'SYSTEM', 'ORACLE_OCM')
ORDER BY owner, enabled DESC, job_name;
```

---

## 三、迁移方式选型

| 迁移方式 | 适用场景 | 停机时间 | 复杂度 | 跨版本 | 跨平台 | 推荐度 |
|---------|---------|---------|--------|--------|--------|--------|
| **Data Pump (expdp/impdp)** | 中小规模（< 1TB），可接受停机 | 数小时 | 低 | 是 | 是 | ★★★★★ |
| **RMAN 备份恢复** | 同平台同版本，全库迁移 | 数小时 | 低 | 受限 | 否 | ★★★★☆ |
| **RMAN 可传输表空间** | 大表空间迁移，跨平台 | 较短 | 中 | 受限 | 是 | ★★★★☆ |
| **XTTS (跨平台可传输表空间)** | 跨平台大库迁移，增量备份 | 较短 | 中 | 受限 | 是 | ★★★★★ |
| **GoldenGate (OGG) 实时同步** | 零/微停机在线迁移，跨版本 | 分钟级 | 高 | 是 | 是 | ★★★★★ |
| **Data Guard 切换** | 同平台同版本灾备切换 | 分钟级 | 中 | 否 | 否 | ★★★★☆ |
| **RMAN 增量备份恢复** | 大库在线迁移（配合全量+增量） | 较短 | 中 | 受限 | 否 | ★★★★☆ |

### 选型决策树

```
                          ┌── 同版本? ──┐
                          │ 是          │ 否
                          v             v
                    ┌── 同平台? ──┐   Data Pump / OGG
                    │ 是          │ 否
                    v             v
              ┌── 在线? ──┐   XTTS / Data Pump
              │ 是        │ 否
              v           v
         OGG / DG    Data Pump / RMAN
```

### 推荐依据

| 条件 | 推荐方案 | 理由 |
|------|---------|------|
| 数据量 < 500GB，可停机 4h+ | Data Pump (expdp/impdp) | 简单可靠，工具成熟，跨版本兼容好 |
| 数据量 500GB~2TB，可停机 4h+ | Data Pump (并行) 或 RMAN 可传输表空间 | 并行加速，可传输减少数据转换 |
| 数据量 > 2TB，跨平台 | XTTS + 增量备份 | 减少停机窗口，增量同步 |
| 零/微停机需求 | OGG 实时同步 | 分钟级 RTO，双向同步能力 |
| 同平台同版本全库 | RMAN DUPLICATE | 最简单，一条命令完成 |
| 11g → 19c 跨版本 | Data Pump 或 OGG | expdp 兼容性最好，OGG 需处理版本适配 |

---

## 四、前置检查清单

### 4.1 源端检查

```sql
-- 归档模式检查
SELECT log_mode FROM v$database;
-- 要求：ARCHIVELOG（在线迁移/OGG 必需）

-- 补丁级别检查
SELECT action, version, comments, bundle_series
FROM dba_registry_history
ORDER BY action_time DESC;

-- 已安装组件检查
SELECT comp_id, comp_name, version, status
FROM dba_registry;

-- 闪回数据库检查
SELECT flashback_on FROM v$database;

-- 当前 SCN
SELECT current_scn FROM v$database;
```

### 4.2 目标端检查

```sql
-- 目标端存储空间评估（需大于源端数据量 × 1.3）
SELECT tablespace_name,
       ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) AS total_gb,
       ROUND(SUM(bytes) - SUM(bytes) + SUM(user_bytes) / 1024 / 1024 / 1024, 2) AS free_gb
FROM dba_data_files
GROUP BY tablespace_name;

-- 字符集兼容性检查
-- 目标端字符集必须是源端字符集的超集
SELECT parameter, value
FROM nls_database_parameters
WHERE parameter IN ('NLS_CHARACTERSET', 'NLS_NCHAR_CHARACTERSET');

-- 目标端版本兼容检查
SELECT banner_full FROM v$version;
```

### 4.3 网络与存储检查

| 检查项 | 方法 | 阈值 |
|--------|------|------|
| 网络带宽 | `iperf3` 或 `scp` 大文件测速 | 建议 ≥ 1Gbps |
| 网络延迟 | `ping` / `tcping` port 1521 | 建议 < 5ms（同城）/ < 50ms（异地） |
| 源端磁盘空间 | `df -h` | 导出目录需 ≥ 数据量 × 1.5 |
| 目标端磁盘空间 | `df -h` | 导入目录需 ≥ 数据量 × 1.5 |
| 防火墙端口 | `telnet <dst_host> 1521` | 1521 端口双向可达 |

---

## 五、迁移步骤设计

### 方案A：Data Pump 离线迁移（推荐中小规模）

```bash
# === 阶段1：源端导出 ===
# 创建目录对象
CREATE OR REPLACE DIRECTORY dpump_dir AS '/oracle/dpump';
# 导出 schema（并行 + 压缩）
expdp system/*** DIRECTORY=dpump_dir \
  SCHEMAS=<schema_name> \
  PARALLEL=<parallel_degree> \
  COMPRESSION=ALL \
  DUMPFILE=<schema>_%U.dmp \
  LOGFILE=<schema>_exp.log \
  FLASHBACK_TIME=SYSTIMESTAMP \
  METRICS=YES

# 导出全库
expdp system/*** DIRECTORY=dpump_dir \
  FULL=Y \
  PARALLEL=<parallel_degree> \
  COMPRESSION=ALL \
  DUMPFILE=full_%U.dmp \
  LOGFILE=full_exp.log \
  FLASHBACK_TIME=SYSTIMESTAMP \
  METRICS=YES

# === 阶段2：传输 dump 文件 ===
# 使用 rsync / scp / 共享存储
rsync -avP --progress /oracle/dpump/ oracle@<dst_host>:/oracle/dpump/

# === 阶段3：目标端导入 ===
# 创建表空间（如需要）
# 创建 schema 用户（如需要）
# 导入 schema
impdp system/*** DIRECTORY=dpump_dir \
  SCHEMAS=<schema_name> \
  PARALLEL=<parallel_degree> \
  DUMPFILE=<schema>_%U.dmp \
  LOGFILE=<schema>_imp.log \
  TRANSFORM=SEGMENT_ATTRIBUTES:N:TABLE \
  METRICS=YES

# 导入全库
impdp system/*** DIRECTORY=dpump_dir \
  FULL=Y \
  PARALLEL=<parallel_degree> \
  DUMPFILE=full_%U.dmp \
  LOGFILE=full_imp.log \
  METRICS=YES

# === 阶段4：导入后处理 ===
# 编译无效对象
@?/rdbms/admin/utlrp.sql
# 收集统计信息
EXEC DBMS_STATS.GATHER_SCHEMA_STATS('<schema_name>');
```

### 方案B：RMAN 可传输表空间 + 增量备份（大库跨平台）

```bash
# === 阶段1：源端全量备份 ===
# 1. 检查自包含
EXEC DBMS_TTS.TRANSPORT_SET_CHECK('<tablespace1>,<tablespace2>', TRUE);
SELECT * FROM transport_set_violations;
# 2. 置表空间为只读
ALTER TABLESPACE <tbs> READ ONLY;
# 3. 导出元数据
expdp system/*** DIRECTORY=dpump_dir \
  TRANSPORT_TABLESPACES=<tbs_list> \
  DUMPFILE=transport.dmp \
  LOGFILE=transport_exp.log
# 4. 转换数据文件（跨平台）
rman target /
RMAN> CONVERT TABLESPACE <tbs_list>
      TO PLATFORM 'Linux x86 64-bit'
      FORMAT '/oracle/convert/%U'
      PARALLELISM <parallel_degree>;

# === 阶段2：传输 + 目标端导入 ===
# 传输转换后的数据文件 + dump 文件
rsync -avP /oracle/convert/ oracle@<dst>:/oracle/convert/
# 目标端导入元数据
impdp system/*** DIRECTORY=dpump_dir \
  TRANSPORT_DATAFILES='/oracle/data/<tbs>.dbf' \
  DUMPFILE=transport.dmp \
  LOGFILE=transport_imp.log

# === 阶段3：增量备份（减少停机） ===
# 源端恢复读写后，对变化数据做增量备份
rman target /
RMAN> BACKUP INCREMENTAL LEVEL 1 FOR RECOVER OF COPY
      WITH TAG 'incr_update' DATABASE;
# 多次增量拉近源端与目标端差距

# === 阶段4：最终割接 ===
# 停写源端 → 最后一次增量备份 → 恢复目标端 → 校验 → 切读
```

### 方案C：GoldenGate 在线迁移（零/微停机）

```bash
# === 阶段1：源端 OGG 配置 ===
# 1. 开启归档 + 补充日志
ALTER DATABASE ADD SUPPLEMENTAL LOG DATA;
ALTER DATABASE ADD SUPPLEMENTAL LOG DATA (PRIMARY KEY, UNIQUE INDEX) COLUMNS;
# 2. 配置 Extract 进程
GGSCI> ADD EXTRACT ext1, TRANLOG, BEGIN NOW
GGSCI> ADD EXTTRAIL /ogg/dirdat/lt, EXTRACT ext1
GGSCI> EDIT PARAMS ext1
EXTRACT ext1
USERID ogg_user, PASSWORD ***
EXTTRAIL /ogg/dirdat/lt
TABLE <schema>.*;

# 3. 配置 Data Pump 进程
GGSCI> ADD EXTRACT pump1, EXTTRAILSOURCE /ogg/dirdat/lt
GGSCI> ADD RMTTRAIL /ogg/dirdat/rt, EXTRACT pump1
GGSCI> EDIT PARAMS pump1
EXTRACT pump1
RMTHOST <dst_host>, MGRPORT 7809
RMTTRAIL /ogg/dirdat/rt
TABLE <schema>.*;

# === 阶段2：目标端 OGG 配置 ===
GGSCI> ADD REPLICAT rep1, EXTTRAIL /ogg/dirdat/rt
GGSCI> EDIT PARAMS rep1
REPLICAT rep1
USERID ogg_user, PASSWORD ***
HANDLECOLLISIONS
MAP <schema>.*, TARGET <schema>.*;

# === 阶段3：全量初始化 ===
# 使用 Data Pump 导出导入全量数据（源端开启 Extract 后）
# 导出时记录 SCN
expdp ... FLASHBACK_SCN=<scn> ...
# 导入到目标端
impdp ... TABLE_EXISTS_ACTION=REPLACE ...
# 配置 Replicat 从该 SCN 开始增量同步
GGSCI> START REPLICAT rep1, AFTERCSN <scn>

# === 阶段4：割接 ===
# 停写源端 → 确认延迟归零 → 停 OGG → 校验 → 切换
```

### 方案D：Data Guard 切换（同平台同版本）

```bash
# === 阶段1：搭建物理备库 ===
# 1. 主库开启归档 + FORCE LOGGING
ALTER DATABASE FORCE LOGGING;
# 2. RMAN 全量备份 + 创建备库控制文件
rman target /
RMAN> BACKUP DATABASE PLUS ARCHIVELOG;
RMAN> BACKUP CURRENT CONTROLFILE FOR STANDBY;
# 3. 传输到备机并恢复
# 4. 配置 DG Broker 或手动配置
ALTER SYSTEM SET LOG_ARCHIVE_CONFIG='DG_CONFIG=(<primary>,<standby>)';
ALTER SYSTEM SET LOG_ARCHIVE_DEST_2='SERVICE=<standby> ASYNC VALID_FOR=(ONLINE_LOGFILES,PRIMARY_ROLE) DB_UNIQUE_NAME=<standby>';
# 5. 启动 REDO APPLY
ALTER DATABASE RECOVER MANAGED STANDBY DATABASE DISCONNECT FROM SESSION;

# === 阶段2：切换 ===
# 1. 确认备库同步状态
SELECT PROCESS, STATUS, THREAD#, SEQUENCE#, BLOCK# FROM V$MANAGED_STANDBY;
# 2. Switchover
ALTER DATABASE COMMIT TO SWITCHOVER TO PHYSICAL STANDBY WITH SESSION SHUTDOWN;
# 3. 新主库打开
ALTER DATABASE OPEN;
```

---

## 六、分批策略

| 策略 | 适用场景 | 方法 |
|------|---------|------|
| 按 schema 分批 | 多 schema 独立迁移 | 逐个 schema 导出导入，降低单次失败影响 |
| 按表空间分批 | 表空间粒度隔离 | 可传输表空间方式逐一迁移 |
| 按大小分批 | 含超大表（> 100GB） | 单独导出大表，并行处理中小表 |
| 按业务分批 | 多业务模块独立 | 核心业务先迁，外围后迁 |

### 大表迁移 EXCLUDE/INCLUDE 策略

```bash
# 先导出结构（不含数据），再分批次导入数据
expdp ... CONTENT=METADATA_ONLY ...
# 第一批：小表（< 1GB）
expdp ... INCLUDE=TABLE:"IN (SELECT table_name FROM ... WHERE size_mb < 1024)" ...
# 第二批：中表（1GB~100GB）
# 第三批：大表（> 100GB），单独处理，并行调高
expdp ... TABLES=<big_table> PARALLEL=8 ...
```

---

## 七、一致性校验

### 7.1 对象数量校验

```sql
-- 源端 vs 目标端对象计数对比
-- 源端
SELECT object_type, COUNT(*) AS cnt
FROM dba_objects
WHERE owner = '<schema_name>'
  AND object_type NOT IN ('INDEX PARTITION', 'TABLE PARTITION', 'LOB PARTITION')
GROUP BY object_type
ORDER BY object_type;

-- 目标端（同上）
-- 对比结果，差异项需排查
```

### 7.2 数据量校验

```sql
-- 行数校验（双侧执行）
SELECT owner, table_name, num_rows, last_analyzed
FROM dba_tables
WHERE owner = '<schema_name>'
ORDER BY num_rows DESC;

-- 段大小校验（双侧执行）
SELECT segment_name, segment_type,
       ROUND(bytes / 1024 / 1024, 2) AS size_mb
FROM dba_segments
WHERE owner = '<schema_name>'
ORDER BY size_mb DESC;
```

### 7.3 数据一致性校验

```sql
-- 表级 CHECKSUM（需逐表执行）
-- 使用 DBMS_SQLHASH 或自定义校验
-- 对核心表抽样校验
SELECT COUNT(*) AS row_count,
       SUM(ORA_HASH(column1 || column2 || ...)) AS hash_sum
FROM <schema>.<table>;
-- 双侧对比 hash_sum 值

-- 外键完整性校验
SELECT owner, table_name, constraint_name, status
FROM dba_constraints
WHERE owner = '<schema_name>'
  AND constraint_type = 'R'
  AND status = 'ENABLED';
```

### 7.4 无效对象复检

```sql
-- 目标端编译无效对象
@?/rdbms/admin/utlrp.sql
-- 编译后检查
SELECT owner, object_type, object_name, status
FROM dba_objects
WHERE owner = '<schema_name>'
  AND status = 'INVALID';
-- 要求：无效对象数 = 0 或仅剩与源端一致的无效对象
```

---

## 八、回滚与割接

### 割接步骤

| 阶段 | 动作 | 预计耗时 | 回滚 |
|------|------|---------|------|
| 割接前 | 源端全量备份 | 视数据量 | 可随时恢复 |
| T-1 | 通知业务方停写 | 即时 | — |
| T0 | 源端置只读（或停应用） | 1 min | 回滚 |
| T0+ | 最终增量同步（OGG/RMAN增量） | 视差异量 | 重试 |
| T1 | 目标端导入裁剪/恢复读写 | 10-30 min | 重试 |
| T2 | 双侧一致性校验 | 10-30 min | 重迁差异 |
| T3 | 切换应用连接串 → 目标端 | 1-5 min | 切回源端 |
| T4 | 业务验证（功能/性能） | 30 min | 切回源端 |
| T5 | 确认无误，源端保留观察 N 天 | — | 源端回退 |

### 回滚方案

| 场景 | 回滚动作 |
|------|---------|
| 导入失败 | 清理目标端 → 修复问题 → 重新导入 |
| 校验不一致 | 差异分析 → 增量补充或全量重迁 |
| 割接后性能异常 | 切回源端连接串 → 排查目标端问题 |
| 数据异常 | 源端数据未删，切回源端即可恢复 |
| 极端回滚 | 源端保留完整数据 + 备份，可随时恢复 |

> 红线：迁移完成并校验一致前，不删除源端数据。目标端验证通过后，源端至少保留 7 天观察期。

---

## 输出格式

- 结构化输出：
  1. **迁移范围评估**：源端版本/平台/字符集、数据总量、对象清单、特殊对象、无效对象
  2. **迁移方式推荐**：主方案 + 备选方案 + 选型理由
  3. **前置检查清单**：源端/目标端/网络存储检查项与结果
  4. **迁移步骤**：分阶段详细步骤（含命令/脚本，仅输出不执行）
  5. **分批策略**：按 schema/表空间/大小分批计划
  6. **一致性校验**：对象数量/数据量/数据内容校验 SQL
  7. **割接与回滚**：割接时间线、回滚方案、业务验证清单
  8. **风险与注意事项**：平台差异、字符集兼容、性能影响、特殊对象处理

## 异常处理
- 本技能仅生成方案，不直接执行、不暴露原始报错栈。
- 强调执行前必须全量备份、维护窗口内操作、监控日志与负载。
- 跨平台迁移需特别关注字节序（Endian）兼容性。
- 跨版本迁移需关注优化器行为变化、参数兼容性、废弃特性。