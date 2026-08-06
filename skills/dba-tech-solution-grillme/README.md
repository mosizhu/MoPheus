# dba-tech-solution-grillme

> **定位**：决策类辅助 GrillMe  
> **功能**：当 DBA 提出模糊需求时，通过系统性反问识别关键信息缺口，最终输出结构化技术方案。

## 使用场景

DBA 经常会提出模糊的需求，例如：

- "做 Oracle 迁移达梦"
- "这个系统怎么调优"
- "数据库怎么高可用"

本 Skill 通过一系列标准化的反问，帮助梳理出完整的技术方案。

## 工作流程

```
用户模糊需求 → 场景识别 → 反问收集关键信息 → 结构化方案输出
```

### 示例交互

**用户输入**：`做 Oracle 迁移达梦`

**Skill 反问**：
1. 迁移范围：全量 / 按模块 / 按表？
2. 数据量规模？
3. 停机窗口？
4. 源版本 → 目标版本？
5. 是否有存储过程/LOB/JSON 等特殊对象？
6. 是否需要高可用？
7. 应用层是否需要改造？
8. 数据校验方案？
9. 回滚预案？

**Skill 输出**：结构化技术方案，包含迁移概述、方案选型、特殊对象处理、应用改造、数据校验、回滚预案、风险评估等章节。

## 支持场景

| 场景 ID | 场景名称 | 触发关键词 |
|---------|---------|-----------|
| `oracle-to-dm` | Oracle → 达梦迁移 | oracle, 达梦, 迁移, 国产, 替代 |
| `generic-migration` | 通用数据库迁移 | 迁移, 数据库搬迁, 数据同步 |

## 目录结构

```
dba-tech-solution-grillme/
├── manifest.json    # Skill 元信息
├── config.json      # 场景配置 + 问题模板 + 解决方案模板
├── main.py          # 核心引擎（场景识别、反问流程、方案生成）
└── README.md        # 说明文档
```

## 扩展指南

### 添加新场景

在 `config.json` 的 `scenarios` 下新增场景：

```json
"new-scenario": {
  "id": "new-scenario",
  "name": "新场景名称",
  "keywords": ["关键词1", "关键词2"],
  "questions": [
    {
      "id": "q1",
      "category": "分类",
      "text": "反问内容",
      "options": ["选项A", "选项B"],
      "required": true
    }
  ],
  "solution_templates": {
    "title": "方案标题",
    "sections": [...]
  }
}
```

### 添加风险知识库

在 `config.json` 的 `risk_knowledge` 下添加场景相关的风险列表。

## 运行方式

```bash
cd skills/dba-tech-solution-grillme
python3 main.py
```

## 版本历史

- `v1.0.0` - 初始版本，支持 Oracle → 达梦迁移、通用数据库迁移两个场景
