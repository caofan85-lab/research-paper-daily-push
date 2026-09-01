from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import push_wechat  # noqa: E402


class WxPusherConfigurationTests(unittest.TestCase):
    def test_valid_settings_support_multiple_uids(self) -> None:
        env = {
            "WXPUSHER_APP_TOKEN": "AT_example",
            "WXPUSHER_UID": "UID_one, UID_two;UID_three",
        }
        with patch.dict(os.environ, env, clear=True):
            token, uids = push_wechat.wxpusher_settings()
        self.assertEqual(token, "AT_example")
        self.assertEqual(uids, ["UID_one", "UID_two", "UID_three"])

    def test_invalid_prefix_is_rejected_without_network(self) -> None:
        env = {"WXPUSHER_APP_TOKEN": "wrong", "WXPUSHER_UID": "UID_one"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "AT_"):
                push_wechat.wxpusher_settings()

    def test_check_config_does_not_print_credentials(self) -> None:
        env = {"WXPUSHER_APP_TOKEN": "AT_secret", "WXPUSHER_UID": "UID_secret"}
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
            code = push_wechat.main(["--provider", "wxpusher", "--check-config"])
        self.assertEqual(code, 0)
        self.assertNotIn("AT_secret", output.getvalue())
        self.assertNotIn("UID_secret", output.getvalue())

    def test_test_message_dry_run_never_calls_sender(self) -> None:
        env = {"WXPUSHER_APP_TOKEN": "AT_secret", "WXPUSHER_UID": "UID_secret"}
        with tempfile.TemporaryDirectory() as temp_dir:
            result_path = Path(temp_dir) / "delivery.json"
            with (
                patch.dict(os.environ, env, clear=True),
                patch.object(push_wechat, "send_wxpusher") as sender,
            ):
                code = push_wechat.main(
                    [
                        "--provider",
                        "wxpusher",
                        "--test-message",
                        "--dry-run",
                        "--result-json",
                        str(result_path),
                    ]
                )
            self.assertEqual(code, 0)
            sender.assert_not_called()
            self.assertTrue(result_path.exists())

    def test_send_wxpusher_uses_official_markdown_payload(self) -> None:
        env = {"WXPUSHER_APP_TOKEN": "AT_secret", "WXPUSHER_UID": "UID_secret"}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                push_wechat,
                "json_request",
                return_value={"code": 1000, "success": True},
            ) as request,
        ):
            responses = push_wechat.send_wxpusher("测试标题", "# 测试正文")
        self.assertEqual(responses, [{"code": 1000, "success": True}])
        self.assertEqual(
            request.call_args.kwargs["payload"],
            {
                "appToken": "AT_secret",
                "content": "# 测试正文",
                "summary": "测试标题",
                "contentType": 3,
                "uids": ["UID_secret"],
                "verifyPayType": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
