---
name: research-paper-daily-push
description: Search, evidence-review, score, deduplicate, summarize, remember, and optionally push a small daily or weekly set of recent research papers for a user-configured topic. Use for selective literature-radar requests; do not use for exhaustive systematic reviews or citation-only formatting.
---

# Research Paper Daily Push

Produce a selective Chinese literature radar, not a keyword dump. Recommend at most 5–10 evidence-supported papers scoring at least 70/100; return fewer or zero when evidence is weak. Explain every specialized term used in each paper twice: one precise academic definition and one faithful analogy or plain-language explanation.

## Configuration boundary

Read [references/research_topics.md](references/research_topics.md) before evidence review and use `config/research_profile.json` for deterministic search and preliminary scoring. The public profile is intentionally blank. If `configured` is `false`, stop and help the user define the research topic; never invent a topic or silently use a bundled example. Read [references/profile_schema.md](references/profile_schema.md) when creating or changing a profile.

The narrative topic file controls scientific interpretation. The JSON profile controls API queries, keyword groups, focused modes, preliminary weights, quality tiers, exclusions, strong-recommendation conditions, roadmap classification, and tag vocabulary. Keep them consistent.

## Workflow

1. Run `python scripts/run_daily.py collect --mode <mode>`. `all` uses the default profile queries; focused mode names come from the profile. The command queries Europe PMC, Crossref, Semantic Scholar, and bioRxiv; merges duplicates; filters confirmed delivery history; and writes `data/runs/YYYY-MM-DD/review_queue.json`.
2. Start with a near-24-hour discovery pool. If fewer than five preliminary candidates reach 70, expand automatically to seven days. Scholarly APIs often provide only day-level dates, so treat “24 hours” as a prioritized approximation and disclose the window.
3. Read the bounded `research_memory_context`, candidate titles, abstracts, metadata, score evidence, and verification warnings. Use memory to detect accumulating evidence, unresolved questions, gaps, and repeated ideas—not as proof of user preference.
4. For likely finalists, verify the DOI and publisher or repository page when the abstract is absent, truncated, contradictory, or insufficient for a substantive claim. Never infer results from a title alone.
5. Re-score each finalist after evidence review. The index is `relevance*0.40 + novelty*0.20 + quality*0.15 + methodology*0.15 + inspiration*0.10`, with every component on 0–100. Set `score_status` to `evidence_reviewed` only after checking available evidence. The deterministic score is a routing aid, not ground truth.
6. Exclude weakly related papers, duplicates, retractions/corrections/editorials, questionable venues, studies matching configured exclusions, and papers whose key claims cannot be verified. Label preprints as unreviewed evidence. An unfamiliar journal is “needs verification”, not automatically low quality.
7. Select only evidence-supported papers scoring at least 70, sorted high to low, without quota filling. Write `reviewed_articles.json` using the contract below, set root `term_explanation_mode` to `dual`, then render with `python scripts/summarize_papers.py --input <reviewed.json> --output <report.md>`.
8. Push only when the user or scheduled-task prompt authorizes the external side effect: `python scripts/run_daily.py deliver --reviewed <reviewed.json> --report <report.md> --provider auto`. For a report that was actually presented locally, use `--skip-push --record-local-report`. The deliver stage commits deduplication history and research memory only after confirmed delivery or presentation.

## Evidence and writing rules

Distinguish direct evidence, correlation, hypothesis, and speculation. Use cautious scientific Chinese. Do not fabricate titles, entities, methods, samples, numerical results, DOIs, mechanisms, or datasets. Write “需要核实” when a detail is not supported.

For each paper, provide a faithful Chinese title plus the original title, journal/date/DOI/URL/type, overall and component scores, one reason under 100 Chinese characters, 3–5 evidence-bound findings, and tailored implications for experimental design, methods, key entities or mechanisms, the configured target system, future projects or grants, paper potential, and limitations/validation. Explain which configured roadmap stage it informs when stages exist. Italicize Latin species and gene names when appropriate. Add 1–8 focused tags.

Use `strong_recommendation: true` only when evidence is sufficient and the paper satisfies a configured strong-recommendation rule after human review. A keyword match alone is never enough.

At report level, include retrieved/screened/final counts, TOP 3 reasons, and 1–3 testable research ideas synthesized from that day's evidence.

## Dual term explanations

Cover every specialized term actually introduced in the Chinese title, findings, implications, or strong-recommendation reasoning. Include relevant methods, domain concepts, mechanisms, structures, statistics, computational methods, and named pathways or frameworks. Deduplicate exact terms and obvious aliases within the paper.

- `academic_explanation`: a technically correct definition explaining what the term is and, when useful, what it measures or supports; at most 180 Chinese characters.
- `plain_explanation`: a concrete analogy or plain-language explanation that preserves scientific boundaries; at most 180 Chinese characters.

Definitions do not constitute evidence for the paper. Do not turn association into causation or present an analogy as the literal mechanism.

## Reviewed JSON contract

The root contains `date`, `term_explanation_mode`, `metadata`, `articles`, and `research_ideas`. Each article includes:

```json
{
  "title": "Original title",
  "chinese_title": "忠实中文题名",
  "journal": "Journal",
  "publication_date": "YYYY-MM-DD",
  "doi": "10.xxxx/xxxx",
  "url": "https://...",
  "article_type": "research article",
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
  "core_findings": ["3–5条证据限定的结论"],
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

## Deduplication and memory

`data/pushed_articles.json` is the delivery history. Identity is DOI-first with normalized-title fallback. Never push an existing DOI as new. Treat a preprint-to-formal-publication change as an update rather than a new paper. Writes are atomic.

`data/research_memory.json` records only confirmed reports: compact lessons, tags, explained terms, roadmap links, strong recommendations, unresolved validation items, and research ideas. Read [references/research_memory.md](references/research_memory.md) when changing memory behavior. This is local workflow memory, not model training.

## Notification and errors

Provider order is WxPusher, ServerChan, then WeCom. Credentials must remain in environment variables and never appear in reports or logs:

- WxPusher: `WXPUSHER_APP_TOKEN`, `WXPUSHER_UID`; optional `WXPUSHER_CONTENT_URL`.
- ServerChan: `SERVERCHAN_SENDKEY`.
- WeCom: `WECOM_WEBHOOK_URL` or `WECHAT_WORK_WEBHOOK_URL`.

When configuring, testing, or troubleshooting WxPusher, read [references/wxpusher_setup.md](references/wxpusher_setup.md). Validate settings locally with `python scripts/push_wechat.py --provider wxpusher --check-config`. Send a real connectivity test only when explicitly authorized, using `--test-message`.

If no provider is configured, still generate the report and state exactly: “微信推送尚未配置。” If one source fails, continue and disclose it. If every source fails, stop. If no paper survives review, generate a zero-result report instead of lowering the threshold. Do not retry indefinitely.

Recurring schedules are intentionally not bundled. Create or change a schedule only when the user explicitly asks, and include explicit delivery authorization in the scheduled prompt.
