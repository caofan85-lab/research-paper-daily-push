from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import deduplicate  # noqa: E402
import rank_papers  # noqa: E402


def profile() -> dict[str, object]:
    return {
        "profile_name": "测试配置",
        "topic_groups": [
            {"label": "低温", "weight": 80, "terms": ["cold stress"]}
        ],
        "method_groups": [
            {"label": "转录组", "terms": ["rna-seq"]}
        ],
        "quality_tiers": {
            "tier_1": ["Test Journal"],
            "tier_2": [],
            "tier_3": [],
        },
    }


class RankingTests(unittest.TestCase):
    def test_recommendation_score_uses_declared_weights(self) -> None:
        paper = {
            "title": "Cold stress response",
            "abstract": "A novel RNA-seq knockout time course study.",
            "journal": "Test Journal",
            "article_type": "article",
        }
        ranked = rank_papers.rank_one(paper, profile())
        self.assertEqual(
            rank_papers.WEIGHTS,
            {
                "relevance": 0.40,
                "novelty": 0.20,
                "quality": 0.15,
                "methodology": 0.15,
                "inspiration": 0.10,
            },
        )
        expected = round(
            sum(
                ranked["component_scores"][name] * weight
                for name, weight in rank_papers.WEIGHTS.items()
            )
        )
        self.assertEqual(ranked["recommendation_score"], expected)

    def test_threshold_includes_70_and_excludes_69(self) -> None:
        ranked = [
            {"title": "boundary", "recommendation_score": 70, "excluded": False},
            {"title": "below", "recommendation_score": 69, "excluded": False},
        ]
        with patch.object(rank_papers, "rank_one", side_effect=ranked):
            result = rank_papers.rank_payload(
                {"papers": [{}, {}]}, profile(), threshold=70
            )
        self.assertEqual(
            [paper["title"] for paper in result["recommendations"]],
            ["boundary"],
        )

    def test_excluded_high_score_paper_is_not_recommended(self) -> None:
        with patch.object(
            rank_papers,
            "rank_one",
            return_value={
                "title": "excluded",
                "recommendation_score": 100,
                "excluded": True,
            },
        ):
            result = rank_papers.rank_payload({"papers": [{}]}, profile(), threshold=70)
        self.assertEqual(result["recommendations"], [])


class DeduplicationTests(unittest.TestCase):
    def test_doi_variants_are_recognized_as_duplicates(self) -> None:
        history = [{"doi": "10.1000/example", "title": "Original"}]
        papers = [
            {
                "doi": "https://doi.org/10.1000/EXAMPLE.",
                "title": "Changed title",
            }
        ]
        result = deduplicate.filter_history(papers, history)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["new_count"], 0)

    def test_normalized_title_is_used_when_doi_is_missing(self) -> None:
        history = [{"doi": "", "title": "Cold-Stress Responses in Plants"}]
        papers = [{"doi": "", "title": "cold stress responses in plants!"}]
        result = deduplicate.filter_history(papers, history)
        self.assertEqual(result["duplicate_count"], 1)

    def test_preprint_to_formal_publication_is_an_update(self) -> None:
        history = [
            {
                "doi": "",
                "title": "Cold response mechanism",
                "publication_date": "2026-08-01",
                "journal": "bioRxiv",
                "article_type": "preprint",
                "is_preprint": True,
                "pushed_date": "2026-08-02",
            }
        ]
        papers = [
            {
                "doi": "10.1000/formal",
                "title": "Cold response mechanism",
                "publication_date": "2026-09-01",
                "journal": "Plant Journal",
                "article_type": "article",
                "is_preprint": False,
            }
        ]
        result = deduplicate.filter_history(papers, history)
        self.assertEqual(result["update_count"], 1)
        self.assertIn("formal_publication", result["updates"][0]["updated_fields"])
        self.assertEqual(result["new_count"], 0)

    def test_commit_rejects_duplicate_doi_variants_in_same_batch(self) -> None:
        papers = [
            {"doi": "10.1000/example", "title": "First"},
            {"doi": "DOI: 10.1000/EXAMPLE", "title": "Second"},
        ]
        history, committed = deduplicate.commit_history(
            papers,
            [],
            delivery="local-report",
            pushed_date="2026-09-01",
        )
        self.assertEqual(committed, 1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["doi"], "10.1000/example")


if __name__ == "__main__":
    unittest.main()
