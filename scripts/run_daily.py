#!/usr/bin/env python3
"""编排每日科研文献雷达的检索与交付流程。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from common import ChineseArgumentParser, atomic_write_json, load_json, utc_now_iso
from profile_config import DEFAULT_PROFILE, ProfileError, load_profile
from update_research_memory import build_context, load_memory

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_HISTORY = SKILL_DIR / "data" / "pushed_articles.json"
DEFAULT_MEMORY = SKILL_DIR / "data" / "research_memory.json"
DEFAULT_RUNS = SKILL_DIR / "data" / "runs"


def run_script(name: str, *arguments: str) -> None:
    command = [sys.executable, str(SCRIPT_DIR / name), *arguments]
    subprocess.run(command, check=True)


def collect_stage(args: argparse.Namespace) -> Path:
    today = datetime.now().astimezone().date().isoformat()
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_RUNS / today
    output_dir.mkdir(parents=True, exist_ok=True)

    def execute_window(label: str, days: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        raw_path = output_dir / f"search_{label}.json"
        fresh_path = output_dir / f"deduplicated_{label}.json"
        ranked_path = output_dir / f"ranked_{label}.json"
        run_script(
            "search_papers.py",
            "--days", str(days),
            "--mode", args.mode,
            "--profile", str(args.profile),
            "--sources", args.sources,
            "--output", str(raw_path),
        )
        run_script(
            "deduplicate.py",
            "filter",
            "--input", str(raw_path),
            "--output", str(fresh_path),
            "--history", str(args.history),
        )
        run_script(
            "rank_papers.py",
            "--input", str(fresh_path),
            "--output", str(ranked_path),
            "--profile", str(args.profile),
            "--threshold", str(args.threshold),
            "--max-results", str(args.max_results),
        )
        return load_json(raw_path, {}), load_json(fresh_path, {}), load_json(ranked_path, {})

    # 多数学术接口只提供日级出版日期，而不是精确时间戳。
    # 因此以今天和昨天构成候选池，再由 Codex 优先复核可能位于近24小时内的论文。
    raw, fresh, ranked = execute_window("24h", 2)
    used_window = "近24小时优先（按来源可用的日级日期，候选池覆盖今天和昨天）"
    if int(ranked.get("recommended_count") or 0) < args.min_results:
        raw, fresh, ranked = execute_window("7d", 7)
        used_window = "最近7天（因近24小时高分候选不足5篇而扩大）"

    source_errors = raw.get("errors") or []
    warnings = [f"{item.get('source')}: {item.get('error')}" for item in source_errors]
    if fresh.get("update_count"):
        warnings.append(f"发现 {fresh['update_count']} 篇已推送论文的出版信息更新；不作为新论文重复推荐")
    queue = {
        "generated_at": utc_now_iso(),
        "date": today,
        "mode": args.mode,
        "profile_name": raw.get("profile_name") or "",
        "metadata": {
            "window": used_window,
            "retrieved_count": int(raw.get("retrieved_count") or 0),
            "unique_relevant_count": int(raw.get("unique_relevant_count") or 0),
            "new_after_history_count": int(fresh.get("new_count") or 0),
            "screened_count": int(ranked.get("screened_count") or 0),
            "preliminary_recommended_count": int(ranked.get("recommended_count") or 0),
            "threshold": args.threshold,
            "maximum": args.max_results,
            "source_counts": raw.get("source_counts") or {},
            "warnings": warnings,
        },
        "review_requirement": (
            "这些是元数据初筛候选，不是最终推送结果。Codex 必须阅读可用摘要，并在重要结论不充分时核对出版商页面/全文；"
            "逐项复核评分，排除证据不足或弱相关论文，再写入 reviewed_articles.json。"
        ),
        "research_memory_context": build_context(load_memory(args.memory), recent=10),
        "scoring_formula": ranked.get("formula"),
        "candidates": ranked.get("recommendations") or [],
        "updates_not_for_new_push": fresh.get("updates") or [],
    }
    queue_path = output_dir / "review_queue.json"
    atomic_write_json(queue_path, queue)
    print(f"复核队列已生成：{queue_path}")
    print(f"检索窗口：{used_window}；候选论文：{len(queue['candidates'])} 篇")
    return queue_path


def deliver_stage(args: argparse.Namespace) -> Path:
    reviewed_path = Path(args.reviewed)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    run_script("summarize_papers.py", "--input", str(reviewed_path), "--output", str(report_path))

    delivery = "local-report"
    should_commit = bool(args.record_local_report)
    if not args.skip_push:
        status_path = report_path.with_suffix(".delivery.json")
        run_script(
            "push_wechat.py",
            "--report", str(report_path),
            "--provider", args.provider,
            "--result-json", str(status_path),
        )
        status = load_json(status_path, {})
        if status.get("configured") and status.get("success"):
            delivery = str(status.get("provider"))
            should_commit = True
        elif not status.get("configured"):
            print("微信推送尚未配置。报告已正常生成；在当前对话展示报告后，可按 local-report 提交历史。")

    if should_commit:
        run_script(
            "deduplicate.py",
            "commit",
            "--input", str(reviewed_path),
            "--history", str(args.history),
            "--delivery", delivery,
        )
        try:
            run_script(
                "update_research_memory.py",
                "learn",
                "--input", str(reviewed_path),
                "--memory", str(args.memory),
                "--profile", str(args.profile),
                "--delivery", delivery,
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"警告：报告交付和历史提交已成功，但研究记忆更新失败：{exc}",
                file=sys.stderr,
            )
    else:
        print("未确认成功交付，因此没有写入推送历史。")
    print(f"报告已生成：{report_path}")
    return report_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = ChineseArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="检索、去重、评分并生成复核队列")
    collect_parser.add_argument("--mode", default="all", help="研究配置中定义的模式名称")
    collect_parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    collect_parser.add_argument("--sources", default="europepmc,crossref,semanticscholar,biorxiv")
    collect_parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    collect_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    collect_parser.add_argument("--output-dir")
    collect_parser.add_argument("--threshold", type=int, default=70)
    collect_parser.add_argument("--min-results", type=int, default=5)
    collect_parser.add_argument("--max-results", type=int, default=10)

    deliver_parser = subparsers.add_parser("deliver", help="生成已复核 JSON 报告，并可选择推送")
    deliver_parser.add_argument("--reviewed", required=True)
    deliver_parser.add_argument("--report", required=True)
    deliver_parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    deliver_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    deliver_parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    deliver_parser.add_argument("--provider", choices=("auto", "wxpusher", "serverchan", "wecom"), default="auto")
    deliver_parser.add_argument("--skip-push", action="store_true")
    deliver_parser.add_argument("--record-local-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "collect":
        try:
            load_profile(args.profile)
        except ProfileError as exc:
            raise SystemExit(str(exc)) from exc
        if not 0 <= args.threshold <= 100:
            raise SystemExit("--threshold 必须在0到100之间")
        if not 1 <= args.min_results <= args.max_results <= 50:
            raise SystemExit("参数必须满足 1 <= --min-results <= --max-results <= 50")
        collect_stage(args)
    else:
        deliver_stage(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
