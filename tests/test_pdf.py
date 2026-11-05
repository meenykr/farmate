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
    def __init__(self, _file: object, strict: bool = False, pages: list[FakePage] | None = None) -> None:
        self.is_encrypted = False
        self.pages = pages or [FakePage("농업 지원사업 공고 내용 " * 8)]


class PdfExtractionTests(unittest.TestCase):
    @patch("farmate.pdf.PdfReader", FakeReader)
    def test_extracts_text_from_pdf_pages(self) -> None:
        pages = extract_pdf_pages(b"pdf")
        self.assertEqual(pages[0].number, 1)
        self.assertEqual(pages[0].text, "농업 지원사업 공고 내용 " * 8)

    @patch("farmate.pdf._ocr_page", return_value="청년농업인 지원사업")
    @patch("farmate.pdf.PdfReader")
    def test_scanned_page_uses_ocr_and_preserves_page_number(
        self, reader_mock: object, ocr_mock: object
    ) -> None:
        reader_mock.return_value = FakeReader(  # type: ignore[attr-defined]
            b"pdf",
            pages=[FakePage("농업 지원사업 공고 내용 " * 8), FakePage("")],
        )

        pages = extract_pdf_pages(b"pdf")

        self.assertEqual(pages[1].number, 2)
        self.assertEqual(pages[1].text, "청년농업인 지원사업")
        ocr_mock.assert_called_once_with(b"pdf", 1)  # type: ignore[attr-defined]

    @patch("farmate.pdf._ocr_page", return_value="농업경영체 등록이 필요합니다")
    @patch("farmate.pdf.PdfReader")
    def test_short_native_text_page_is_enhanced_with_ocr(
        self, reader_mock: object, _ocr_mock: object
    ) -> None:
        reader_mock.return_value = FakeReader(  # type: ignore[attr-defined]
            b"pdf", pages=[FakePage("신청 자격")]
        )

        pages = extract_pdf_pages(b"pdf")

        self.assertIn("신청 자격", pages[0].text)
        self.assertIn("농업경영체 등록이 필요합니다", pages[0].text)

    @patch("farmate.pdf._ocr_page", return_value="")
    @patch("farmate.pdf.PdfReader")
    def test_unreadable_scanned_page_returns_clear_error(
        self, reader_mock: object, _ocr_mock: object
    ) -> None:
        reader_mock.return_value = FakeReader(  # type: ignore[attr-defined]
            b"pdf", pages=[FakePage("")]
        )

        with self.assertRaisesRegex(PdfInputError, "1페이지에서 텍스트를 인식하지 못했습니다"):
            extract_pdf_pages(b"pdf")

    def test_rejects_empty_upload(self) -> None:
        with self.assertRaisesRegex(PdfInputError, "비어"):
            extract_pdf_pages(b"")


if __name__ == "__main__":
    unittest.main()
