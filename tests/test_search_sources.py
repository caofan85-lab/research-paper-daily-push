from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import search_papers  # noqa: E402


class SearchSourceTests(unittest.TestCase):
    def test_crossref_searches_online_and_general_publication_dates(self) -> None:
        empty_payload = {"message": {"items": []}}
        with (
            patch.dict(
                os.environ,
                {"CROSSREF_MAILTO": "researcher@example.org"},
                clear=True,
            ),
            patch.object(
                search_papers, "json_request", return_value=empty_payload
            ) as request,
            patch.object(search_papers.time, "sleep"),
        ):
            search_papers.search_crossref(
                ["plant cold stress"], date(2026, 8, 31), date(2026, 9, 1)
            )

        self.assertEqual(request.call_count, 2)
        queries = [
            parse_qs(urlparse(call.args[0]).query)
            for call in request.call_args_list
        ]
        filters = {query["filter"][0] for query in queries}
        self.assertEqual(
            filters,
            {
                "from-online-pub-date:2026-08-31,until-online-pub-date:2026-09-01,type:journal-article",
                "from-pub-date:2026-08-31,until-pub-date:2026-09-01,type:journal-article",
            },
        )
        self.assertTrue(
            all(query["mailto"] == ["researcher@example.org"] for query in queries)
        )

    def test_semantic_scholar_spaces_multiple_queries_at_one_request_per_second(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                search_papers, "json_request", return_value={"data": []}
            ),
            patch.object(search_papers.time, "sleep") as sleep,
        ):
            search_papers.search_semantic_scholar(
                ["cold stress", "polyploid"],
                date(2026, 8, 31),
                date(2026, 9, 1),
            )

        sleep.assert_called_once_with(1.05)


if __name__ == "__main__":
    unittest.main()
