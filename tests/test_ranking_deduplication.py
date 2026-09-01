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

    def test_cross_topic_bonus_requires_every_configured_topic(self) -> None:
        configured_profile = {
            "topic_groups": [
                {"label": "低温", "weight": 40, "terms": ["cold"]},
                {"label": "多倍体", "weight": 40, "terms": ["polyploid"]},
            ],
            "cross_topic_bonuses": [
                {
                    "labels": ["低温", "多倍体"],
                    "bonus": 10,
                    "reason": "低温与多倍体交叉",
                }
            ],
        }

        partial_score, partial_topics, partial_evidence = rank_papers.score_relevance(
            "cold acclimation", configured_profile
        )
        full_score, full_topics, full_evidence = rank_papers.score_relevance(
            "cold acclimation in a polyploid plant", configured_profile
        )

        self.assertEqual(partial_topics, ["低温"])
        self.assertEqual(partial_score, 40)
        self.assertNotIn("低温与多倍体交叉", partial_evidence)
        self.assertEqual(full_topics, ["低温", "多倍体"])
        self.assertEqual(full_score, 93)
        self.assertIn("低温与多倍体交叉", full_evidence)

    def test_strong_recommendation_requires_every_topic_and_method(self) -> None:
        configured_profile = {
            "strong_recommendation_rules": [
                {
                    "labels": ["低温", "多倍体"],
                    "methods": ["转录组", "Hi-C"],
                    "min_score": 80,
                    "reason": "核心主题与技术全部命中",
                }
            ]
        }

        missing_topic = rank_papers.strong_recommendation(
            ["低温"], ["转录组", "Hi-C"], 90, configured_profile
        )
        missing_method = rank_papers.strong_recommendation(
            ["低温", "多倍体"], ["转录组"], 90, configured_profile
        )
        complete = rank_papers.strong_recommendation(
            ["低温", "多倍体"], ["转录组", "Hi-C"], 90, configured_profile
        )

        self.assertEqual(missing_topic, (False, []))
        self.assertEqual(missing_method, (False, []))
        self.assertEqual(complete, (True, ["核心主题与技术全部命中"]))


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
