from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_EXTRACTED_CHARACTERS = 60_000
OCR_TEXT_THRESHOLD = 80
OCR_DPI = 300


class PdfInputError(ValueError):
    """The uploaded PDF cannot be safely processed by the MVP."""


@dataclass(frozen=True)
class PdfPage:
    number: int
    text: str


def _ocr_page(pdf_bytes: bytes, page_index: int) -> str:
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as exc:
        raise PdfInputError(
            "스캔 페이지를 인식하려면 OCR 패키지가 필요합니다. "
            "python -m pip install -r requirements.txt 를 실행하세요."
        ) from exc

    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        page = pdf[page_index]
        image = page.render(scale=OCR_DPI / 72).to_pil()
        try:
            return pytesseract.image_to_string(image, lang="kor+eng", config="--psm 6").strip()
        finally:
            image.close()
    except pytesseract.TesseractNotFoundError as exc:
        raise PdfInputError(
            "Tesseract OCR을 찾을 수 없습니다. README의 Tesseract 설치 안내를 확인하세요."
        ) from exc
    except pytesseract.TesseractError as exc:
        raise PdfInputError(
            f"{page_index + 1}페이지 OCR에 실패했습니다. "
            "한국어/영어 Tesseract 언어 데이터를 설치했는지 확인하세요."
        ) from exc
    except (OSError, RuntimeError, pdfium.PdfiumError) as exc:
        raise PdfInputError(f"{page_index + 1}페이지를 이미지로 변환하지 못했습니다.") from exc
    finally:
        if "pdf" in locals():
            pdf.close()


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
        pages = []
        for index, page in enumerate(reader.pages):
            native_text = page.extract_text() or ""
            if len(native_text.strip()) < OCR_TEXT_THRESHOLD:
                ocr_text = _ocr_page(pdf_bytes, index)
                if not ocr_text:
                    if not native_text.strip():
                        raise PdfInputError(
                            f"{index + 1}페이지에서 텍스트를 인식하지 못했습니다. "
                            "더 선명한 PDF를 사용하거나 원문을 직접 확인하세요."
                        )
                else:
                    native_text = f"{native_text.strip()}\n{ocr_text}".strip()
            pages.append(PdfPage(number=index + 1, text=native_text))
    except (PdfReadError, OSError) as exc:
        raise PdfInputError("PDF를 읽을 수 없습니다. 파일이 손상되지 않았는지 확인하세요.") from exc

    if not any(page.text.strip() for page in pages):
        raise PdfInputError("PDF 페이지를 찾지 못했습니다. 파일을 확인하세요.")
    if sum(len(page.text) for page in pages) > MAX_EXTRACTED_CHARACTERS:
        raise PdfInputError("추출된 텍스트가 너무 깁니다. 60,000자 이하 PDF를 사용하세요.")
    return pages
