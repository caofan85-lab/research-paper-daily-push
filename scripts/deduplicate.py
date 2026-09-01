#!/usr/bin/env python3
"""Filter or commit article history using DOI-first, title-fallback identity."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from common import (
    atomic_write_json,
    clean_text,
    extract_papers,
    load_json,
    normalize_doi,
    normalize_title,
    paper_key,
    utc_now_iso,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_HISTORY = SCRIPT_DIR.parent / "data" / "pushed_articles.json"


def load_history(path: str | Path) -> list[dict[str, Any]]:
    payload = load_json(path, [])
    if isinstance(payload, dict):
        payload = payload.get("articles", [])
    if not isinstance(payload, list):
        raise TypeError("History must be a JSON array or an object containing an articles array")
    return [item for item in payload if isinstance(item, dict)]


def build_indexes(history: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_doi: dict[str, dict[str, Any]] = {}
    by_title: dict[str, dict[str, Any]] = {}
    for item in history:
        doi = normalize_doi(item.get("doi"))
        title = normalize_title(item.get("title"))
        if doi:
            by_doi[doi] = item
        if title:
            by_title[title] = item
    return by_doi, by_title


def meaningful_update(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for field in ("publication_date", "journal", "article_type"):
        before = clean_text(old.get(field)).casefold()
        after = clean_text(new.get(field)).casefold()
        if before and after and before != after:
            changed.append(field)
    if not old.get("doi") and new.get("doi"):
        changed.append("doi")
    if old.get("is_preprint") and not new.get("is_preprint"):
        changed.append("formal_publication")
    return changed


def filter_history(papers: list[dict[str, Any]], history: list[dict[str, Any]]) -> dict[str, Any]:
    by_doi, by_title = build_indexes(history)
    new_items: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for paper in papers:
        doi = normalize_doi(paper.get("doi"))
        title = normalize_title(paper.get("title"))
        previous = by_doi.get(doi) if doi else None
        previous = previous or (by_title.get(title) if title else None)
        item = dict(paper)
        if previous is None:
            item["history_status"] = "new"
            new_items.append(item)
            continue
        changes = meaningful_update(previous, item)
        if changes:
            item["history_status"] = "update"
            item["updated_fields"] = changes
            item["previous_record"] = {
                "doi": previous.get("doi", ""),
                "publication_date": previous.get("publication_date", ""),
                "pushed_date": previous.get("pushed_date", ""),
            }
            updates.append(item)
        else:
            item["history_status"] = "duplicate"
            item["previous_pushed_date"] = previous.get("pushed_date", "")
            duplicates.append(item)
    return {
        "generated_at": utc_now_iso(),
        "history_count": len(history),
        "input_count": len(papers),
        "new_count": len(new_items),
        "update_count": len(updates),
        "duplicate_count": len(duplicates),
        "new": new_items,
        "updates": updates,
        "duplicates": duplicates,
    }


def commit_history(
    papers: list[dict[str, Any]],
    history: list[dict[str, Any]],
    *,
    delivery: str,
    pushed_date: str,
) -> tuple[list[dict[str, Any]], int]:
    by_doi, by_title = build_indexes(history)
    committed = 0
    for paper in papers:
        doi = normalize_doi(paper.get("doi"))
        title_key = normalize_title(paper.get("title"))
        if (doi and doi in by_doi) or (title_key and title_key in by_title):
            continue
        record = {
            "doi": doi,
            "title": clean_text(paper.get("title")),
            "publication_date": clean_text(paper.get("publication_date")),
            "pushed_date": pushed_date,
            "relevance_score": int((paper.get("component_scores") or {}).get("relevance") or 0),
            "recommendation_score": int(paper.get("recommendation_score") or 0),
            "journal": clean_text(paper.get("journal")),
            "article_type": clean_text(paper.get("article_type")),
            "is_preprint": bool(paper.get("is_preprint")),
            "delivery": delivery,
            "identity_key": paper_key(paper),
        }
        history.append(record)
        if doi:
            by_doi[doi] = record
        if title_key:
            by_title[title_key] = record
        committed += 1
    history.sort(key=lambda item: (item.get("pushed_date", ""), item.get("title", "")))
    return history, committed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    filter_parser = subparsers.add_parser("filter", help="Separate new, updated, and duplicate papers")
    filter_parser.add_argument("--input", required=True)
    filter_parser.add_argument("--output", required=True)
    filter_parser.add_argument("--history", default=str(DEFAULT_HISTORY))

    commit_parser = subparsers.add_parser("commit", help="Atomically append successfully delivered papers")
    commit_parser.add_argument("--input", required=True)
    commit_parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    commit_parser.add_argument("--delivery", choices=("wxpusher", "serverchan", "wecom", "local-report"), required=True)
    commit_parser.add_argument("--pushed-date", help="YYYY-MM-DD; defaults to local date")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    history = load_history(args.history)
    papers = extract_papers(load_json(args.input, {}))
    if args.command == "filter":
        result = filter_history(papers, history)
        atomic_write_json(args.output, result)
        print(
            f"History filter: {result['new_count']} new, {result['update_count']} updates, "
            f"{result['duplicate_count']} duplicates."
        )
        return 0

    pushed_date = args.pushed_date or datetime.now().astimezone().date().isoformat()
    updated, committed = commit_history(
        papers, history, delivery=args.delivery, pushed_date=pushed_date
    )
    atomic_write_json(args.history, updated)
    print(f"Committed {committed} article(s) to history via {args.delivery}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
