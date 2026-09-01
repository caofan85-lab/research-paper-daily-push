#!/usr/bin/env python3
"""科研文献雷达共用的零依赖辅助函数。"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import tempfile
import time
import sys
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "research-paper-daily-push/1.0 (literature metadata client)"


class ChineseArgumentParser(argparse.ArgumentParser):
    """使用中文标题、帮助说明和错误前缀的命令行参数解析器。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "位置参数"
        self._optionals.title = "选项"
        self.add_argument(
            "-h",
            "--help",
            action="help",
            default=argparse.SUPPRESS,
            help="显示此帮助信息并退出",
        )

    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "用法：", 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "用法：", 1)

    def error(self, message: str) -> None:
        translations = {
            "the following arguments are required:": "缺少必填参数：",
            "unrecognized arguments:": "无法识别的参数：",
            "expected one argument": "需要一个参数值",
        }
        for source, target in translations.items():
            message = message.replace(source, target)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}：错误：{message}\n")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def normalize_doi(value: Any) -> str:
    if not value:
        return ""
    doi = str(value).strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.rstrip(" .;,)")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(value: Any) -> str:
    text = clean_text(value).casefold()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
    return text


def paper_key(paper: dict[str, Any]) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"
    title = normalize_title(paper.get("title"))
    if title:
        return f"title:{hashlib.sha256(title.encode('utf-8')).hexdigest()[:24]}"
    source_ids = paper.get("source_ids") or {}
    stable = json.dumps(source_ids, ensure_ascii=False, sort_keys=True)
    return f"source:{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:24]}"


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def parse_date(value: Any) -> str:
    """尽可能返回 YYYY-MM-DD，无法解析时返回空字符串。"""
    if not value:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    match = re.search(r"(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?", text)
    if match:
        year, month, day = match.groups()
        try:
            return date(int(year), int(month), int(day or 1)).isoformat()
        except ValueError:
            return ""
    if re.fullmatch(r"\d{4}", text):
        return f"{text}-01-01"
    return ""


def date_from_parts(parts: Any) -> str:
    try:
        values = list(parts[0]["date-parts"] if isinstance(parts, list) else parts["date-parts"])
        values = list(values[0]) if values and isinstance(values[0], list) else values
        year = int(values[0])
        month = int(values[1]) if len(values) > 1 else 1
        day = int(values[2]) if len(values) > 2 else 1
        return date(year, month, day).isoformat()
    except (KeyError, IndexError, TypeError, ValueError):
        return ""


def json_request(
    url: str,
    *,
    method: str = "GET",
    payload: Any = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> Any:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, data=data, headers=request_headers, method=method)
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt + 1 >= retries:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = min(float(retry_after), 10.0) if retry_after and retry_after.isdigit() else 2**attempt
            time.sleep(delay)
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 >= retries:
                raise
            time.sleep(2**attempt)
    if last_error:
        raise last_error
    raise RuntimeError("HTTP 请求失败，但没有捕获到具体异常")


def form_request(
    url: str,
    fields: dict[str, str],
    *,
    timeout: int = 30,
    retries: int = 2,
) -> Any:
    from urllib.parse import urlencode

    encoded = urlencode(fields).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": USER_AGENT,
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, data=encoded, headers=headers, method="POST")
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 >= retries:
                raise
            time.sleep(2**attempt)
    if last_error:
        raise last_error
    raise RuntimeError("表单请求失败，但没有捕获到具体异常")


def extract_papers(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("papers", "new", "recommendations", "articles"):
        items = payload.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean_text(value)
        marker = text.casefold()
        if text and marker not in seen:
            seen.add(marker)
            result.append(text)
    return result


def merge_papers(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for field in ("doi", "title", "journal", "publication_date", "url", "article_type"):
        merged[field] = first_nonempty(left.get(field), right.get(field))
    left_abstract = clean_text(left.get("abstract"))
    right_abstract = clean_text(right.get("abstract"))
    merged["abstract"] = right_abstract if len(right_abstract) > len(left_abstract) else left_abstract
    merged["authors"] = unique_strings((left.get("authors") or []) + (right.get("authors") or []))
    merged["sources"] = unique_strings((left.get("sources") or []) + (right.get("sources") or []))
    source_ids = dict(left.get("source_ids") or {})
    source_ids.update(right.get("source_ids") or {})
    merged["source_ids"] = source_ids
    merged["citation_count"] = max(int(left.get("citation_count") or 0), int(right.get("citation_count") or 0))
    merged["is_open_access"] = bool(left.get("is_open_access") or right.get("is_open_access"))
    merged["is_preprint"] = bool(left.get("is_preprint") or right.get("is_preprint"))
    merged["needs_verification"] = unique_strings(
        (left.get("needs_verification") or []) + (right.get("needs_verification") or [])
    )
    return merged


def deduplicate_papers(papers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    title_to_key: dict[str, str] = {}
    for paper in papers:
        candidate = dict(paper)
        candidate["doi"] = normalize_doi(candidate.get("doi"))
        candidate["title"] = clean_text(candidate.get("title"))
        candidate["abstract"] = clean_text(candidate.get("abstract"))
        key = paper_key(candidate)
        normalized_title = normalize_title(candidate.get("title"))
        existing_key = key if key in by_key else title_to_key.get(normalized_title, "")
        if existing_key:
            by_key[existing_key] = merge_papers(by_key[existing_key], candidate)
        else:
            by_key[key] = candidate
            if normalized_title:
                title_to_key[normalized_title] = key
    return list(by_key.values())
