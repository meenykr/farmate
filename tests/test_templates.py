from __future__ import annotations

import unittest
import zipfile
from io import BytesIO

from farmate.templates import (
    TemplateInputError,
    extract_template_text,
    fill_hwpx_template,
)

SECTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p id="1"><hp:run><hp:t>Application</hp:t></hp:run></hp:p>
  <hp:p id="2"><hp:run><hp:t>{{사업명}}</hp:t></hp:run></hp:p>
  <hp:tbl><hp:tr>
    <hp:tc><hp:p><hp:run><hp:t>성명</hp:t></hp:run></hp:p></hp:tc>
    <hp:tc><hp:p><hp:run><hp:t/></hp:run></hp:p></hp:tc>
  </hp:tr></hp:tbl>
</hs:sec>""".encode("utf-8")


def make_hwpx(section: bytes = SECTION_XML) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", b"application/hwp+zip")
        archive.writestr("Contents/section0.xml", section)
        archive.writestr("Contents/header.xml", b"<header>unchanged</header>")
        archive.writestr("BinData/image1.png", b"image-data")
    return output.getvalue()


class TemplateTests(unittest.TestCase):
    def test_extracts_hwp_x_section_text(self) -> None:
        text = extract_template_text("application.hwpx", make_hwpx())
        self.assertIn("Application", text)
        self.assertIn("{{사업명}}", text)
        self.assertIn("성명", text)

    def test_fills_placeholders_and_labeled_cells_and_preserves_package(self) -> None:
        source = make_hwpx()
        completed, filled_count = fill_hwpx_template(
            "application.hwpx",
            source,
            {"사업명": "청년농업 지원", "성명": "홍길동"},
            "신청 목적\n지역 농산물 가공 기반을 조성합니다.",
        )

        with zipfile.ZipFile(BytesIO(completed)) as archive:
            section = archive.read("Contents/section0.xml").decode("utf-8")
            self.assertEqual(archive.read("Contents/header.xml"), b"<header>unchanged</header>")
            self.assertEqual(archive.read("BinData/image1.png"), b"image-data")

        self.assertEqual(filled_count, 2)
        self.assertIn("청년농업 지원", section)
        self.assertIn("홍길동", section)
        self.assertIn("신청 목적", section)
        self.assertIn("지역 농산물 가공 기반을 조성합니다.", section)

    def test_rejects_legacy_hwp_with_explicit_conversion_guidance(self) -> None:
        with self.assertRaisesRegex(TemplateInputError, "HWPX"):
            extract_template_text("application.hwp", b"legacy hwp")

    def test_rejects_malformed_hwpx_xml(self) -> None:
        with self.assertRaises(TemplateInputError):
            extract_template_text("broken.hwpx", make_hwpx(b"<!DOCTYPE x [<!ENTITY e 'x'>]><x>&e;</x>"))


if __name__ == "__main__":
    unittest.main()
