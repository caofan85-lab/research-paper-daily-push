#!/usr/bin/env python3
"""从稳定的公开学术接口检索近期论文并规范化元数据。"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from common import (
    ChineseArgumentParser,
    atomic_write_json,
    clean_text,
    date_from_parts,
    deduplicate_papers,
    first_nonempty,
    json_request,
    normalize_doi,
    parse_date,
    unique_strings,
    utc_now_iso,
)
from profile_config import DEFAULT_PROFILE, ProfileError, load_profile, profile_queries, profile_terms

API_SOURCES = ("europepmc", "crossref", "semanticscholar", "openalex", "biorxiv")

OPENALEX_SELECT_FIELDS = (
    "id",
    "doi",
    "display_name",
    "authorships",
    "primary_location",
    "publication_date",
    "type",
    "abstract_inverted_index",
    "cited_by_count",
    "open_access",
    "best_oa_location",
    "is_retracted",
)


def compact_query(query: str) -> str:
    """为不支持布尔语法的接口生成普通查询文本。"""
    text = re.sub(r"\b(?:AND|OR|NOT)\b", " ", query, flags=re.IGNORECASE)
    text = text.replace("(", " ").replace(")", " ").replace('"', "")
    return re.sub(r"\s+", " ", text).strip()


def plausible_relevance(paper: dict[str, Any], terms: list[str]) -> bool:
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".casefold()
    return any(term.casefold() in text for term in terms)


def _epmc_type(record: dict[str, Any]) -> str:
    values = record.get("pubTypeList", {}).get("pubType", [])
    if isinstance(values, str):
        return values
    return "; ".join(clean_text(value) for value in values if value)


def search_europepmc(queries: list[str], start: date, end: date) -> list[dict[str, Any]]:
    combined = " OR ".join(f"({query})" for query in queries)
    epmc_query = f"({combined}) AND FIRST_PDATE:[{start.isoformat()} TO {end.isoformat()}] sort_date:y"
    params = urlencode(
        {
            "query": epmc_query,
            "format": "json",
            "resultType": "core",
            "pageSize": 500,
            "synonym": "false",
        }
    )
    payload = json_request(f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}")
    output: list[dict[str, Any]] = []
    for item in payload.get("resultList", {}).get("result", []):
        doi = normalize_doi(item.get("doi"))
        pmid = clean_text(item.get("pmid"))
        pmcid = clean_text(item.get("pmcid"))
        url = f"https://doi.org/{doi}" if doi else (
            f"https://europepmc.org/article/MED/{pmid}" if pmid else f"https://europepmc.org/article/PMC/{pmcid}"
        )
        output.append(
            {
                "doi": doi,
                "title": clean_text(item.get("title")),
                "authors": unique_strings((item.get("authorString") or "").split(",")),
                "journal": clean_text(first_nonempty(item.get("journalTitle"), item.get("journalInfo", {}).get("journal", {}).get("title"))),
                "publication_date": parse_date(first_nonempty(item.get("firstPublicationDate"), item.get("electronicPublicationDate"), item.get("journalInfo", {}).get("printPublicationDate"))),
                "url": url,
                "article_type": _epmc_type(item),
                "abstract": clean_text(item.get("abstractText")),
                "sources": ["Europe PMC"],
                "source_ids": {key: value for key, value in {"pmid": pmid, "pmcid": pmcid}.items() if value},
                "citation_count": int(item.get("citedByCount") or 0),
                "is_open_access": str(item.get("isOpenAccess", "")).upper() == "Y",
                "is_preprint": "preprint" in _epmc_type(item).casefold(),
                "needs_verification": [] if item.get("abstractText") else ["摘要缺失，核心结论需从原文核实"],
            }
        )
    return output


def _crossref_date(item: dict[str, Any]) -> str:
    for key in ("published-online", "published", "issued", "published-print", "created"):
        value = item.get(key)
        if key == "created" and isinstance(value, dict) and value.get("date-time"):
            parsed = parse_date(value.get("date-time"))
        else:
            parsed = date_from_parts(value) if value else ""
        if parsed:
            return parsed
    return ""


def search_crossref(queries: list[str], start: date, end: date) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    mailto = os.environ.get("CROSSREF_MAILTO", "").strip()
    for index, query in enumerate(queries):
        params: dict[str, Any] = {
            "query.bibliographic": compact_query(query),
            "filter": f"from-pub-date:{start.isoformat()},until-pub-date:{end.isoformat()},type:journal-article",
            "rows": 100,
            "sort": "published",
            "order": "desc",
        }
        if mailto:
            params["mailto"] = mailto
        payload = json_request(f"https://api.crossref.org/works?{urlencode(params)}")
        for item in payload.get("message", {}).get("items", []):
            authors = []
            for author in item.get("author", []):
                name = " ".join(filter(None, [clean_text(author.get("given")), clean_text(author.get("family"))]))
                if name:
                    authors.append(name)
            doi = normalize_doi(item.get("DOI"))
            output.append(
                {
                    "doi": doi,
                    "title": clean_text(first_nonempty(*(item.get("title") or []))),
                    "authors": unique_strings(authors),
                    "journal": clean_text(first_nonempty(*(item.get("container-title") or []))),
                    "publication_date": _crossref_date(item),
                    "url": clean_text(first_nonempty(item.get("URL"), f"https://doi.org/{doi}" if doi else "")),
                    "article_type": clean_text(item.get("type")),
                    "abstract": clean_text(item.get("abstract")),
                    "sources": ["Crossref"],
                    "source_ids": {},
                    "citation_count": int(item.get("is-referenced-by-count") or 0),
                    "is_open_access": bool(item.get("license")),
                    "is_preprint": item.get("type") == "posted-content",
                    "needs_verification": [] if item.get("abstract") else ["Crossref 未提供摘要，结论需从原文核实"],
                }
            )
        if index + 1 < len(queries):
            time.sleep(0.15)
    return output


def search_semantic_scholar(queries: list[str], start: date, end: date) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    headers: dict[str, str] = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    fields = "title,abstract,authors,venue,publicationDate,url,externalIds,publicationTypes,citationCount,openAccessPdf,journal"
    for index, query in enumerate(queries):
        params = urlencode(
            {
                "query": compact_query(query),
                "limit": 100,
                "fields": fields,
                "year": f"{start.year}-{end.year}",
            }
        )
        payload = json_request(
            f"https://api.semanticscholar.org/graph/v1/paper/search?{params}", headers=headers
        )
        for item in payload.get("data", []):
            published = parse_date(item.get("publicationDate"))
            if not published or not (start.isoformat() <= published <= end.isoformat()):
                continue
            external = item.get("externalIds") or {}
            doi = normalize_doi(external.get("DOI"))
            journal = item.get("journal") or {}
            types = item.get("publicationTypes") or []
            output.append(
                {
                    "doi": doi,
                    "title": clean_text(item.get("title")),
                    "authors": unique_strings(author.get("name") for author in item.get("authors", [])),
                    "journal": clean_text(first_nonempty(journal.get("name"), item.get("venue"))),
                    "publication_date": published,
                    "url": clean_text(first_nonempty(item.get("url"), f"https://doi.org/{doi}" if doi else "")),
                    "article_type": "; ".join(clean_text(value) for value in types),
                    "abstract": clean_text(item.get("abstract")),
                    "sources": ["Semantic Scholar"],
                    "source_ids": {"semantic_scholar": clean_text(item.get("paperId"))},
                    "citation_count": int(item.get("citationCount") or 0),
                    "is_open_access": bool(item.get("openAccessPdf")),
                    "is_preprint": any("preprint" in str(value).casefold() for value in types),
                    "needs_verification": [] if item.get("abstract") else ["Semantic Scholar 未提供摘要，结论需从原文核实"],
                }
            )
        if index + 1 < len(queries):
            time.sleep(0.8 if not api_key else 0.15)
    return output


def reconstruct_openalex_abstract(index: Any) -> str:
    """把 OpenAlex 的单词位置倒排索引还原为可读摘要。"""
    if not isinstance(index, dict):
        return ""
    positioned_words: list[tuple[int, str]] = []
    for word, positions in index.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int) and position >= 0:
                positioned_words.append((position, clean_text(word)))
    positioned_words.sort(key=lambda item: item[0])
    return clean_text(" ".join(word for _, word in positioned_words if word))


def search_openalex(queries: list[str], start: date, end: date) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    headers: dict[str, str] = {}
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for index, query in enumerate(queries):
        params = urlencode(
            {
                "search": query,
                "filter": (
                    f"from_publication_date:{start.isoformat()},"
                    f"to_publication_date:{end.isoformat()}"
                ),
                "sort": "publication_date:desc",
                "per_page": 100,
                "select": ",".join(OPENALEX_SELECT_FIELDS),
            }
        )
        payload = json_request(
            f"https://api.openalex.org/works?{params}", headers=headers
        )
        for item in payload.get("results") or []:
            doi = normalize_doi(item.get("doi"))
            openalex_url = clean_text(item.get("id"))
            openalex_id = openalex_url.rsplit("/", 1)[-1] if openalex_url else ""
            primary_location = item.get("primary_location") or {}
            best_oa_location = item.get("best_oa_location") or {}
            source = primary_location.get("source") or {}
            abstract = reconstruct_openalex_abstract(item.get("abstract_inverted_index"))
            work_type = clean_text(item.get("type"))
            article_type = f"retraction; {work_type}" if item.get("is_retracted") else work_type
            landing_page = clean_text(
                first_nonempty(
                    best_oa_location.get("landing_page_url"),
                    primary_location.get("landing_page_url"),
                    openalex_url,
                )
            )
            output.append(
                {
                    "doi": doi,
                    "title": clean_text(item.get("display_name")),
                    "authors": unique_strings(
                        (authorship.get("author") or {}).get("display_name")
                        for authorship in item.get("authorships") or []
                        if isinstance(authorship, dict)
                    ),
                    "journal": clean_text(
                        first_nonempty(
                            source.get("display_name"),
                            primary_location.get("raw_source_name"),
                        )
                    ),
                    "publication_date": parse_date(item.get("publication_date")),
                    "url": f"https://doi.org/{doi}" if doi else landing_page,
                    "article_type": article_type,
                    "abstract": abstract,
                    "sources": ["OpenAlex"],
                    "source_ids": {"openalex": openalex_id} if openalex_id else {},
                    "citation_count": int(item.get("cited_by_count") or 0),
                    "is_open_access": bool((item.get("open_access") or {}).get("is_oa")),
                    "is_preprint": work_type.casefold() == "preprint",
                    "needs_verification": (
                        [] if abstract else ["OpenAlex 未提供摘要，结论需从原文核实"]
                    ),
                }
            )
        if index + 1 < len(queries):
            time.sleep(0.15)
    return output


def search_biorxiv(_queries: list[str], start: date, end: date) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    cursor = 0
    maximum = 600
    while cursor < maximum:
        url = (
            "https://api.biorxiv.org/details/biorxiv/"
            f"{start.isoformat()}/{end.isoformat()}/{cursor}/json"
        )
        payload = json_request(url)
        collection = payload.get("collection", [])
        if not collection:
            break
        for item in collection:
            doi = normalize_doi(item.get("doi"))
            published_doi = normalize_doi(item.get("published"))
            output.append(
                {
                    "doi": doi,
                    "title": clean_text(item.get("title")),
                    "authors": unique_strings((item.get("authors") or "").split(";")),
                    "journal": "bioRxiv",
                    "publication_date": parse_date(item.get("date")),
                    "url": f"https://doi.org/{doi}" if doi else "",
                    "article_type": clean_text(first_nonempty(item.get("type"), "preprint")),
                    "abstract": clean_text(item.get("abstract")),
                    "sources": ["bioRxiv"],
                    "source_ids": {"biorxiv_version": clean_text(item.get("version"))},
                    "citation_count": 0,
                    "is_open_access": True,
                    "is_preprint": True,
                    "formally_published_doi": published_doi,
                    "needs_verification": ["预印本，尚未完成正式同行评议"],
                }
            )
        cursor += len(collection)
        messages = payload.get("messages") or []
        total = int(messages[0].get("total") or cursor) if messages else cursor
        if cursor >= total:
            break
    return output


SOURCE_FUNCTIONS: dict[str, Callable[[list[str], date, date], list[dict[str, Any]]]] = {
    "europepmc": search_europepmc,
    "crossref": search_crossref,
    "semanticscholar": search_semantic_scholar,
    "openalex": search_openalex,
    "biorxiv": search_biorxiv,
}


def collect(
    *,
    queries: list[str],
    start: date,
    end: date,
    sources: list[str],
    relevance_terms: list[str],
) -> dict[str, Any]:
    papers: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    errors: list[dict[str, str]] = []
    for source in sources:
        try:
            found = SOURCE_FUNCTIONS[source](queries, start, end)
            counts[source] = len(found)
            papers.extend(found)
        # 各来源可能出现不同的解析或传输异常；逐个隔离，避免单一来源故障清空其他有效结果。
        except Exception as exc:  # noqa: BLE001
            counts[source] = 0
            errors.append({"source": source, "error": f"{type(exc).__name__}: {exc}"})
    retrieved_count = len(papers)
    merged = [
        paper for paper in deduplicate_papers(papers)
        if plausible_relevance(paper, relevance_terms)
    ]
    merged.sort(key=lambda item: (item.get("publication_date", ""), item.get("title", "")), reverse=True)
    return {
        "generated_at": utc_now_iso(),
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "date_precision_note": "部分来源仅提供日级出版日期；默认 1 天窗口是最近 24 小时的近似实现。",
        "queries": queries,
        "sources_requested": sources,
        "source_counts": counts,
        "retrieved_count": retrieved_count,
        "unique_relevant_count": len(merged),
        "errors": errors,
        "papers": merged,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = ChineseArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1, choices=range(1, 31), metavar="1-30")
    parser.add_argument("--from-date", help="起始日期 YYYY-MM-DD；设置后覆盖 --days")
    parser.add_argument("--to-date", help="结束日期 YYYY-MM-DD；默认为本地日期的今天")
    parser.add_argument("--mode", default="all", help="研究配置中定义的模式名称")
    parser.add_argument("--query", action="append", help="自定义查询语句；可以重复传入")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--sources", default=",".join(API_SOURCES), help="以英文逗号分隔的来源标识")
    parser.add_argument("--output", required=True, help="输出 JSON 路径")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        profile = load_profile(args.profile)
        queries = unique_strings(args.query or profile_queries(profile, args.mode))
        relevance_terms = profile_terms(profile)
    except ProfileError as exc:
        raise SystemExit(str(exc)) from exc
    if not queries:
        raise SystemExit(f"模式“{args.mode}”没有配置查询语句")
    end = date.fromisoformat(args.to_date) if args.to_date else datetime.now().astimezone().date()
    start = date.fromisoformat(args.from_date) if args.from_date else end - timedelta(days=args.days - 1)
    if start > end:
        raise SystemExit("--from-date 不能晚于 --to-date")
    sources = [value.strip().casefold() for value in args.sources.split(",") if value.strip()]
    unknown = [source for source in sources if source not in SOURCE_FUNCTIONS]
    if unknown:
        raise SystemExit(f"未知的文献来源：{', '.join(unknown)}")
    result = collect(
        queries=queries,
        start=start,
        end=end,
        sources=sources,
        relevance_terms=relevance_terms,
    )
    result["mode"] = args.mode
    result["profile_name"] = clean_text(profile.get("profile_name"))
    atomic_write_json(args.output, result)
    print(
        f"共检索 {result['retrieved_count']} 条记录；去重并进行相关性预筛后保留 "
        f"{result['unique_relevant_count']} 篇论文。"
    )
    if result["errors"]:
        print(f"警告：{len(result['errors'])} 个来源检索失败；详情见输出 JSON。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
