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
import run_daily  # noqa: E402


class OpenAlexSearchTests(unittest.TestCase):
    def test_reconstructs_abstract_from_inverted_index(self) -> None:
        abstract = search_papers.reconstruct_openalex_abstract(
            {"stress": [2], "Cold": [0], "shapes": [1], "responses.": [3]}
        )
        self.assertEqual(abstract, "Cold shapes stress responses.")

    def test_missing_or_invalid_abstract_index_returns_empty_text(self) -> None:
        self.assertEqual(search_papers.reconstruct_openalex_abstract(None), "")
        self.assertEqual(
            search_papers.reconstruct_openalex_abstract({"ignored": "not-a-list"}),
            "",
        )

    def test_search_uses_date_filter_selected_fields_and_bearer_key(self) -> None:
        payload = {
            "results": [
                {
                    "id": "https://openalex.org/W123",
                    "doi": "https://doi.org/10.1000/TEST",
                    "display_name": "Cold stress response in plants",
                    "authorships": [
                        {"author": {"display_name": "Alice Example"}},
                        {"author": {"display_name": "Bob Example"}},
                    ],
                    "primary_location": {
                        "source": {"display_name": "Plant Journal"},
                        "landing_page_url": "https://example.org/article",
                    },
                    "best_oa_location": {
                        "landing_page_url": "https://example.org/open"
                    },
                    "publication_date": "2026-09-01",
                    "type": "article",
                    "abstract_inverted_index": {
                        "Cold": [0],
                        "response": [1],
                    },
                    "cited_by_count": 7,
                    "open_access": {"is_oa": True},
                    "is_retracted": False,
                }
            ]
        }
        with (
            patch.dict(os.environ, {"OPENALEX_API_KEY": "test-key"}, clear=True),
            patch.object(search_papers, "json_request", return_value=payload) as request,
        ):
            results = search_papers.search_openalex(
                ["plant AND cold"], date(2026, 8, 31), date(2026, 9, 1)
            )

        query = parse_qs(urlparse(request.call_args.args[0]).query)
        self.assertEqual(query["search"], ["plant AND cold"])
        self.assertEqual(
            query["filter"],
            ["from_publication_date:2026-08-31,to_publication_date:2026-09-01"],
        )
        self.assertEqual(query["sort"], ["publication_date:desc"])
        self.assertEqual(query["per_page"], ["100"])
        self.assertIn("abstract_inverted_index", query["select"][0])
        self.assertEqual(
            request.call_args.kwargs["headers"],
            {"Authorization": "Bearer test-key"},
        )
        self.assertEqual(len(results), 1)
        paper = results[0]
        self.assertEqual(paper["doi"], "10.1000/test")
        self.assertEqual(paper["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(paper["journal"], "Plant Journal")
        self.assertEqual(paper["url"], "https://doi.org/10.1000/test")
        self.assertEqual(paper["abstract"], "Cold response")
        self.assertEqual(paper["source_ids"], {"openalex": "W123"})
        self.assertTrue(paper["is_open_access"])

    def test_missing_doi_and_abstract_use_safe_fallbacks(self) -> None:
        payload = {
            "results": [
                {
                    "id": "https://openalex.org/W456",
                    "doi": None,
                    "display_name": "A recent preprint",
                    "authorships": [],
                    "primary_location": {
                        "source": None,
                        "raw_source_name": "Repository Name",
                        "landing_page_url": "https://example.org/preprint",
                    },
                    "best_oa_location": None,
                    "publication_date": "2026-08-31",
                    "type": "preprint",
                    "abstract_inverted_index": None,
                    "cited_by_count": 0,
                    "open_access": {"is_oa": True},
                    "is_retracted": False,
                }
            ]
        }
        with patch.object(search_papers, "json_request", return_value=payload):
            paper = search_papers.search_openalex(
                ["plant"], date(2026, 8, 31), date(2026, 9, 1)
            )[0]

        self.assertEqual(paper["url"], "https://example.org/preprint")
        self.assertEqual(paper["journal"], "Repository Name")
        self.assertTrue(paper["is_preprint"])
        self.assertIn("OpenAlex 未提供摘要", paper["needs_verification"][0])

    def test_retracted_work_is_marked_for_existing_exclusion_logic(self) -> None:
        payload = {
            "results": [
                {
                    "id": "https://openalex.org/W789",
                    "display_name": "Retracted work",
                    "authorships": [],
                    "primary_location": {},
                    "publication_date": "2026-09-01",
                    "type": "article",
                    "abstract_inverted_index": {"Text": [0]},
                    "open_access": {},
                    "is_retracted": True,
                }
            ]
        }
        with patch.object(search_papers, "json_request", return_value=payload):
            paper = search_papers.search_openalex(
                ["plant"], date(2026, 9, 1), date(2026, 9, 1)
            )[0]
        self.assertIn("retraction", paper["article_type"])

    def test_openalex_is_registered_as_a_default_source(self) -> None:
        self.assertIn("openalex", search_papers.API_SOURCES)
        self.assertIs(
            search_papers.SOURCE_FUNCTIONS["openalex"],
            search_papers.search_openalex,
        )

    def test_daily_collection_enables_openalex_by_default(self) -> None:
        args = run_daily.parse_args(["collect"])
        self.assertIn("openalex", args.sources.split(","))


if __name__ == "__main__":
    unittest.main()
