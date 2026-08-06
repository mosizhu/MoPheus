"""
MoPheus Skill: DBA 技术方案反问机 (dba-tech-solution-grillme)

定位：决策类辅助 GrillMe
功能：当 DBA 提出模糊需求时，通过系统性反问识别关键信息缺口，
      最终输出结构化技术方案。

支持场景：
  - Oracle → 达梦 迁移
  - 通用数据库迁移
  - 可扩展：性能调优、高可用设计、备份恢复等
"""

import json
import os
import re
from typing import Any, Optional


class GrillMeEngine:
    """GrillMe 反问引擎：基于场景配置进行交互式问题追问。"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.scenarios = self.config.get("scenarios", {})
        self.methodology = self.config.get("methodology", {})
        self.risks = self.config.get("risk_knowledge", {})

    # ------------------------------------------------------------------ #
    #  场景识别
    # ------------------------------------------------------------------ #

    def identify_scenario(self, user_input: str) -> Optional[dict]:
        """根据用户输入匹配最可能的场景。"""
        user_input_lower = user_input.lower()

        best_match = None
        best_score = 0

        for scenario in self.scenarios.values():
            keywords = scenario.get("keywords", [])
            score = sum(
                1 for kw in keywords if kw.lower() in user_input_lower
            )
            if score > best_score:
                best_score = score
                best_match = scenario

        if best_match:
            return best_match
        return None

    # ------------------------------------------------------------------ #
    #  问题流管理
    # ------------------------------------------------------------------ #

    def get_questions(self, scenario_id: str) -> list[dict]:
        """获取指定场景的问题列表。"""
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            return []
        return scenario.get("questions", [])

    def filter_required_questions(self, questions: list[dict]) -> list[dict]:
        """筛选必填问题。"""
        return [q for q in questions if q.get("required", False)]

    # ------------------------------------------------------------------ #
    #  方法论推荐
    # ------------------------------------------------------------------ #

    def recommend_methodology(self, answers: dict) -> dict:
        """根据用户回答推荐迁移方法论。"""
        downtime = answers.get("downtime", "")
        data_size = answers.get("data_size", "")
        ha_req = answers.get("ha_requirement", "")

        if downtime in ("< 1 小时", "1 - 4 小时"):
            return self.methodology.get("online_migration", {})
        elif downtime in ("可接受长时间停机", "> 24 小时"):
            return self.methodology.get("offline_migration", {})
        else:
            if ha_req in ("需要 RAC 级别的高可用", "主备/读写分离"):
                return self.methodology.get("dual_write_migration", {})
            return self.methodology.get("online_migration", {})

    # ------------------------------------------------------------------ #
    #  方案生成
    # ------------------------------------------------------------------ #

    def generate_solution(self, scenario_id: str, answers: dict) -> str:
        """基于场景和回答生成结构化技术方案。"""
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            return "抱歉，无法识别当前场景。请提供更详细的需求描述。"

        templates = scenario.get("solution_templates", {})
        title = templates.get("title", "技术方案")
        sections = templates.get("sections", [])

        methodology = self.recommend_methodology(answers)
        method_name = methodology.get("name", "")
        method_steps = methodology.get("steps", [])

        scope = answers.get("scope", "未指定")
        data_size = answers.get("data_size", "未指定")
        downtime = answers.get("downtime", "未指定")
        version = answers.get("version", "未指定")
        special = answers.get("special_objects", "无特殊对象")
        app_mod = answers.get("app_modification", "未指定")
        validation = answers.get("data_validation", "未指定")
        rollback = answers.get("rollback", "未指定")
        perf_req = answers.get("performance_requirement", "未指定")

        special_handling = self._build_special_handling(special)
        app_plan = self._build_app_plan(app_mod)
        validation_plan = self._build_validation_plan(validation)
        rollback_plan = self._build_rollback_plan(rollback)
        risk_assessment = self._build_risk_assessment(scenario_id, answers)

        output = [f"# {title}", ""]

        for section in sections:
            output.append(f"## {section['name']}")

            template = section["template"]
            template = template.replace("{scope}", scope)
            template = template.replace("{data_size}", data_size)
            template = template.replace("{downtime}", downtime)
            template = template.replace("{version}", version)
            template = template.replace("{special_objects}", special)
            template = template.replace("{app_modification}", app_mod)
            template = template.replace("{data_validation}", validation)
            template = template.replace("{rollback}", rollback)
            template = template.replace("{performance_requirement}", perf_req)

            template = template.replace(
                "{methodology_recommendation}",
                f"**推荐方案：{method_name}**\n\n"
                f"适用条件：停机窗口 {downtime}，数据规模 {data_size}\n\n"
                f"推荐工具：{', '.join(methodology.get('tools', []))}"
            )
            template = template.replace(
                "{detailed_steps}",
                "\n".join(f"  {step}" for step in method_steps)
            )
            template = template.replace("{special_objects_handling}", special_handling)
            template = template.replace("{app_modification_plan}", app_plan)
            template = template.replace("{validation_plan}", validation_plan)
            template = template.replace("{rollback_plan}", rollback_plan)
            template = template.replace("{risk_assessment}", risk_assessment)

            output.append(template)
            output.append("")

        output.append("---")
        output.append("*本方案由 DBA 技术方案反问机自动生成，请结合实际情况进行调整。*")
        return "\n".join(output)

    # ------------------------------------------------------------------ #
    #  内部辅助方法
    # ------------------------------------------------------------------ #

    def _build_special_handling(self, special: str) -> str:
        if not special or special == "无特殊对象":
            return "源库无特殊对象，无需额外处理。\n\n**建议：**\n1. 执行 `USER_SOURCE` 检查，确认所有 PL/SQL 对象编译状态\n2. 检查字典视图一致性"

        items = [s.strip() for s in re.split(r"[,，、]", special) if s.strip()]
        handling = []

        mapping = {
            "存储过程": "✅ 存储过程/函数/包：达梦对 PL/SQL 兼容性有限\n  - 建议：评估复杂度，简单 PL/SQL 可直接迁移，复杂逻辑需改写为达梦 DMSQL\n  - 工具：使用达梦 DTS 工具进行语法转换\n  - 验证：迁移后逐一重新编译并执行单元测试",
            "触发器": "⚙️ 触发器：达梦支持标准 SQL 触发器\n  - 注意：Oracle 特有的触发器类型（如 INSTEAD OF、复合触发器）可能需要改写\n  - 建议：转换后逐一验证触发器逻辑",
            "存储过程/函数/包": "✅ 存储过程/函数/包：达梦对 PL/SQL 兼容性有限\n  - 建议：评估复杂度，简单 PL/SQL 可直接迁移，复杂逻辑需改写为达梦 DMSQL\n  - 验证：迁移后逐一重新编译",
            "LOB": "📦 LOB 大字段：\n  - 达梦支持 CLOB/BLOB，但存储机制不同\n  - 建议：使用 DMETL 流式传输大对象，避免内存溢出\n  - 验证：抽样对比大字段内容完整性",
            "JSON": "📄 JSON 类型：\n  - Oracle 20c+ 支持原生 JSON，达梦也支持\n  - 建议：验证 JSON 查询函数兼容性，必要时改用达梦 JSON 函数",
            "物化视图": "🔄 物化视图：\n  - 达梦支持物化视图，但刷新机制不同\n  - 建议：改为定时任务 + 手动刷新策略",
            "同义词": "🔗 同义词/序列：\n  - 达梦支持同义词和序列，但注意对象引用方式\n  - 建议：迁移后重新编译所有同义词引用的对象",
        }

        for item in items:
            matched = False
            for key, value in mapping.items():
                if key.lower() in item.lower():
                    handling.append(value)
                    matched = True
                    break
            if not matched and item not in ("以上都没有",):
                handling.append(f"⚠️ {item}：需评估兼容性，建议制定专项迁移方案")

        return "\n\n".join(handling) if handling else "无需处理的特殊对象。"

    def _build_app_plan(self, app_mod: str) -> str:
        plans = {
            "需要全面改造": [
                "1. SQL 方言适配层：建立 SQL 转换中间件或 DAO 层",
                "2. 驱动替换：ojdbc → dmjdbc，注意连接串格式差异",
                "3. 数据类型映射：",
                "   - Oracle NUMBER → DM DECIMAL/NUMERIC",
                "   - Oracle VARCHAR2 → DM VARCHAR",
                "   - Oracle DATE → DM DATETIME/TIMESTAMP",
                "4. 事务语法改造：COMMIT/ROLLBACK 行为验证",
                "5. 分页语法改造：ROWNUM → LIMIT/OFFSET",
                "6. 存储过程调用改造：需重写或使用兼容模式"
            ],
            "仅需替换驱动": [
                "1. 替换 JDBC 驱动为 dmjdbc",
                "2. 修改连接串为达梦格式",
                "3. 验证 SQL 兼容性（重点检查 Oracle 特有函数）",
                "4. 灰度发布：先在测试环境验证所有业务 SQL"
            ],
            "已有适配层，改造量小": [
                "1. 确认适配层对达梦的支持完善度",
                "2. 补充达梦特有的数据类型映射",
                "3. 回归测试：全量业务功能验证"
            ],
            "尚未评估": [
                "1. 建议先对应用 SQL 进行全面梳理",
                "2. 统计 Oracle 特有 SQL 语法使用情况",
                "3. 评估改造工作量后再制定详细计划"
            ]
        }
        for key, value in plans.items():
            if key in app_mod:
                return "\n".join(value)
        return "尚未制定应用改造方案，建议先进行 SQL 兼容性评估。"

    def _build_validation_plan(self, validation: str) -> str:
        if "全量" in validation:
            return "\n".join([
                "1. 行数对比：按表统计源端和目标端行数差异",
                "2. 内容校验：按主键逐行比对（建议使用达梦 DTS 校验工具）",
                "3. 索引校验：验证所有索引的正确性",
                "4. 抽样深度校验：对关键字段进行哈希比对",
                "5. 业务层校验：执行业务流程测试，验证数据完整性"
            ])
        elif "抽样" in validation:
            return "\n".join([
                "1. 关键字段全量校验：主键、外键、业务关键字段",
                "2. 随机抽样：每表随机抽取 1% 记录进行深度比对",
                "3. 热点数据校验：优先校验高频访问的热数据",
                "4. 业务流程验证：通过接口测试验证核心业务流程"
            ])
        elif "业务" in validation:
            return "\n".join([
                "1. 核心业务流程端到端验证",
                "2. 报表/统计数据对比",
                "3. 用户登录/权限验证",
                "4. 关联查询正确性验证"
            ])
        return "尚未规划数据校验方案，建议制定：行数对比 + 关键字段校验 + 业务流程验证的组合策略。"

    def _build_rollback_plan(self, rollback: str) -> str:
        if "双写" in rollback:
            return "\n".join([
                "1. 切换前：保持双写运行，Oracle 和达梦数据双向同步",
                "2. 切换后：保留 Oracle 环境，设置反向同步通道",
                "3. 回滚条件：达梦出现严重故障或数据不一致",
                "4. 回滚步骤：",
                "   a. 停止写入达梦",
                "   b. 从 Oracle 恢复最近数据",
                "   c. 切换应用回 Oracle",
                "   d. 排查问题后重新评估切换可行性",
                "5. 回滚时间：预计 30 分钟内可完成回退"
            ])
        elif "反向" in rollback:
            return "\n".join([
                "1. 切换前：保留 Oracle 环境，启动反向同步通道",
                "2. 反向同步：达梦 → Oracle，确保数据实时回写",
                "3. 回滚条件：达梦运行异常或性能不达标",
                "4. 回滚步骤：",
                "   a. 确认 Oracle 数据同步完成",
                "   b. 切换应用回 Oracle",
                "   c. 验证业务恢复正常",
                "5. 回滚时间：预计 15 分钟内"
            ])
        elif "直接" in rollback:
            return "\n".join([
                "⚠️ 直接回滚风险较高，建议：",
                "1. 切换前：完整备份 Oracle 数据库",
                "2. 切换后：Oracle 环境保留 7 天",
                "3. 回滚条件：达梦环境不可用",
                "4. 回滚步骤：",
                "   a. 停止应用",
                "   b. 恢复应用配置指向 Oracle",
                "   c. 启动应用",
                "5. 注意：切换期间的数据变更可能丢失"
            ])
        return "\n".join([
            "尚未制定回滚方案，建议：",
            "1. 切换前完整备份源端 Oracle",
            "2. 保留源端环境至少 7 天",
            "3. 建立反向数据同步通道",
            "4. 制定详细的回滚操作手册",
            "5. 进行至少 2 次回滚演练"
        ])

    def _build_risk_assessment(self, scenario_id: str, answers: dict) -> str:
        risks = []

        if "oracle" in scenario_id.lower() or "达梦" in scenario_id:
            common_risks = self.risks.get("oracle_to_dm_common_risks", [])
            risks.extend(common_risks)

        special = answers.get("special_objects", "")
        if "存储过程" in special or "函数" in special or "包" in special:
            risks.append(
                "🔴 **高风险**：存储过程/函数/包兼容性问题 - "
                "建议投入 30% 以上的迁移工作量在 PL/SQL 改造上"
            )

        if "LOB" in special or "BLOB" in special or "CLOB" in special:
            risks.append(
                "🟡 **中风险**：LOB 大对象迁移需验证完整性，建议使用流式传输"
            )

        if "JSON" in special:
            risks.append(
                "🟡 **中风险**：JSON 查询函数兼容性需逐个验证"
            )

        ha = answers.get("ha_requirement", "")
        if "RAC" in ha or "集群" in ha or "高可用" in ha:
            risks.append(
                "🟡 **中风险**：高可用架构搭建复杂度 - 达梦 MPEC 集群与 Oracle RAC 架构差异大"
            )

        app_mod = answers.get("app_modification", "")
        if "全面改造" in app_mod:
            risks.append(
                "🟡 **中风险**：应用层改造范围大，建议分阶段灰度推进"
            )

        perf = answers.get("performance_requirement", "")
        if "不得下降" in perf:
            risks.append(
                "🟡 **中风险**：性能要求严格，需要提前进行基准测试和 SQL 调优"
            )

        if not risks:
            risks.append("暂未识别出高风险项，建议关注：数据一致性、业务回归测试、性能表现")

        return "\n".join(risks)


def main():
    """交互入口：命令行模式下的 GrilMe 对话。"""
    engine = GrillMeEngine()

    print("=" * 60)
    print("  DBA 技术方案反问机 (dba-tech-solution-grillme)")
    print("  输入模糊需求，我会通过反问帮你梳理技术方案")
    print("=" * 60)
    print()

    user_input = input("请描述你的需求（如：做 Oracle 迁移达梦）：").strip()
    if not user_input:
        print("未检测到需求，退出。")
        return

    scenario = engine.identify_scenario(user_input)
    if not scenario:
        print("未能识别需求场景。当前支持的场景：")
        for s in engine.scenarios.values():
            print(f"  - {s['name']}")
        print("\n请尝试用更具体的描述。")
        return

    scenario_id = scenario["id"]
    print(f"\n✅ 已识别场景：{scenario['name']}")

    questions = engine.get_questions(scenario_id)
    answers = {}

    print("\n📋 请回答以下问题（输入选项编号或直接作答）：\n")

    for q in questions:
        print(f"【{q['category']}】{q['text']}")

        if q.get("options"):
            for i, opt in enumerate(q["options"], 1):
                print(f"  {i}. {opt}")
            raw = input("你的选择：").strip()
            try:
                idx = int(raw)
                answers[q["id"]] = q["options"][idx - 1]
            except (ValueError, IndexError):
                answers[q["id"]] = raw if raw else q["options"][0]
        else:
            raw = input("你的回答：").strip()
            answers[q["id"]] = raw if raw else "未指定"

        print()

    print("\n" + "=" * 60)
    print("  正在生成技术方案...")
    print("=" * 60 + "\n")

    solution = engine.generate_solution(scenario_id, answers)
    print(solution)


if __name__ == "__main__":
    main()
