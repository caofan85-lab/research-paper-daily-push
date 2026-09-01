#!/usr/bin/env python3
"""Validate Codex-reviewed paper summaries and render the Chinese daily report."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from common import clean_text, load_json, normalize_doi

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
            errors.append(f"{prefix}.{field} is required")
    score = article.get("recommendation_score")
    if not isinstance(score, int) or not 0 <= score <= 100:
        errors.append(f"{prefix}.recommendation_score must be an integer from 0 to 100")
    component_scores = article.get("component_scores") or {}
    for field in ("relevance", "novelty", "quality", "methodology", "inspiration"):
        value = component_scores.get(field)
        if not isinstance(value, int) or not 0 <= value <= 100:
            errors.append(f"{prefix}.component_scores.{field} must be an integer from 0 to 100")
    why = clean_text(article.get("why_worth_reading"))
    if not why:
        errors.append(f"{prefix}.why_worth_reading is required")
    elif len(why) > 100:
        errors.append(f"{prefix}.why_worth_reading exceeds 100 characters")
    findings = _list(article.get("core_findings"))
    if not 3 <= len(findings) <= 5:
        errors.append(f"{prefix}.core_findings must contain 3-5 evidence-bound items")
    terms = _term_explanations(article.get("term_explanations"))
    if require_term_explanations and not terms:
        errors.append(f"{prefix}.term_explanations must cover the specialized terms used in this article")
    seen_terms: set[str] = set()
    for term_index, item in enumerate(terms):
        term_prefix = f"{prefix}.term_explanations[{term_index}]"
        term = clean_text(item.get("term"))
        academic = clean_text(item.get("academic_explanation"))
        plain = clean_text(item.get("plain_explanation"))
        if not term:
            errors.append(f"{term_prefix}.term is required")
        else:
            key = term.casefold()
            if key in seen_terms:
                errors.append(f"{term_prefix}.term duplicates another term in the same article")
            seen_terms.add(key)
        if not academic:
            errors.append(f"{term_prefix}.academic_explanation is required")
        elif len(academic) > 180:
            errors.append(f"{term_prefix}.academic_explanation exceeds 180 characters")
        if not plain:
            errors.append(f"{term_prefix}.plain_explanation is required")
        elif len(plain) > 180:
            errors.append(f"{term_prefix}.plain_explanation exceeds 180 characters")
        if academic and plain and academic == plain:
            errors.append(f"{term_prefix} must provide distinct academic and plain-language explanations")
    inspiration = article.get("research_inspiration") or {}
    if not isinstance(inspiration, dict):
        errors.append(f"{prefix}.research_inspiration must be an object")
    else:
        for field in REQUIRED_INSPIRATION:
            if not _list(inspiration.get(field)):
                errors.append(f"{prefix}.research_inspiration.{field} is required")
    if not 1 <= len(_list(article.get("tags"))) <= 8:
        errors.append(f"{prefix}.tags must contain 1-8 focused tags")
    if strict and article.get("score_status") != "evidence_reviewed":
        errors.append(f"{prefix}.score_status must be evidence_reviewed after Codex checks the abstract/full text")
    if article.get("strong_recommendation") and len(_list(article.get("strong_recommendation_reasons"))) < 1:
        errors.append(f"{prefix}.strong_recommendation_reasons is required for a strong recommendation")
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
        f"- Journal：{clean_text(article['journal'])}",
        f"- Published date：{clean_text(article['publication_date'])}",
        f"- DOI：{doi}",
        f"- Article URL：{clean_text(article['url'])}",
        f"- Article type：{clean_text(article['article_type'])}",
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
        raise TypeError("articles must be an array")
    errors: list[str] = []
    require_term_explanations = clean_text(payload.get("term_explanation_mode")).casefold() == "dual"
    for index, article in enumerate(articles):
        if not isinstance(article, dict):
            errors.append(f"article[{index}] must be an object")
        else:
            errors.extend(validate_article(article, index, strict, require_term_explanations))
    ideas = _list(payload.get("research_ideas"))
    if articles and not 1 <= len(ideas) <= 3:
        errors.append("research_ideas must contain 1-3 evidence-grounded ideas")
    if strict and not 0 <= len(articles) <= 10:
        errors.append("articles must contain at most 10 items")
    if errors:
        raise ValueError("Review payload validation failed:\n- " + "\n- ".join(errors))

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
            "## 今日最值得阅读 TOP 3",
            "",
            "今日无符合条件的 TOP 3。",
            "",
            "## 今日研究灵感",
            "",
            "今日暂无足够文献证据形成可靠研究灵感。",
        ])
        return "\n".join(parts).rstrip() + "\n"

    parts.append("\n\n---\n\n".join(render_article(article, rank) for rank, article in enumerate(articles, 1)))
    parts.extend(["", "## 今日最值得阅读 TOP 3", ""])
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Codex-reviewed JSON")
    parser.add_argument("--output", required=True, help="Markdown report")
    parser.add_argument("--allow-draft", action="store_true", help="Allow preliminary score_status for debugging only")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = load_json(args.input, {})
    report = render_report(payload, strict=not args.allow_draft)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8", newline="\n")
    print(f"Rendered {len(payload.get('articles') or [])} article(s) to {output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
