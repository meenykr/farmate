from __future__ import annotations

import copy
import re
import zipfile
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_TEMPLATE_BYTES = 20 * 1024 * 1024
MAX_TEMPLATE_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_TEMPLATE_TEXT = 30_000
MAX_TEMPLATE_ENTRIES = 2_000
PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


class TemplateInputError(ValueError):
    """An uploaded application template cannot be safely read or filled."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _register_namespaces(xml_bytes: bytes) -> None:
    for _, namespace in SafeET.iterparse(BytesIO(xml_bytes), events=("start-ns",)):
        prefix, uri = namespace
        if prefix != "xml":
            ET.register_namespace(prefix, uri)


def _section_names(archive: zipfile.ZipFile) -> list[str]:
    sections = sorted(
        name
        for name in archive.namelist()
        if re.fullmatch(r"Contents/section\d+\.xml", name)
    )
    if not sections:
        raise TemplateInputError("HWPX 양식에 읽을 수 있는 본문(section)이 없습니다.")
    return sections


def _read_hwpx(data: bytes) -> tuple[list[tuple[str, bytes]], str]:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_TEMPLATE_ENTRIES:
                raise TemplateInputError("HWPX 양식에 파일이 너무 많이 포함되어 있습니다.")
            if sum(item.file_size for item in infos) > MAX_TEMPLATE_ARCHIVE_BYTES:
                raise TemplateInputError("압축 해제된 HWPX 양식이 허용 크기를 초과합니다.")
            section_xml = [(name, archive.read(name)) for name in _section_names(archive)]

            parts: list[str] = []
            for name, xml_bytes in section_xml:
                if len(xml_bytes) > MAX_TEMPLATE_BYTES:
                    raise TemplateInputError(f"{name} 본문 XML이 너무 큽니다.")
                _register_namespaces(xml_bytes)
                root = SafeET.fromstring(xml_bytes)
                parts.extend(
                    element.text
                    for element in root.iter()
                    if _local_name(element.tag) == "t" and element.text
                )
            return section_xml, "\n".join(parts)
    except TemplateInputError:
        raise
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError, DefusedXmlException) as exc:
        raise TemplateInputError("HWPX 양식을 읽지 못했습니다. 파일 형식을 확인하세요.") from exc


def extract_template_text(filename: str, data: bytes) -> str:
    if not data:
        raise TemplateInputError("신청서 양식 파일이 비어 있습니다.")
    if len(data) > MAX_TEMPLATE_BYTES:
        raise TemplateInputError("신청서 양식 파일은 20MB 이하만 처리할 수 있습니다.")

    extension = PurePosixPath(filename.lower()).suffix
    if extension == ".hwp":
        raise TemplateInputError(
            "구형 .hwp 양식은 이 앱에서 편집된 파일로 저장할 수 없습니다. "
            "한글에서 HWPX 형식으로 변환해 다시 업로드하세요."
        )
    if extension != ".hwpx":
        raise TemplateInputError("편집 가능한 신청서 출력에는 HWPX 양식이 필요합니다.")

    _, text = _read_hwpx(data)
    text = text.strip()
    if not text:
        raise TemplateInputError(
            "양식에서 텍스트를 추출하지 못했습니다. 이미지 전용 양식은 지원하지 않습니다."
        )
    if len(text) > MAX_TEMPLATE_TEXT:
        raise TemplateInputError("양식 텍스트가 너무 깁니다. 30,000자 이하 파일을 사용하세요.")
    return text


def _normalized_label(text: str) -> str:
    return re.sub(r"[\s:：·•_-]+", "", text).strip()


def _fill_text_nodes(root: ET.Element, fields: dict[str, str]) -> int:
    normalized_fields = {_normalized_label(key): value for key, value in fields.items()}
    replaced = 0
    for element in root.iter():
        if _local_name(element.tag) != "t" or not element.text:
            continue

        def substitute(match: re.Match[str]) -> str:
            nonlocal replaced
            value = normalized_fields.get(_normalized_label(match.group(1)))
            if value is not None:
                replaced += 1
                return value
            return match.group(0)

        element.text = PLACEHOLDER.sub(substitute, element.text)
    return replaced


def _fill_labeled_table_cells(root: ET.Element, fields: dict[str, str]) -> int:
    normalized_fields = {_normalized_label(key): value for key, value in fields.items()}
    replaced = 0
    for row in (node for node in root.iter() if _local_name(node.tag) == "tr"):
        cells = [child for child in list(row) if _local_name(child.tag) == "tc"]
        for index, cell in enumerate(cells[:-1]):
            label = _normalized_label(
                "".join(
                    element.text or ""
                    for element in cell.iter()
                    if _local_name(element.tag) == "t"
                )
            )
            value = normalized_fields.get(label)
            if value is None:
                continue
            destination = cells[index + 1]
            destination_text_nodes = [
                element for element in destination.iter() if _local_name(element.tag) == "t"
            ]
            if any((element.text or "").strip() for element in destination_text_nodes):
                continue
            if destination_text_nodes:
                destination_text_nodes[0].text = value
            else:
                run = next(
                    (element for element in destination.iter() if _local_name(element.tag) == "run"),
                    None,
                )
                if run is None:
                    continue
                text_tag = f"{{{run.tag.split('}')[0][1:]}}}t" if "}" in run.tag else "t"
                ET.SubElement(run, text_tag).text = value
            replaced += 1
    return replaced


def _append_draft(root: ET.Element, draft: str) -> int:
    sections = [node for node in root.iter() if _local_name(node.tag) == "sec"]
    if not sections:
        raise TemplateInputError("HWPX 본문에서 신청서 초안을 추가할 위치를 찾지 못했습니다.")
    section = sections[-1]
    paragraph_tag = next(
        (node.tag for node in section.iter() if _local_name(node.tag) == "p"),
        None,
    )
    if paragraph_tag is None:
        raise TemplateInputError("HWPX 양식에 초안을 추가할 문단 구조가 없습니다.")
    prototype = next(node for node in section.iter() if node.tag == paragraph_tag)
    existing_ids = [
        int(node.attrib["id"])
        for node in root.iter()
        if _local_name(node.tag) == "p"
        and node.attrib.get("id", "").isdigit()
    ]
    next_id = max(existing_ids, default=0) + 1
    paragraph_namespace = paragraph_tag.split("}")[0] + "}" if "}" in paragraph_tag else ""
    run_tag = f"{paragraph_namespace}run"
    text_tag = f"{paragraph_namespace}t"
    run_prototype = next(
        (node for node in prototype.iter() if _local_name(node.tag) == "run"),
        None,
    )
    if run_prototype is None:
        raise TemplateInputError("HWPX 양식에서 문단 서식을 복사할 수 없습니다.")

    lines = draft.splitlines() or [draft]
    paragraphs: list[ET.Element] = []
    for line in lines:
        paragraph = copy.deepcopy(prototype)
        paragraph.attrib["id"] = str(next_id)
        next_id += 1
        runs = [node for node in paragraph.iter() if _local_name(node.tag) == "run"]
        if not runs:
            run = ET.SubElement(paragraph, run_tag)
            ET.SubElement(run, text_tag).text = line
        else:
            first_text = next(
                (node for node in runs[0].iter() if _local_name(node.tag) == "t"),
                None,
            )
            for node in paragraph.iter():
                if _local_name(node.tag) == "t":
                    node.text = ""
            if first_text is None:
                ET.SubElement(runs[0], text_tag).text = line
            else:
                first_text.text = line
        paragraphs.append(paragraph)

    insertion_index = len(section)
    if insertion_index and _local_name(section[-1].tag) == "ctrl":
        insertion_index -= 1
    for paragraph in paragraphs:
        section.insert(insertion_index, paragraph)
        insertion_index += 1
    return len(paragraphs)


def fill_hwpx_template(
    filename: str,
    data: bytes,
    fields: dict[str, str],
    application_draft: str,
) -> tuple[bytes, int]:
    if PurePosixPath(filename.lower()).suffix != ".hwpx":
        raise TemplateInputError("편집된 지원서를 만들려면 HWPX 양식을 업로드하세요.")
    if not data or len(data) > MAX_TEMPLATE_BYTES:
        raise TemplateInputError("HWPX 양식 파일은 20MB 이하만 처리할 수 있습니다.")
    if len(application_draft.strip()) == 0:
        raise TemplateInputError("저장할 신청서 초안이 비어 있습니다.")

    sections, _ = _read_hwpx(data)
    modified_sections: dict[str, bytes] = {}
    filled_fields = 0
    for name, xml_bytes in sections:
        _register_namespaces(xml_bytes)
        root = SafeET.fromstring(xml_bytes)
        filled_fields += _fill_text_nodes(root, fields)
        filled_fields += _fill_labeled_table_cells(root, fields)
        _append_draft(root, application_draft)
        modified_sections[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    output = BytesIO()
    try:
        with zipfile.ZipFile(BytesIO(data)) as source, zipfile.ZipFile(output, "w") as target:
            for info in source.infolist():
                contents = modified_sections.get(info.filename)
                if contents is None:
                    contents = source.read(info.filename)
                target.writestr(info, contents)
    except (zipfile.BadZipFile, OSError) as exc:
        raise TemplateInputError("HWPX 결과 파일을 생성하지 못했습니다.") from exc
    return output.getvalue(), filled_fields
