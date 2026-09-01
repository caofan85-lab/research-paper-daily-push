#!/usr/bin/env python3
"""验证 Codex 复核后的论文摘要数据，并生成中文每日报告。"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from common import ChineseArgumentParser, clean_text, load_json, normalize_doi

REQUIRED_INSPIRATION = (
    "experimental_design",
    "methods",
    "key_entities_mechanisms",
    "target_system",
    "future_direction",
    "paper_potential",
    "limitations_validation",
)


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if clean_text(value):
        return [clean_text(value)]
    return []


def _term_explanations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def validate_article(
    article: dict[str, Any], index: int, strict: bool, require_term_explanations: bool
) -> list[str]:
    errors: list[str] = []
    prefix = f"article[{index}]"
    for field in ("title", "chinese_title", "journal", "publication_date", "url", "article_type"):
        if not clean_text(article.get(field)):
            errors.append(f"{prefix}.{field} 为必填字段")
    score = article.get("recommendation_score")
    if not isinstance(score, int) or not 0 <= score <= 100:
        errors.append(f"{prefix}.recommendation_score 必须是0到100之间的整数")
    component_scores = article.get("component_scores") or {}
    for field in ("relevance", "novelty", "quality", "methodology", "inspiration"):
        value = component_scores.get(field)
        if not isinstance(value, int) or not 0 <= value <= 100:
            errors.append(f"{prefix}.component_scores.{field} 必须是0到100之间的整数")
    why = clean_text(article.get("why_worth_reading"))
    if not why:
        errors.append(f"{prefix}.why_worth_reading 为必填字段")
    elif len(why) > 100:
        errors.append(f"{prefix}.why_worth_reading 超过100个字符")
    findings = _list(article.get("core_findings"))
    if not 3 <= len(findings) <= 5:
        errors.append(f"{prefix}.core_findings 必须包含3–5条受证据约束的要点")
    terms = _term_explanations(article.get("term_explanations"))
    if require_term_explanations and not terms:
        errors.append(f"{prefix}.term_explanations 必须覆盖本篇论文中使用的专业术语")
    seen_terms: set[str] = set()
    for term_index, item in enumerate(terms):
        term_prefix = f"{prefix}.term_explanations[{term_index}]"
        term = clean_text(item.get("term"))
        academic = clean_text(item.get("academic_explanation"))
        plain = clean_text(item.get("plain_explanation"))
        if not term:
            errors.append(f"{term_prefix}.term 为必填字段")
        else:
            key = term.casefold()
            if key in seen_terms:
                errors.append(f"{term_prefix}.term 与本篇论文中的其他术语重复")
            seen_terms.add(key)
        if not academic:
            errors.append(f"{term_prefix}.academic_explanation 为必填字段")
        elif len(academic) > 180:
            errors.append(f"{term_prefix}.academic_explanation 超过180个字符")
        if not plain:
            errors.append(f"{term_prefix}.plain_explanation 为必填字段")
        elif len(plain) > 180:
            errors.append(f"{term_prefix}.plain_explanation 超过180个字符")
        if academic and plain and academic == plain:
            errors.append(f"{term_prefix} 的学术解释和大白话解释不能完全相同")
    inspiration = article.get("research_inspiration") or {}
    if not isinstance(inspiration, dict):
        errors.append(f"{prefix}.research_inspiration 必须是对象")
    else:
        for field in REQUIRED_INSPIRATION:
            if not _list(inspiration.get(field)):
                errors.append(f"{prefix}.research_inspiration.{field} 为必填字段")
    if not 1 <= len(_list(article.get("tags"))) <= 8:
        errors.append(f"{prefix}.tags 必须包含1–8个聚焦标签")
    if strict and article.get("score_status") != "evidence_reviewed":
        errors.append(f"Codex 核对摘要或全文后，{prefix}.score_status 必须设为 evidence_reviewed")
    if article.get("strong_recommendation") and len(_list(article.get("strong_recommendation_reasons"))) < 1:
        errors.append(f"强烈推荐时必须填写 {prefix}.strong_recommendation_reasons")
    return errors


def stars(relevance: int) -> str:
    filled = max(1, min(5, round(relevance / 20)))
    return "★" * filled + "☆" * (5 - filled)


def line_items(values: Any, prefix: str = "- ") -> list[str]:
    return [f"{prefix}{item}" for item in _list(values)]


def render_article(article: dict[str, Any], rank: int) -> str:
    strong = bool(article.get("strong_recommendation"))
    heading = f"### {rank}. {clean_text(article['chinese_title'])}"
    if strong:
        heading += "　🔥 **强烈推荐**"
    doi = normalize_doi(article.get("doi")) or "暂无/需核实"
    components = article.get("component_scores") or {}
    tags = " ".join(
        tag if str(tag).startswith("#") else f"#{clean_text(tag).replace(' ', '')}"
        for tag in _list(article.get("tags"))
    )
    sections = [
        heading,
        "",
        f"**英文原题：** {clean_text(article['title'])}",
        "",
        f"- 期刊：{clean_text(article['journal'])}",
        f"- 发表日期：{clean_text(article['publication_date'])}",
        f"- DOI：{doi}",
        f"- 论文链接：{clean_text(article['url'])}",
        f"- 论文类型：{clean_text(article['article_type'])}",
        "",
        f"**推荐指数：{article['recommendation_score']}/100**",
        f"**相关性：{stars(int(components.get('relevance') or 0))}**",
        (
            "分项：相关性 {relevance}｜创新性 {novelty}｜期刊/论文质量 {quality}｜"
            "方法学价值 {methodology}｜研究启发 {inspiration}"
        ).format(**components),
        "",
        f"**为什么值得看：** {clean_text(article['why_worth_reading'])}",
        "",
        "**核心发现**",
        "",
    ]
    sections.extend(f"{number}. {finding}" for number, finding in enumerate(_list(article["core_findings"]), 1))
    terms = _term_explanations(article.get("term_explanations"))
    if terms:
        sections.extend(["", "**学术名词双重解释**", ""])
        for number, item in enumerate(terms, 1):
            sections.extend([
                f"{number}. **{clean_text(item.get('term'))}**",
                f"   - 正常解释：{clean_text(item.get('academic_explanation'))}",
                f"   - 比喻/大白话：{clean_text(item.get('plain_explanation'))}",
            ])
    sections.extend(["", "**对我的研究有什么启发**", ""])
    labels = {
        "experimental_design": "可借鉴的实验设计",
        "methods": "值得采用的技术",
        "key_entities_mechanisms": "值得关注的对象/机制",
        "target_system": "向目标研究体系延伸",
        "future_direction": "潜在研究或基金方向",
        "paper_potential": "高水平论文潜力",
        "limitations_validation": "局限与验证需求",
    }
    inspiration = article["research_inspiration"]
    for field in REQUIRED_INSPIRATION:
        value = "；".join(_list(inspiration.get(field)))
        sections.append(f"- **{labels[field]}：** {value}")
    if strong:
        sections.extend(["", "**🔥 强烈推荐理由**", ""])
        sections.extend(line_items(article.get("strong_recommendation_reasons")))
    verification = _list(article.get("needs_verification"))
    if verification:
        sections.extend(["", "**需核实：** " + "；".join(verification)])
    sections.extend(["", f"**重点标记：** {tags}"])
    return "\n".join(sections)


def render_report(payload: dict[str, Any], strict: bool = True) -> str:
    articles = payload.get("articles") or []
    if not isinstance(articles, list):
        raise TypeError("articles 必须是数组")
    errors: list[str] = []
    require_term_explanations = clean_text(payload.get("term_explanation_mode")).casefold() == "dual"
    for index, article in enumerate(articles):
        if not isinstance(article, dict):
            errors.append(f"article[{index}] 必须是对象")
        else:
            errors.extend(validate_article(article, index, strict, require_term_explanations))
    ideas = _list(payload.get("research_ideas"))
    if articles and not 1 <= len(ideas) <= 3:
        errors.append("research_ideas 必须包含1–3个以证据为基础的研究思路")
    if strict and not 0 <= len(articles) <= 10:
        errors.append("articles 最多只能包含10篇论文")
    if errors:
        raise ValueError("已复核数据验证失败：\n- " + "\n- ".join(errors))

    report_date = clean_text(payload.get("date")) or datetime.now().astimezone().date().isoformat()
    metadata = payload.get("metadata") or {}
    retrieved = int(metadata.get("retrieved_count") or 0)
    screened = int(metadata.get("screened_count") or 0)
    articles = sorted(articles, key=lambda item: int(item.get("recommendation_score") or 0), reverse=True)
    parts = [
        "# 【今日科研文献雷达】",
        "",
        f"日期：{report_date}  ",
        f"检索论文：{retrieved}篇  ",
        f"筛选论文：{screened}篇  ",
        f"最终推荐：{len(articles)}篇",
        "",
    ]
    warnings = _list(metadata.get("warnings"))
    if warnings:
        parts.extend(["> 检索提示：" + "；".join(warnings), ""])
    if not articles:
        parts.extend([
            "今天没有达到推荐阈值且证据充分的论文。宁缺毋滥，不用低相关性论文填充名额。",
            "",
            "## 今日最值得阅读前三名",
            "",
            "今日没有符合条件的前三名论文。",
            "",
            "## 今日研究灵感",
            "",
            "今日暂无足够文献证据形成可靠研究灵感。",
        ])
        return "\n".join(parts).rstrip() + "\n"

    parts.append("\n\n---\n\n".join(render_article(article, rank) for rank, article in enumerate(articles, 1)))
    parts.extend(["", "## 今日最值得阅读前三名", ""])
    medals = ("🥇", "🥈", "🥉")
    ordinals = ("第一篇", "第二篇", "第三篇")
    for index, article in enumerate(articles[:3]):
        reason = clean_text(article.get("top3_reason")) or clean_text(article.get("why_worth_reading"))
        parts.extend([
            f"{medals[index]} **{ordinals[index]}：{clean_text(article['chinese_title'])}**",
            "",
            reason,
            "",
        ])
    parts.extend(["## 今日研究灵感", ""])
    parts.extend(f"{index}. {idea}" for index, idea in enumerate(ideas, 1))
    return "\n".join(parts).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = ChineseArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="经过 Codex 复核的 JSON")
    parser.add_argument("--output", required=True, help="Markdown 报告路径")
    parser.add_argument("--allow-draft", action="store_true", help="仅调试时允许使用初步 score_status")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = load_json(args.input, {})
    report = render_report(payload, strict=not args.allow_draft)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8", newline="\n")
    print(f"已将 {len(payload.get('articles') or [])} 篇论文写入报告：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
