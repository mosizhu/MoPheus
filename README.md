# MoPheus Skills

MoPheus 平台 Skill 开发仓库。

## Skill 列表

| Skill | 描述 | 版本 |
|-------|------|------|
| [dba-tech-solution-grillme](./skills/dba-tech-solution-grillme) | DBA 决策类辅助 GrillMe，反问模糊需求生成技术方案 | v1.0.0 |

## 目录结构

```
skills/{skill-name}/
├── manifest.json    # Skill 元信息
├── config.json      # 配置（问题模板、解决方案模板）
├── main.py / main.js # Skill 主逻辑
└── README.md        # Skill 文档
```

## 创建新 Skill

```bash
mkdir -p skills/my-new-skill
# 创建 manifest.json, config.json, main.py
```

详细规范参见仓库管理规则（Git 提交规范、分支管理、命名约定等）。