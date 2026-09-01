#!/usr/bin/env python3
"""通过 WxPusher、Server酱或企业微信 Webhook 发送完整报告。"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from common import ChineseArgumentParser, atomic_write_json, form_request, json_request, utc_now_iso

PROVIDER_PRIORITY = ("wxpusher", "serverchan", "wecom")


def wxpusher_settings() -> tuple[str, list[str]]:
    """返回经过验证的 WxPusher 配置，不记录任何凭据内容。"""
    token = os.environ.get("WXPUSHER_APP_TOKEN", "").strip()
    uids = [
        value.strip()
        for value in re.split(r"[,;]", os.environ.get("WXPUSHER_UID", ""))
        if value.strip()
    ]
    if not token or not uids:
        raise ValueError("WXPUSHER_APP_TOKEN 和 WXPUSHER_UID 不能为空")
    if not token.startswith("AT_"):
        raise ValueError("WXPUSHER_APP_TOKEN 必须以 AT_ 开头")
    if any(not uid.startswith("UID_") for uid in uids):
        raise ValueError("每个 WXPUSHER_UID 都必须以 UID_ 开头")
    return token, uids


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
    token, uids = wxpusher_settings()
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
            raise RuntimeError(f"WxPusher 拒绝了消息：code={response.get('code')}，msg={response.get('msg')}")
        responses.append({"code": response.get("code"), "success": response.get("success", True)})
    return responses


def serverchan_url(sendkey: str) -> str:
    if sendkey.startswith("sctp"):
        match = re.fullmatch(r"sctp(\d+)t.+", sendkey)
        if not match:
            raise ValueError("Server酱 sctp SendKey 格式无效")
        return f"https://{match.group(1)}.push.ft07.com/send/{quote(sendkey, safe='')}.send"
    return f"https://sctapi.ftqq.com/{quote(sendkey, safe='')}.send"


def send_serverchan(title: str, report: str) -> list[dict[str, Any]]:
    sendkey = os.environ["SERVERCHAN_SENDKEY"].strip()
    if not sendkey:
        raise ValueError("SERVERCHAN_SENDKEY 不能为空")
    responses: list[dict[str, Any]] = []
    chunks = chunk_utf8(report, 30000)
    for index, chunk in enumerate(chunks, 1):
        suffix = f" {index}/{len(chunks)}" if len(chunks) > 1 else ""
        response = form_request(
            serverchan_url(sendkey), {"title": (title + suffix)[:32], "desp": chunk}
        )
        if int(response.get("code", -1)) != 0:
            raise RuntimeError(f"Server酱拒绝了消息：code={response.get('code')}，message={response.get('message') or response.get('msg')}")
        responses.append({"code": response.get("code"), "success": True})
    return responses


def validated_wecom_url() -> str:
    url = (os.environ.get("WECOM_WEBHOOK_URL") or os.environ.get("WECHAT_WORK_WEBHOOK_URL") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "qyapi.weixin.qq.com":
        raise ValueError("企业微信 Webhook 必须使用 https://qyapi.weixin.qq.com/")
    if parsed.path != "/cgi-bin/webhook/send" or not parsed.query.startswith("key="):
        raise ValueError("企业微信群机器人 Webhook 路径无效")
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
            raise RuntimeError(f"企业微信拒绝了消息：errcode={response.get('errcode')}，errmsg={response.get('errmsg')}")
        responses.append({"code": response.get("errcode"), "success": True})
    return responses


SENDERS = {
    "wxpusher": send_wxpusher,
    "serverchan": send_serverchan,
    "wecom": send_wecom,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = ChineseArgumentParser(description=__doc__)
    parser.add_argument("--report", help="需要发送的完整 Markdown 报告")
    parser.add_argument("--title")
    parser.add_argument("--provider", choices=("auto",) + PROVIDER_PRIORITY, default="auto")
    parser.add_argument("--result-json", help="写入不含凭据的交付状态 JSON")
    parser.add_argument("--dry-run", action="store_true", help="仅验证配置和分段，不发起网络请求")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--check-config",
        action="store_true",
        help="在本地验证通知渠道配置，不发送消息",
    )
    action.add_argument(
        "--test-message",
        action="store_true",
        help="发送内置的简短连通性测试，不读取报告",
    )
    args = parser.parse_args(argv)
    if not args.report and not args.check_config and not args.test_message:
        parser.error("必须指定 --report、--check-config 或 --test-message 中的一项")
    return args


def validate_provider_config(provider: str) -> dict[str, Any]:
    """验证所选通知渠道，但不返回或输出凭据。"""
    if provider == "wxpusher":
        _, uids = wxpusher_settings()
        return {"recipients": len(uids)}
    if provider == "serverchan":
        sendkey = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
        if not sendkey:
            raise ValueError("SERVERCHAN_SENDKEY 不能为空")
        serverchan_url(sendkey)
        return {}
    if provider == "wecom":
        validated_wecom_url()
        return {}
    raise ValueError(f"不支持的通知渠道：{provider}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
        return 2 if args.check_config or args.test_message else 0

    try:
        config_summary = validate_provider_config(provider)
    except ValueError as exc:
        print(f"{provider} 配置无效：{exc}")
        return 2

    if args.check_config:
        status = {
            "generated_at": utc_now_iso(),
            "configured": True,
            "success": True,
            "provider": provider,
            **config_summary,
        }
        if args.result_json:
            atomic_write_json(args.result_json, status)
        recipient_note = f"；接收者数量={config_summary['recipients']}" if "recipients" in config_summary else ""
        print(f"配置有效：通知渠道={provider}{recipient_note}。未输出任何凭据。")
        return 0

    title = args.title or ("WxPusher 配置测试" if args.test_message else "今日科研文献雷达")
    report = (
        "# WxPusher 配置测试\n\n"
        "如果你看到这条消息，说明应用 Token、UID 和消息接口均已连通。\n\n"
        f"测试时间（UTC）：{utc_now_iso()}"
        if args.test_message
        else Path(args.report).read_text(encoding="utf-8")
    )
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
        responses = SENDERS[provider](title, report)
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
    action = "验证完成" if args.dry_run else "发送完成"
    print(f"{provider} {action}；共 {status['chunks']} 个消息分段。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
