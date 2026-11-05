from __future__ import annotations

import unittest
from unittest.mock import patch

from farmate.pdf import PdfInputError, extract_pdf_pages


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, _file: object, strict: bool = False) -> None:
        self.is_encrypted = False
        self.pages = [FakePage("공고 내용")]


class PdfExtractionTests(unittest.TestCase):
    @patch("farmate.pdf.PdfReader", FakeReader)
    def test_extracts_text_from_pdf_pages(self) -> None:
        pages = extract_pdf_pages(b"pdf")
        self.assertEqual(pages[0].number, 1)
        self.assertEqual(pages[0].text, "공고 내용")

    def test_rejects_empty_upload(self) -> None:
        with self.assertRaisesRegex(PdfInputError, "비어"):
            extract_pdf_pages(b"")


if __name__ == "__main__":
    unittest.main()
