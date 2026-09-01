#!/usr/bin/env python3
"""根据已交付的每日报告维护精简、持久化的研究记忆。"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from common import (
    ChineseArgumentParser,
    atomic_write_json,
    clean_text,
    load_json,
    normalize_doi,
    paper_key,
    unique_strings,
    utc_now_iso,
)
from profile_config import DEFAULT_PROFILE, load_profile, named_term_groups

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_MEMORY = SKILL_DIR / "data" / "research_memory.json"
SCOPE_NOTE = (
    "报告入选仅表示论文已经过证据复核并被认为值得阅读，不等于用户明确表示喜欢；"
    "明确的用户反馈应单独记录，并优先于自动归纳信号。"
)

def empty_memory() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "",
        "scope_note": SCOPE_NOTE,
        "learned_reports": [],
        "papers": [],
        "research_ideas": [],
        "explicit_preferences": {
            "liked_topics": [],
            "disliked_topics": [],
            "notes": [],
        },
        "signals": {
            "tag_counts": {},
            "key_term_counts": {},
            "roadmap_stage_counts": {},
            "strong_recommendation_count": 0,
            "unresolved_validation_count": 0,
        },
    }


def load_memory(path: str | Path) -> dict[str, Any]:
    payload = load_json(path, None)
    if not isinstance(payload, dict):
        return empty_memory()
    memory = empty_memory()
    memory.update(payload)
    memory["scope_note"] = SCOPE_NOTE
    for field in ("learned_reports", "papers", "research_ideas"):
        if not isinstance(memory.get(field), list):
            memory[field] = []
    default_preferences = empty_memory()["explicit_preferences"]
    if not isinstance(memory.get("explicit_preferences"), dict):
        memory["explicit_preferences"] = default_preferences
    else:
        memory["explicit_preferences"] = {
            key: memory["explicit_preferences"].get(key, default)
            for key, default in default_preferences.items()
        }
    return memory


def article_text(article: dict[str, Any]) -> str:
    inspiration = article.get("research_inspiration") or {}
    parts: list[Any] = [
        article.get("title"),
        article.get("chinese_title"),
        article.get("why_worth_reading"),
        *(article.get("tags") or []),
        *(article.get("core_findings") or []),
        *(article.get("strong_recommendation_reasons") or []),
    ]
    if isinstance(inspiration, dict):
        for values in inspiration.values():
            if isinstance(values, list):
                parts.extend(values)
            else:
                parts.append(values)
    return " ".join(clean_text(value) for value in parts if value).casefold()


def infer_roadmap_stages(article: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    text = article_text(article)
    return [
        group["label"]
        for group in named_term_groups(profile, "roadmap_stages")
        if any(keyword.casefold() in text for keyword in group["terms"])
    ]


def extract_key_terms(article: dict[str, Any]) -> list[str]:
    terms = []
    for item in article.get("term_explanations") or []:
        if isinstance(item, dict):
            terms.append(item.get("term"))
    return unique_strings(terms)


def report_id(payload: dict[str, Any]) -> str:
    identities = sorted(paper_key(article) for article in payload.get("articles") or [])
    stable = json.dumps(
        {"date": clean_text(payload.get("date")), "papers": identities},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]


def compact_paper(
    article: dict[str, Any], *, date: str, current_report_id: str, profile: dict[str, Any]
) -> dict[str, Any]:
    identity_key = paper_key(article)
    return {
        "identity_key": identity_key,
        "doi": normalize_doi(article.get("doi")),
        "title": clean_text(article.get("title")),
        "chinese_title": clean_text(article.get("chinese_title")),
        "publication_date": clean_text(article.get("publication_date")),
        "first_report_date": date,
        "last_report_date": date,
        "report_ids": [current_report_id],
        "recommendation_score": int(article.get("recommendation_score") or 0),
        "tags": unique_strings(article.get("tags") or []),
        "key_terms": extract_key_terms(article),
        "strong_recommendation": bool(article.get("strong_recommendation")),
        "why_worth_reading": clean_text(article.get("why_worth_reading")),
        "roadmap_stages": infer_roadmap_stages(article, profile),
        "needs_verification": unique_strings(article.get("needs_verification") or []),
        "source": "evidence_reviewed_report",
    }


def merge_compact_paper(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for field in (
        "doi", "title", "chinese_title", "publication_date", "recommendation_score",
        "strong_recommendation", "why_worth_reading", "source",
    ):
        if new.get(field) not in (None, "", [], {}):
            merged[field] = new[field]
    dates = [
        value for value in (existing.get("first_report_date"), new.get("first_report_date")) if value
    ]
    merged["first_report_date"] = min(dates) if dates else ""
    dates = [
        value for value in (existing.get("last_report_date"), new.get("last_report_date")) if value
    ]
    merged["last_report_date"] = max(dates) if dates else ""
    for field in ("report_ids", "tags", "key_terms", "roadmap_stages", "needs_verification"):
        merged[field] = unique_strings((existing.get(field) or []) + (new.get(field) or []))
    return merged


def recompute_signals(memory: dict[str, Any]) -> None:
    tag_counts: Counter[str] = Counter()
    term_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    strong_count = 0
    unresolved_count = 0
    for paper in memory.get("papers") or []:
        tag_counts.update(paper.get("tags") or [])
        term_counts.update(paper.get("key_terms") or [])
        stage_counts.update(paper.get("roadmap_stages") or [])
        strong_count += int(bool(paper.get("strong_recommendation")))
        unresolved_count += len(paper.get("needs_verification") or [])
    memory["signals"] = {
        "tag_counts": dict(tag_counts.most_common()),
        "key_term_counts": dict(term_counts.most_common()),
        "roadmap_stage_counts": dict(stage_counts.most_common()),
        "strong_recommendation_count": strong_count,
        "unresolved_validation_count": unresolved_count,
    }


def learn_report(
    payload: dict[str, Any], memory: dict[str, Any], *, delivery: str, profile: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int | bool]]:
    articles = [item for item in payload.get("articles") or [] if isinstance(item, dict)]
    date = clean_text(payload.get("date"))
    current_report_id = report_id(payload)
    reports = memory.get("learned_reports") or []
    already_learned = any(item.get("report_id") == current_report_id for item in reports)

    paper_map = {
        item.get("identity_key"): item
        for item in memory.get("papers") or []
        if isinstance(item, dict) and item.get("identity_key")
    }
    new_papers = 0
    for article in articles:
        compact = compact_paper(
            article,
            date=date,
            current_report_id=current_report_id,
            profile=profile,
        )
        identity = compact["identity_key"]
        if identity in paper_map:
            paper_map[identity] = merge_compact_paper(paper_map[identity], compact)
        else:
            paper_map[identity] = compact
            new_papers += 1
    memory["papers"] = sorted(
        paper_map.values(),
        key=lambda item: (
            item.get("last_report_date") or "",
            int(item.get("recommendation_score") or 0),
            item.get("title") or "",
        ),
        reverse=True,
    )

    if not already_learned:
        reports.append(
            {
                "report_id": current_report_id,
                "date": date,
                "learned_at": utc_now_iso(),
                "delivery": delivery,
                "article_count": len(articles),
                "dois": unique_strings(normalize_doi(item.get("doi")) for item in articles),
            }
        )
        memory["learned_reports"] = sorted(
            reports, key=lambda item: (item.get("date") or "", item.get("report_id") or "")
        )

        ideas = memory.get("research_ideas") or []
        known_ideas = {
            (item.get("date"), clean_text(item.get("text")).casefold())
            for item in ideas
            if isinstance(item, dict)
        }
        for idea in payload.get("research_ideas") or []:
            text = clean_text(idea)
            marker = (date, text.casefold())
            if text and marker not in known_ideas:
                ideas.append({"date": date, "text": text, "report_id": current_report_id})
                known_ideas.add(marker)
        memory["research_ideas"] = sorted(
            ideas, key=lambda item: (item.get("date") or "", item.get("report_id") or "")
        )

    memory["version"] = 1
    memory["scope_note"] = SCOPE_NOTE
    memory["updated_at"] = utc_now_iso()
    recompute_signals(memory)
    return memory, {
        "report_added": not already_learned,
        "new_papers": new_papers,
        "total_reports": len(memory.get("learned_reports") or []),
        "total_papers": len(memory.get("papers") or []),
    }


def build_context(memory: dict[str, Any], *, recent: int = 10) -> dict[str, Any]:
    signals = memory.get("signals") or {}
    papers = sorted(
        memory.get("papers") or [],
        key=lambda item: (
            item.get("last_report_date") or "",
            int(item.get("recommendation_score") or 0),
        ),
        reverse=True,
    )
    ideas = sorted(
        memory.get("research_ideas") or [],
        key=lambda item: item.get("date") or "",
        reverse=True,
    )
    return {
        "scope_note": memory.get("scope_note") or SCOPE_NOTE,
        "learned_report_count": len(memory.get("learned_reports") or []),
        "learned_paper_count": len(memory.get("papers") or []),
        "strong_recommendation_count": int(signals.get("strong_recommendation_count") or 0),
        "unresolved_validation_count": int(signals.get("unresolved_validation_count") or 0),
        "top_tags": list((signals.get("tag_counts") or {}).items())[:12],
        "roadmap_stage_counts": signals.get("roadmap_stage_counts") or {},
        "recent_high_value_papers": [
            {
                "doi": item.get("doi") or "",
                "title": item.get("title") or "",
                "score": int(item.get("recommendation_score") or 0),
                "date": item.get("last_report_date") or "",
                "roadmap_stages": item.get("roadmap_stages") or [],
                "why_worth_reading": item.get("why_worth_reading") or "",
                "needs_verification": item.get("needs_verification") or [],
            }
            for item in papers[:recent]
        ],
        "recent_research_ideas": ideas[:recent],
        "use_guidance": (
            "用于发现连续证据、研究空白和主题饱和；不得据此降低70分阈值、重复推荐已推送DOI，"
            "也不得把自动累计频次当作用户明确偏好。"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = ChineseArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    learn = subparsers.add_parser("learn", help="从一份已经交付且经过证据复核的报告中学习")
    learn.add_argument("--input", required=True, help="已复核报告 JSON")
    learn.add_argument("--memory", default=str(DEFAULT_MEMORY))
    learn.add_argument("--profile", default=str(DEFAULT_PROFILE))
    learn.add_argument("--delivery", default="local-report")

    context = subparsers.add_parser("context", help="输出供下一次复核使用的精简上下文")
    context.add_argument("--memory", default=str(DEFAULT_MEMORY))
    context.add_argument("--recent", type=int, default=10)
    context.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "learn":
        payload = load_json(args.input, None)
        if not isinstance(payload, dict):
            raise SystemExit(f"已复核 JSON 不存在或格式无效：{args.input}")
        memory = load_memory(args.memory)
        profile = load_profile(args.profile, require_configured=False)
        memory, result = learn_report(
            payload,
            memory,
            delivery=args.delivery,
            profile=profile,
        )
        atomic_write_json(args.memory, memory)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.recent < 1:
        raise SystemExit("--recent 必须至少为1")
    context = build_context(load_memory(args.memory), recent=args.recent)
    if args.output:
        atomic_write_json(args.output, context)
        print(f"研究记忆上下文已生成：{args.output}")
    else:
        print(json.dumps(context, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
