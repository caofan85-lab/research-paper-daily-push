"""Offline regression tests for shared normalization helpers."""

import unittest

from scripts.common import normalize_doi


class NormalizeDoiTests(unittest.TestCase):
    def test_normalizes_unicode_doi_url_at_whitespace_and_punctuation_boundary(self) -> None:
        self.assertEqual(
            normalize_doi(" \tHTTPS://DX.DOI.ORG/10.1234/CAFÉ.ÅNGSTRÖM); \n"),
            "10.1234/café.ångström",
        )

    def test_accepts_doi_label_with_whitespace(self) -> None:
        self.assertEqual(normalize_doi("DOI:   10.5555/Example"), "10.5555/example")

    def test_returns_empty_for_empty_or_falsy_non_string_values(self) -> None:
        for value in (None, "", 0, False):
            with self.subTest(value=value):
                self.assertEqual(normalize_doi(value), "")


if __name__ == "__main__":
    unittest.main()
