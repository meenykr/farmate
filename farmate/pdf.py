from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_EXTRACTED_CHARACTERS = 60_000


class PdfInputError(ValueError):
    """The uploaded PDF cannot be safely processed by the MVP."""


@dataclass(frozen=True)
class PdfPage:
    number: int
    text: str


def extract_pdf_pages(pdf_bytes: bytes) -> list[PdfPage]:
    if not pdf_bytes:
        raise PdfInputError("PDF 파일이 비어 있습니다.")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise PdfInputError("PDF는 20MB 이하만 처리할 수 있습니다.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            raise PdfInputError("암호가 설정된 PDF는 처리할 수 없습니다.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise PdfInputError("PDF는 50페이지 이하만 처리할 수 있습니다.")
        pages = [
            PdfPage(number=index, text=page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)
        ]
    except (PdfReadError, OSError) as exc:
        raise PdfInputError("PDF를 읽을 수 없습니다. 파일이 손상되지 않았는지 확인하세요.") from exc

    if not any(page.text.strip() for page in pages):
        raise PdfInputError("PDF에서 텍스트를 찾지 못했습니다. 스캔본/OCR PDF는 MVP에서 지원하지 않습니다.")
    if sum(len(page.text) for page in pages) > MAX_EXTRACTED_CHARACTERS:
        raise PdfInputError("추출된 텍스트가 너무 깁니다. 60,000자 이하 PDF를 사용하세요.")
    return pages
