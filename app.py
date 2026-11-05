from __future__ import annotations

import asyncio
import hashlib
import logging

import streamlit as st

from farmate.agent import create_agent
from farmate.analysis import AnalysisError, AnalysisResult, analyze_announcement
from farmate.diagnostics import safe_error_detail
from farmate.pdf import PdfInputError, PdfPage, extract_pdf_pages
from farmate.templates import (
    MAX_TEMPLATE_TEXT,
    TemplateInputError,
    extract_template_text,
    fill_hwpx_template,
)

LOGGER = logging.getLogger(__name__)
RESULT_KEY = "farmate_result"
HISTORY_KEY = "farmate_history"
FINGERPRINT_KEY = "farmate_fingerprint"
APPLICANT_KEY = "farmate_applicant"
TEMPLATE_TEXT_KEY = "farmate_template_text"
DRAFT_KEY = "farmate_draft_editor"


async def run_analysis(
    pages: list[PdfPage],
    applicant_information: str,
    application_template: str,
    conversation_history: list[dict[str, str]],
) -> AnalysisResult:
    async with create_agent() as agent:
        return await analyze_announcement(
            agent,
            pages,
            applicant_information,
            application_template=application_template,
            conversation_history=conversation_history,
        )


def _fingerprint(pdf_bytes: bytes | None, template_bytes: bytes | None, applicant_info: str) -> str:
    digest = hashlib.sha256()
    digest.update(pdf_bytes or b"")
    digest.update(b"\0template\0")
    digest.update(template_bytes or b"")
    digest.update(b"\0applicant\0")
    digest.update(applicant_info.encode("utf-8"))
    return digest.hexdigest()


def _clear_application_state() -> None:
    for key in (
        RESULT_KEY,
        HISTORY_KEY,
        FINGERPRINT_KEY,
        APPLICANT_KEY,
        TEMPLATE_TEXT_KEY,
        DRAFT_KEY,
    ):
        st.session_state.pop(key, None)


st.set_page_config(page_title="FARMATE", page_icon="🌱", layout="wide")
st.title("🌱 FARMATE")
st.caption("공고 분석부터 질문 답변, HWPX 신청서 초안까지 함께 작성하는 AI 농업 행정 에이전트")
st.warning(
    "AI 결과는 공식 자격 판정이 아닙니다. 자격·인용·작성 내용을 원문과 대조하고 제출 전 담당자가 검토해야 합니다."
)
st.info(
    "분석 동의 후 공고 PDF, 신청자 정보, 업로드한 신청서 양식의 추출 텍스트와 대화 내용이 "
    "GitHub Copilot 서비스로 전송됩니다. 민감한 식별정보는 입력하지 마세요. 업로드 파일을 앱 서버에 저장하지 않습니다."
)

uploaded_pdf = st.file_uploader("지원사업 공고 PDF", type=["pdf"])
uploaded_template = st.file_uploader(
    "작성할 신청서 양식 (편집된 결과 다운로드는 HWPX만 지원)",
    type=["hwp", "hwpx"],
    help="구형 .hwp 파일은 한글에서 .hwpx로 변환해 업로드하세요.",
)
applicant_information = st.text_area(
    "신청자 기본 정보",
    placeholder="예: 경북 청도군 거주, 만 32세, 농업경영체 등록, 복숭아 재배 3년, 청년농업인",
    height=120,
)
consent = st.checkbox(
    "공고 PDF, 신청자 정보, 신청서 양식과 대화 내용을 GitHub Copilot으로 전송하는 데 동의합니다."
)

pdf_bytes = uploaded_pdf.getvalue() if uploaded_pdf else None
template_bytes = uploaded_template.getvalue() if uploaded_template else None
current_fingerprint = (
    _fingerprint(pdf_bytes, template_bytes, applicant_information) if pdf_bytes is not None else None
)

if not consent:
    _clear_application_state()
elif current_fingerprint != st.session_state.get(FINGERPRINT_KEY):
    _clear_application_state()

if st.button(
    "공고 분석 및 대화 시작",
    type="primary",
    disabled=not (uploaded_pdf and uploaded_template and consent),
):
    try:
        pages = extract_pdf_pages(pdf_bytes or b"")
        template_text = extract_template_text(
            uploaded_template.name if uploaded_template else "",
            template_bytes or b"",
        )
        if not applicant_information.strip():
            raise AnalysisError("신청자 기본 정보를 입력해 주세요.")
    except (PdfInputError, TemplateInputError, AnalysisError) as exc:
        st.error(str(exc))
    else:
        with st.spinner("공고와 양식 항목을 읽고 첫 확인 질문을 준비하고 있습니다..."):
            try:
                result = asyncio.run(
                    run_analysis(pages, applicant_information, template_text, [])
                )
            except AnalysisError as exc:
                st.error(str(exc))
            except Exception as exc:
                LOGGER.exception("FARMATE Copilot analysis failed")
                st.error(
                    f"Copilot 분석에 실패했습니다 ({type(exc).__name__}). "
                    f"{safe_error_detail(exc)} "
                    "인증 오류라고 단정할 수 없습니다. Codespaces 터미널 traceback을 확인하세요."
                )
            else:
                first_question = (
                    result.follow_up_questions[0]
                    if result.follow_up_questions
                    else "추가 확인 질문이 없습니다. 신청서에 보완할 내용이 있으면 계속 입력해 주세요."
                )
                st.session_state[RESULT_KEY] = result
                st.session_state[HISTORY_KEY] = [
                    {"role": "assistant", "content": first_question}
                ]
                st.session_state[FINGERPRINT_KEY] = current_fingerprint
                st.session_state[APPLICANT_KEY] = applicant_information
                st.session_state[TEMPLATE_TEXT_KEY] = template_text
                st.session_state[DRAFT_KEY] = result.application_draft

result = st.session_state.get(RESULT_KEY)
history = st.session_state.get(HISTORY_KEY, [])
if (
    consent
    and isinstance(result, AnalysisResult)
    and current_fingerprint == st.session_state.get(FINGERPRINT_KEY)
):
    st.header(result.program_name)
    st.caption("현재 분석은 참고용입니다. 확인된 정보가 늘어날 때마다 조건과 신청서 초안을 갱신합니다.")

    st.subheader("양식 항목")
    template_text = st.session_state[TEMPLATE_TEXT_KEY]
    with st.expander("업로드한 신청서 양식에서 추출한 항목 보기"):
        st.text(template_text[:MAX_TEMPLATE_TEXT])

    st.subheader("자격 조건 잠정 검토")
    if result.eligibility:
        st.dataframe(
            [
                {
                    "조건": item.requirement,
                    "잠정 상태": item.status.value,
                    "신청자 정보": item.applicant_basis,
                    "공고 원문": f'{item.source_page}쪽: "{item.source_quote}"',
                }
                for item in result.eligibility
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("공고에서 자격 조건을 추출하지 못했습니다.")

    st.subheader("제출 서류 확인")
    if result.required_documents:
        st.dataframe(
            [
                {
                    "서류": item.name,
                    "상태": item.status.value,
                    "신청자 정보": item.applicant_basis,
                    "공고 원문": f'{item.source_page}쪽: "{item.source_quote}"',
                }
                for item in result.required_documents
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("공고에서 제출 서류를 추출하지 못했습니다.")

    st.subheader("신청서 작성 대화")
    for turn in history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    chat_answer = st.chat_input("확인 질문에 답하거나 신청서에 추가할 정보를 입력하세요")
    if chat_answer:
        updated_history = [*history, {"role": "user", "content": chat_answer}]
        with st.spinner("답변을 반영해 자격, 누락 질문과 신청서 초안을 갱신하고 있습니다..."):
            try:
                pages = extract_pdf_pages(pdf_bytes or b"")
                updated_result = asyncio.run(
                    run_analysis(
                        pages,
                        st.session_state[APPLICANT_KEY],
                        template_text,
                        updated_history,
                    )
                )
            except (AnalysisError, PdfInputError) as exc:
                st.error(str(exc))
            except Exception as exc:
                LOGGER.exception("FARMATE conversational update failed")
                st.error(
                    f"답변 반영에 실패했습니다 ({type(exc).__name__}). "
                    f"{safe_error_detail(exc)} "
                    "인증 오류라고 단정할 수 없습니다."
                )
            else:
                next_question = (
                    updated_result.follow_up_questions[0]
                    if updated_result.follow_up_questions
                    else "현재 입력으로 추가 질문이 없습니다. 더 보완할 내용을 입력하거나 초안을 검토하세요."
                )
                updated_history.append({"role": "assistant", "content": next_question})
                st.session_state[RESULT_KEY] = updated_result
                st.session_state[HISTORY_KEY] = updated_history
                st.session_state[DRAFT_KEY] = updated_result.application_draft
                st.rerun()

    st.subheader("신청서 초안")
    st.text_area(
        "확인된 정보와 대화 답변을 반영한 초안 (검토·수정 필요)",
        value=result.application_draft,
        height=360,
        key=DRAFT_KEY,
    )
    if result.template_fields:
        st.subheader("양식에 채울 수 있는 항목")
        st.dataframe(
            [{"양식 항목": label, "확인된 내용": value} for label, value in result.template_fields.items()],
            use_container_width=True,
            hide_index=True,
        )
    elif result.follow_up_questions:
        st.info("미확인 항목이 남아 있습니다. 질문에 답하면 초안과 양식 값이 갱신됩니다.")

    if uploaded_template and uploaded_template.name.lower().endswith(".hwpx"):
        try:
            completed_hwpx, filled_fields = fill_hwpx_template(
                uploaded_template.name,
                template_bytes or b"",
                result.template_fields,
                st.session_state.get(DRAFT_KEY, result.application_draft),
            )
        except TemplateInputError as exc:
            st.error(str(exc))
        else:
            if filled_fields:
                st.success(f"양식 내 자리표시자/빈 표 항목 {filled_fields}개를 채우고, 전체 초안을 문서 끝에 덧붙였습니다.")
            else:
                st.info("양식 내 인식 가능한 항목은 없어 원본을 보존하고 전체 초안을 문서 끝에 덧붙였습니다.")
            st.download_button(
                "작성된 HWPX 신청서 다운로드",
                data=completed_hwpx,
                file_name=f"{uploaded_template.name.rsplit('.', 1)[0]}_farmate.hwpx",
                mime="application/vnd.hancom.hwpx",
                type="primary",
            )
    elif uploaded_template:
        st.warning(
            "구형 .hwp 양식은 업로드했지만 편집된 .hwp 저장은 지원하지 않습니다. "
            "한글에서 HWPX로 변환한 양식을 업로드해야 작성된 HWPX를 다운로드할 수 있습니다."
        )
