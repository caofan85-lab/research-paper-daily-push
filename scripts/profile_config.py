#!/usr/bin/env python3
"""读取并验证由用户维护的研究配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import clean_text, load_json, unique_strings

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_PROFILE = SKILL_DIR / "config" / "research_profile.json"
LOCAL_PROFILE = SKILL_DIR / "config" / "research_profile.local.json"
DEFAULT_PROFILE = LOCAL_PROFILE if LOCAL_PROFILE.exists() else TEMPLATE_PROFILE


class ProfileError(ValueError):
    """研究配置不足以安全执行任务时抛出。"""


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def load_profile(path: str | Path = DEFAULT_PROFILE, *, require_configured: bool = True) -> dict[str, Any]:
    profile = load_json(path, None)
    if not isinstance(profile, dict):
        raise ProfileError(f"研究配置不存在或格式无效：{path}")
    if require_configured and not profile.get("configured"):
        raise ProfileError(
            "尚未配置研究主题。请从 user_papers 生成研究画像，或填写本地研究配置；"
            "确认后再将 configured 设为 true。"
        )

    profile.setdefault("profile_name", "")
    profile.setdefault("research_context", "")
    profile.setdefault("target_system", "")
    profile.setdefault("priority_questions", [])
    profile.setdefault("queries", [])
    profile.setdefault("modes", {})
    profile.setdefault("topic_groups", [])
    profile.setdefault("cross_topic_bonuses", [])
    profile.setdefault("method_groups", [])
    profile.setdefault("quality_tiers", {})
    profile.setdefault("exclusion_terms", [])
    profile.setdefault("mechanistic_terms", [])
    profile.setdefault("strong_recommendation_rules", [])
    profile.setdefault("roadmap_stages", [])
    profile.setdefault("tags", [])

    if require_configured:
        if not clean_text(profile.get("profile_name")):
            raise ProfileError("configured=true 时必须填写 profile_name")
        if not profile_queries(profile, "all"):
            raise ProfileError("至少需要配置一条默认查询语句")
        groups = topic_groups(profile)
        if not groups:
            raise ProfileError("至少需要配置一个有效的 topic_group")
    return profile


def profile_queries(profile: dict[str, Any], mode: str) -> list[str]:
    if mode == "all":
        queries = list(profile.get("queries") or [])
        configured_mode = (profile.get("modes") or {}).get("all", {})
        if isinstance(configured_mode, dict):
            queries.extend(configured_mode.get("queries") or [])
        elif isinstance(configured_mode, list):
            queries.extend(configured_mode)
        return unique_strings(queries)

    configured_mode = (profile.get("modes") or {}).get(mode)
    if configured_mode is None:
        available = ", ".join(sorted((profile.get("modes") or {}).keys())) or "无"
        raise ProfileError(f"未知的研究配置模式“{mode}”。可用聚焦模式：{available}")
    queries = configured_mode.get("queries") if isinstance(configured_mode, dict) else configured_mode
    return unique_strings(queries or [])


def topic_groups(profile: dict[str, Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in _list_of_dicts(profile.get("topic_groups")):
        label = clean_text(item.get("label"))
        terms = unique_strings(item.get("terms") or [])
        try:
            weight = int(item.get("weight") or 0)
        except (TypeError, ValueError):
            continue
        if label and terms and 1 <= weight <= 100:
            groups.append({"label": label, "weight": weight, "terms": terms})
    return groups


def profile_terms(profile: dict[str, Any]) -> list[str]:
    return unique_strings(
        term
        for group in topic_groups(profile)
        for term in group.get("terms") or []
    )


def named_term_groups(profile: dict[str, Any], field: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in _list_of_dicts(profile.get(field)):
        label = clean_text(item.get("label"))
        terms = unique_strings(item.get("terms") or item.get("keywords") or [])
        if label and terms:
            groups.append({"label": label, "terms": terms})
    return groups
