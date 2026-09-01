from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import ChineseArgumentParser  # noqa: E402
from summarize_papers import render_report  # noqa: E402


class ChineseInterfaceTests(unittest.TestCase):
    def test_command_help_uses_chinese_headings(self) -> None:
        parser = ChineseArgumentParser(description="中文帮助说明")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("用法：", output.getvalue())
        self.assertIn("选项:", output.getvalue())
        self.assertIn("显示此帮助信息并退出", output.getvalue())

    def test_empty_report_uses_chinese_headings(self) -> None:
        report = render_report(
            {
                "date": "2026-09-01",
                "term_explanation_mode": "dual",
                "metadata": {"retrieved_count": 0, "screened_count": 0},
                "articles": [],
                "research_ideas": [],
            }
        )
        self.assertIn("今日最值得阅读前三名", report)
        self.assertNotIn("TOP 3", report)


if __name__ == "__main__":
    unittest.main()
