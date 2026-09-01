# 研究配置结构

公开版本中的 `config/research_profile.json` 有意保持空白。只有必填字段已经填写完整时，才能把 `configured` 设置为 `true`。

## 必填字段

- `profile_name`：显示在运行元数据中的简短配置名称。
- `research_context`：用于帮助判断相关性的精简研究背景。
- `target_system`：生物、疾病、材料、技术、人群或其他主要研究对象。
- `priority_questions`：指导最终证据复核的核心科学问题。
- `queries`：默认 `all` 模式使用的布尔式 API 查询语句。
- `topic_groups`：用于确定性初筛的主题组。每一项包含 `label`、1–100的 `weight` 和非空 `terms` 数组。

至少需要一条查询和一个有效主题组。配置为空时，程序会提示配置错误并停止，不能返回无关论文。

## 可选字段

- `modes`：命名的聚焦模式。每个键对应一个包含 `queries` 数组的对象。
- `cross_topic_bonuses`：包含 `labels`、`bonus` 和可选 `reason` 的条目。只有列出的全部主题组都命中时才应用加分。
- `method_groups`：包含 `label` 和 `terms` 的条目，用于扩展内置通用方法识别器。
- `quality_tiers`：由 `tier_1`、`tier_2` 和 `tier_3` 组成的规范化期刊名称数组。
- `exclusion_terms`：题名或摘要命中后触发初步排除的词语。该列表应保持保守。
- `mechanistic_terms`：提示机制性证据或高信息量证据的领域专用术语。
- `strong_recommendation_rules`：包含 `labels`、可选 `methods`、`min_score` 和 `reason` 的条目。所有已配置条件都必须同时命中。
- `roadmap_stages`：包含 `label` 和 `keywords` 的条目，只用于在研究记忆中归类已经确认的报告。
- `tags`：偏好的报告标签。

权重和关键词命中只用于初步排序，不是最终证据。Codex 仍必须阅读可用摘要或全文，并独立重新评价每篇候选论文。
