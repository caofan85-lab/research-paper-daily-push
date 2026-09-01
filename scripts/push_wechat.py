#!/usr/bin/env python3
"""Send a completed report through WxPusher, ServerChan, or a WeCom webhook."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from common import atomic_write_json, form_request, json_request, utc_now_iso

PROVIDER_PRIORITY = ("wxpusher", "serverchan", "wecom")


def configured(provider: str) -> bool:
    if provider == "wxpusher":
        return bool(os.environ.get("WXPUSHER_APP_TOKEN") and os.environ.get("WXPUSHER_UID"))
    if provider == "serverchan":
        return bool(os.environ.get("SERVERCHAN_SENDKEY"))
    if provider == "wecom":
        return bool(os.environ.get("WECOM_WEBHOOK_URL") or os.environ.get("WECHAT_WORK_WEBHOOK_URL"))
    return False


def select_provider(requested: str) -> str | None:
    if requested != "auto":
        return requested if configured(requested) else None
    return next((provider for provider in PROVIDER_PRIORITY if configured(provider)), None)


def chunk_utf8(text: str, maximum_bytes: int) -> list[str]:
    if len(text.encode("utf-8")) <= maximum_bytes:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for paragraph in text.splitlines(keepends=True):
        data = paragraph.encode("utf-8")
        if len(data) > maximum_bytes:
            if current:
                chunks.append("".join(current).rstrip())
                current, current_bytes = [], 0
            piece = ""
            piece_bytes = 0
            for char in paragraph:
                char_bytes = len(char.encode("utf-8"))
                if piece and piece_bytes + char_bytes > maximum_bytes:
                    chunks.append(piece.rstrip())
                    piece, piece_bytes = "", 0
                piece += char
                piece_bytes += char_bytes
            if piece:
                current = [piece]
                current_bytes = piece_bytes
        elif current and current_bytes + len(data) > maximum_bytes:
            chunks.append("".join(current).rstrip())
            current = [paragraph]
            current_bytes = len(data)
        else:
            current.append(paragraph)
            current_bytes += len(data)
    if current:
        chunks.append("".join(current).rstrip())
    return [chunk for chunk in chunks if chunk]


def send_wxpusher(title: str, report: str) -> list[dict[str, Any]]:
    token = os.environ["WXPUSHER_APP_TOKEN"].strip()
    uids = [value.strip() for value in re.split(r"[,;]", os.environ["WXPUSHER_UID"]) if value.strip()]
    if not token or not uids:
        raise ValueError("WXPUSHER_APP_TOKEN and WXPUSHER_UID must be non-empty")
    responses: list[dict[str, Any]] = []
    chunks = chunk_utf8(report, 18000)
    for index, chunk in enumerate(chunks, 1):
        suffix = f" ({index}/{len(chunks)})" if len(chunks) > 1 else ""
        payload: dict[str, Any] = {
            "appToken": token,
            "content": chunk,
            "summary": (title + suffix)[:100],
            "contentType": 3,
            "uids": uids,
            "verifyPayType": 0,
        }
        content_url = os.environ.get("WXPUSHER_CONTENT_URL", "").strip()
        if content_url.startswith(("https://", "http://")):
            payload["url"] = content_url
        response = json_request(
            "https://wxpusher.zjiecode.com/api/send/message", method="POST", payload=payload
        )
        if response.get("code") != 1000 or response.get("success") is False:
            raise RuntimeError(f"WxPusher rejected message: code={response.get('code')}, msg={response.get('msg')}")
        responses.append({"code": response.get("code"), "success": response.get("success", True)})
    return responses


def serverchan_url(sendkey: str) -> str:
    if sendkey.startswith("sctp"):
        match = re.fullmatch(r"sctp(\d+)t.+", sendkey)
        if not match:
            raise ValueError("Invalid ServerChan sctp SendKey format")
        return f"https://{match.group(1)}.push.ft07.com/send/{quote(sendkey, safe='')}.send"
    return f"https://sctapi.ftqq.com/{quote(sendkey, safe='')}.send"


def send_serverchan(title: str, report: str) -> list[dict[str, Any]]:
    sendkey = os.environ["SERVERCHAN_SENDKEY"].strip()
    if not sendkey:
        raise ValueError("SERVERCHAN_SENDKEY must be non-empty")
    responses: list[dict[str, Any]] = []
    chunks = chunk_utf8(report, 30000)
    for index, chunk in enumerate(chunks, 1):
        suffix = f" {index}/{len(chunks)}" if len(chunks) > 1 else ""
        response = form_request(
            serverchan_url(sendkey), {"title": (title + suffix)[:32], "desp": chunk}
        )
        if int(response.get("code", -1)) != 0:
            raise RuntimeError(f"ServerChan rejected message: code={response.get('code')}, message={response.get('message') or response.get('msg')}")
        responses.append({"code": response.get("code"), "success": True})
    return responses


def validated_wecom_url() -> str:
    url = (os.environ.get("WECOM_WEBHOOK_URL") or os.environ.get("WECHAT_WORK_WEBHOOK_URL") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "qyapi.weixin.qq.com":
        raise ValueError("WeCom webhook must use https://qyapi.weixin.qq.com/")
    if parsed.path != "/cgi-bin/webhook/send" or not parsed.query.startswith("key="):
        raise ValueError("Invalid WeCom group robot webhook path")
    return url


def send_wecom(title: str, report: str) -> list[dict[str, Any]]:
    url = validated_wecom_url()
    chunks = chunk_utf8(report, 3500)
    responses: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, 1):
        header = f"**{title}**"
        if len(chunks) > 1:
            header += f" ({index}/{len(chunks)})"
        response = json_request(
            url,
            method="POST",
            payload={"msgtype": "markdown", "markdown": {"content": f"{header}\n\n{chunk}"}},
        )
        if int(response.get("errcode", -1)) != 0:
            raise RuntimeError(f"WeCom rejected message: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
        responses.append({"code": response.get("errcode"), "success": True})
    return responses


SENDERS = {
    "wxpusher": send_wxpusher,
    "serverchan": send_serverchan,
    "wecom": send_wecom,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--title", default="今日科研文献雷达")
    parser.add_argument("--provider", choices=("auto",) + PROVIDER_PRIORITY, default="auto")
    parser.add_argument("--result-json", help="Write a credential-free delivery status JSON")
    parser.add_argument("--dry-run", action="store_true", help="Validate/chunk without any network call")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = Path(args.report).read_text(encoding="utf-8")
    provider = select_provider(args.provider)
    if provider is None:
        status = {
            "generated_at": utc_now_iso(),
            "configured": False,
            "success": False,
            "provider": None,
            "message": "微信推送尚未配置。",
        }
        if args.result_json:
            atomic_write_json(args.result_json, status)
        print("微信推送尚未配置。")
        return 0
    if args.dry_run:
        limit = {"wxpusher": 18000, "serverchan": 30000, "wecom": 3500}[provider]
        status = {
            "generated_at": utc_now_iso(),
            "configured": True,
            "success": True,
            "dry_run": True,
            "provider": provider,
            "chunks": len(chunk_utf8(report, limit)),
        }
    else:
        responses = SENDERS[provider](args.title, report)
        status = {
            "generated_at": utc_now_iso(),
            "configured": True,
            "success": True,
            "dry_run": False,
            "provider": provider,
            "chunks": len(responses),
        }
    if args.result_json:
        atomic_write_json(args.result_json, status)
    print(f"Delivery {'validated' if args.dry_run else 'completed'} via {provider}; {status['chunks']} chunk(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
