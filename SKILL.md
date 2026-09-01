---
name: research-paper-daily-push
description: 根据用户配置的研究方向，检索、复核、评分、去重并中文总结近期科研论文，同时维护研究记忆并可选推送到微信。适用于每日或每周精选文献雷达；不适用于穷尽式系统综述或仅做参考文献格式整理的任务。
---

# 每日科研文献雷达

生成高选择性的中文文献雷达，不能把关键词检索结果直接堆给用户。每天最多推荐5–10篇证据充分且推荐指数不低于70分的论文；证据不足时允许少于5篇或零推荐。每篇论文中实际使用的专业术语都要给出两种解释：一条严谨的学术定义和一条忠实、易懂的比喻或大白话解释。

## 配置边界

证据复核前先阅读 [`references/research_topics.md`](references/research_topics.md)，并使用 `config/research_profile.json` 进行确定性检索和初步评分。公开配置有意留空；如果 `configured` 为 `false`，停止检索并帮助用户配置研究方向，不能臆造主题，也不能悄悄套用内置示例。创建或修改配置时阅读 [`references/profile_schema.md`](references/profile_schema.md)。

自然语言主题文件负责科学解释，JSON配置负责 API 查询、主题词组、聚焦模式、初筛权重、期刊分层、排除条件、强烈推荐条件、研究路线分类和标签词表。两者必须保持一致。

## 工作流程

1. 运行 `python scripts/run_daily.py collect --mode <mode>`。`all` 使用默认查询，聚焦模式名称来自研究配置。命令会查询 Europe PMC、Crossref、Semantic Scholar、OpenAlex 和 bioRxiv，合并重复记录，排除确认推送过的论文，并写入 `data/runs/YYYY-MM-DD/review_queue.json`。OpenAlex 可匿名检索，并使用游标读取每条查询最多600条近期记录；可选的 `OPENALEX_API_KEY` 和 `OPENALEX_MAILTO` 只能从环境变量读取，不能写入仓库或日志。
2. 先建立近24小时优先的候选池。如果达到70分的初筛候选少于5篇，自动扩展到最近7天。学术接口经常只提供日级日期，因此要把“24小时”视为优先近似窗口，并在报告中说明实际范围。
3. 阅读限定长度的 `research_memory_context`、候选题名、摘要、元数据、评分证据和待核实提示。研究记忆只用于发现连续证据、未解决问题、研究空白和重复思路，不能当成用户明确偏好的证明。
4. 对可能入选的论文进行证据核验。如果摘要缺失、截断、相互矛盾或不足以支持实质性结论，应核对 DOI、出版商页面或可信论文库页面。不能只根据题名推断结果。
5. 证据复核后重新评价每篇候选。推荐指数为 `relevance*0.40 + novelty*0.20 + quality*0.15 + methodology*0.15 + inspiration*0.10`，每个分项均为0–100分。只有检查过可用证据后，才能把 `score_status` 设为 `evidence_reviewed`。程序初筛分只用于排序，不代表最终结论。
6. 排除弱相关论文、重复论文、撤稿/勘误/社论、明显可疑来源、命中配置排除条件的研究，以及关键主张无法核实的论文。预印本要明确标注为未经过正式同行评议。陌生期刊应标记“需要核实”，不能直接判定为低质量。
7. 只保留证据充分且评分不低于70分的论文，按推荐指数降序排列，不为凑数降低标准。按照下方数据约定编写 `reviewed_articles.json`，把根字段 `term_explanation_mode` 设为 `dual`，然后运行 `python scripts/summarize_papers.py --input <reviewed.json> --output <report.md>`。
8. 只有用户或定时任务提示词明确授权外部推送时，才能运行 `python scripts/run_daily.py deliver --reviewed <reviewed.json> --report <report.md> --provider auto`。报告已经在本地真实展示时，可使用 `--skip-push --record-local-report`。只有确认推送或展示成功后，交付阶段才更新去重历史和研究记忆。

## 证据与写作规则

明确区分直接实验依据、相关性、假设和推测。使用审慎的正式科学中文。不得捏造题名、研究对象、方法、样本、数值、DOI、机制或数据集；证据不支持的细节写明“需要核实”。

每篇论文提供：忠实中文题名和英文原题、期刊/日期/DOI/链接/文章类型、总分和分项评分、100个汉字以内的推荐理由、3–5条受证据约束的核心发现，以及针对实验设计、方法、关键对象或机制、目标研究体系、未来课题或基金、高水平论文潜力和局限/验证需求的具体启发。存在研究路线阶段时，说明论文对应的阶段。拉丁学名和适用的基因名称使用斜体。添加1–8个聚焦标签。

只有证据充分，并且人工复核后满足配置的强烈推荐规则，才能设置 `strong_recommendation: true`。单纯关键词命中不能触发强烈推荐。

报告层面应包含检索/筛选/最终推荐数量、最值得阅读前三名及理由，并结合当天证据提出1–3个可检验的研究思路。

## 专业术语双重解释

覆盖中文题名、核心发现、研究启发或强烈推荐理由中实际引入的所有专业术语，包括相关方法、领域概念、机制、结构、统计学术语、计算方法和命名通路/框架。同一篇论文中的相同术语和明显别名只解释一次。

- `academic_explanation`：技术上准确的定义，说明术语是什么，并在必要时说明其测量或支持的内容；不超过180个汉字。
- `plain_explanation`：具体的比喻或大白话解释，同时保持科学边界；不超过180个汉字。

术语定义不是论文证据。不能把相关性写成因果，也不能把比喻当作真实机制。

## 已复核JSON数据约定

根对象包含 `date`、`term_explanation_mode`、`metadata`、`articles` 和 `research_ideas`。每篇论文使用以下结构：

```json
{
  "title": "英文原题",
  "chinese_title": "忠实中文题名",
  "journal": "期刊名称",
  "publication_date": "YYYY-MM-DD",
  "doi": "10.xxxx/xxxx",
  "url": "https://...",
  "article_type": "研究论文",
  "recommendation_score": 86,
  "score_status": "evidence_reviewed",
  "component_scores": {
    "relevance": 90,
    "novelty": 80,
    "quality": 85,
    "methodology": 88,
    "inspiration": 90
  },
  "why_worth_reading": "100字以内",
  "core_findings": ["3–5条受证据约束的结论"],
  "term_explanations": [
    {
      "term": "专业术语",
      "academic_explanation": "严谨解释",
      "plain_explanation": "保持科学边界的大白话解释"
    }
  ],
  "research_inspiration": {
    "experimental_design": ["..."],
    "methods": ["..."],
    "key_entities_mechanisms": ["...或需要核实"],
    "target_system": ["..."],
    "future_direction": ["..."],
    "paper_potential": ["..."],
    "limitations_validation": ["..."]
  },
  "top3_reason": "可选",
  "tags": ["主题标签"],
  "strong_recommendation": false,
  "strong_recommendation_reasons": [],
  "needs_verification": []
}
```

## 去重与研究记忆

`data/pushed_articles.json` 是交付历史。论文身份优先使用 DOI，没有 DOI 时使用规范化题名。已经推送的 DOI 不能再次作为新论文推送。预印本转为正式出版时标记为“更新”，不能当成全新论文。所有写入操作必须保持原子性。

`data/research_memory.json` 只记录已经确认交付的报告，包括精简结论、标签、已解释术语、研究路线关联、强烈推荐、未解决验证事项和研究思路。修改记忆行为时阅读 [`references/research_memory.md`](references/research_memory.md)。这是本地工作流记忆，不是模型训练。

## 通知与错误处理

通知渠道优先级为 WxPusher、Server酱、企业微信。凭据只能存放在环境变量中，不得出现在报告或日志里：

- WxPusher：`WXPUSHER_APP_TOKEN`、`WXPUSHER_UID`；可选 `WXPUSHER_CONTENT_URL`。
- Server酱：`SERVERCHAN_SENDKEY`。
- 企业微信：`WECOM_WEBHOOK_URL` 或 `WECHAT_WORK_WEBHOOK_URL`。

配置、测试或排查 WxPusher 时阅读 [`references/wxpusher_setup.md`](references/wxpusher_setup.md)。使用 `python scripts/push_wechat.py --provider wxpusher --check-config` 在本地检查配置；只有得到明确授权后，才可使用 `--test-message` 发送真实测试消息。

没有配置通知渠道时仍要正常生成报告，并准确提示：“微信推送尚未配置。”某一个文献来源失败时继续处理其他来源，并说明失败情况；所有来源都失败时停止。没有论文通过复核时生成零推荐报告，不能降低阈值。不得无限重试。

仓库不预设周期任务。只有用户明确要求时才创建或修改定时任务，并在定时提示词中写明自动交付授权。
