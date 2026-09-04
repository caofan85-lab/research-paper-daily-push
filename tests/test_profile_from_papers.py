from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_research_profile import (  # noqa: E402
    ProfileBuildError,
    activate_profile,
    extract_document,
    prepare_context,
    validate_drafts,
)


class ProfilePreparationTests(unittest.TestCase):
    def test_prepare_reads_text_recursively_and_skips_duplicate_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "core").mkdir()
            text = "Cold adaptation in a polyploid forage legume. " * 20
            (root / "core" / "paper.md").write_text(text, encoding="utf-8")
            (root / "duplicate.txt").write_text(text, encoding="utf-8")

            payload = prepare_context(root)

            self.assertEqual(payload["document_count"], 1)
            self.assertEqual(payload["documents"][0]["relative_path"], "core/paper.md")
            self.assertTrue(any("内容重复" in item["reason"] for item in payload["errors"]))

    def test_prepare_rejects_folder_without_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "image.png").write_bytes(b"not a paper")
            with self.assertRaises(ProfileBuildError):
                prepare_context(root)

    def test_docx_text_is_extracted_without_external_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "paper.docx"
            xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Transcriptome evidence</w:t></w:r></w:p></w:body>'
                '</w:document>'
            )
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)

            result = extract_document(path, max_pages=10, max_chars=10_000)

            self.assertEqual(result["format"], "docx")
            self.assertIn("Transcriptome evidence", result["text"])

    def test_blank_pdf_is_flagged_as_probable_scan(self) -> None:
        try:
            from pypdf import PdfWriter
        except ModuleNotFoundError:
            self.skipTest("pypdf 尚未安装")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "blank.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with path.open("wb") as handle:
                writer.write(handle)

            result = extract_document(path, max_pages=10, max_chars=10_000)

            self.assertEqual(result["page_count"], 1)
            self.assertEqual(result["character_count"], 0)
            self.assertTrue(any("OCR" in warning for warning in result["warnings"]))


class ProfileDraftValidationTests(unittest.TestCase):
    def _write_fixture(self, root: Path, *, excerpt: str = "Cold adaptation") -> tuple[Path, Path, Path, Path]:
        profile = {
            "configured": False,
            "profile_name": "cold-legume",
            "research_context": "Polyploid forage legume cold adaptation",
            "target_system": "polyploid forage legume",
            "priority_questions": ["How does cold adaptation evolve?"],
            "queries": ["polyploid AND cold adaptation"],
            "modes": {},
            "topic_groups": [{"label": "cold", "weight": 80, "terms": ["cold adaptation"]}],
        }
        context = {
            "documents": [
                {
                    "relative_path": "paper.txt",
                    "sha256": "abc",
                    "text": "Cold adaptation in a polyploid forage legume was investigated.",
                }
            ]
        }
        evidence = {
            "schema_version": 1,
            "profile_claims": [
                {
                    "field": field,
                    "claim": f"claim for {field}",
                    "confidence": "high",
                    "evidence": [
                        {"source": "paper.txt", "locator": "abstract", "excerpt": excerpt}
                    ],
                }
                for field in (
                    "research_context",
                    "target_system",
                    "priority_questions[0]",
                    "queries[0]",
                    "topic_groups[0]",
                )
            ],
            "uncertainties": [],
        }
        profile_path = root / "profile.json"
        evidence_path = root / "evidence.json"
        context_path = root / "context.json"
        topics_path = root / "topics.md"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        context_path.write_text(json.dumps(context), encoding="utf-8")
        topics_path.write_text("# Research topics\n", encoding="utf-8")
        return profile_path, evidence_path, context_path, topics_path

    def test_valid_traceable_drafts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self._write_fixture(Path(temporary))
            self.assertEqual(validate_drafts(*paths), [])

    def test_invented_excerpt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self._write_fixture(Path(temporary), excerpt="Invented mechanism")
            errors = validate_drafts(*paths)
            self.assertTrue(any("不是来源文件中的可追溯原文" in error for error in errors))

    def test_configured_draft_is_rejected_before_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self._write_fixture(root)
            profile = json.loads(paths[0].read_text(encoding="utf-8"))
            profile["configured"] = True
            paths[0].write_text(json.dumps(profile), encoding="utf-8")
            errors = validate_drafts(*paths)
            self.assertTrue(any("configured 必须保持为 false" in error for error in errors))

    def test_activation_requires_confirmation_and_backs_up_existing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile, evidence, context, topics = self._write_fixture(root)
            profile_output = root / "research_profile.local.json"
            evidence_output = root / "profile_evidence.local.json"
            topics_output = root / "research_topics.local.md"
            profile_output.write_text('{"configured": true, "profile_name": "old"}', encoding="utf-8")
            arguments = Namespace(
                profile_draft=str(profile),
                evidence_draft=str(evidence),
                context=str(context),
                topics_draft=str(topics),
                profile_output=str(profile_output),
                evidence_output=str(evidence_output),
                topics_output=str(topics_output),
                confirm=None,
            )
            with self.assertRaises(ProfileBuildError):
                activate_profile(arguments)

            arguments.confirm = "CONFIRM"
            activate_profile(arguments)

            activated = json.loads(profile_output.read_text(encoding="utf-8"))
            self.assertTrue(activated["configured"])
            self.assertEqual(activated["profile_origin"]["type"], "representative_papers")
            self.assertTrue(evidence_output.exists())
            self.assertTrue(topics_output.exists())
            self.assertEqual(len(list(root.glob("research_profile.local.json.backup-*"))), 1)


if __name__ == "__main__":
    unittest.main()
