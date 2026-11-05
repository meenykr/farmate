from __future__ import annotations

import asyncio
import hashlib
import logging

import streamlit as st

from farmate.agent import create_agent
from farmate.analysis import AnalysisError, AnalysisResult, analyze_announcement
from farmate.pdf import PdfInputError, PdfPage, extract_pdf_pages

LOGGER = logging.getLogger(__name__)


async def run_analysis(pages: list[PdfPage], applicant_information: str) -> AnalysisResult:
    async with create_agent() as agent:
        return await analyze_announcement(agent, pages, applicant_information)


st.set_page_config(page_title="FARMATE", page_icon="🌱", layout="wide")
st.title("🌱 FARMATE")
st.caption("농업 지원사업 공고를 읽고 신청 준비를 돕는 AI 에이전트")
st.warning(
    "AI 결과는 참고용이며 공식 자격 판정이 아닙니다. 제출 전 담당자가 원문과 신청서를 확인해야 합니다."
)
st.info(
    "분석을 시작하면 PDF 텍스트와 신청자 정보가 GitHub Copilot 서비스로 전송됩니다. "
    "민감한 식별정보는 입력하지 마세요. 업로드 파일은 저장하지 않습니다."
)

uploaded_pdf = st.file_uploader("지원사업 공고 PDF", type=["pdf"])
pdf_bytes = uploaded_pdf.getvalue() if uploaded_pdf else None
applicant_information = st.text_area(
    "신청자 정보",
    placeholder="예: 경북 청도군 거주, 만 32세, 농업경영체 등록 완료, 복숭아 재배 3년, 청년농업인...",
    height=150,
)
consent = st.checkbox("PDF와 신청자 정보를 AI 분석을 위해 GitHub Copilot으로 전송하는 데 동의합니다.")
input_fingerprint = (
    hashlib.sha256(pdf_bytes + b"\0" + applicant_information.encode("utf-8")).hexdigest()
    if pdf_bytes is not None
    else None
)

if st.button("공고 분석 및 초안 만들기", type="primary", disabled=not (uploaded_pdf and consent)):
    st.session_state.pop("farmate_result", None)
    if not applicant_information.strip():
        st.error("신청자 정보를 입력해 주세요.")
    else:
        try:
            pages = extract_pdf_pages(pdf_bytes)
        except PdfInputError as exc:
            st.error(str(exc))
        else:
            with st.spinner("공고 요건을 분석하고 있습니다..."):
                try:
                    result = asyncio.run(run_analysis(pages, applicant_information))
                except AnalysisError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    LOGGER.exception("FARMATE Copilot analysis failed")
                    st.error(
                        f"Copilot 분석에 실패했습니다 ({type(exc).__name__}). "
                        "Copilot CLI 로그인 또는 COPILOT_GITHUB_TOKEN, 네트워크, "
                        "GitHub Copilot 구독 권한을 확인한 뒤 다시 시도해 주세요."
                    )
                else:
                    st.session_state["farmate_result"] = result
                    st.session_state["farmate_result_fingerprint"] = input_fingerprint

result = st.session_state.get("farmate_result")
if (
    consent
    and isinstance(result, AnalysisResult)
    and input_fingerprint == st.session_state.get("farmate_result_fingerprint")
):
    st.header(result.program_name)
    st.subheader("지원 대상")
    if result.target_applicants:
        st.markdown("\n".join(f"- {target}" for target in result.target_applicants))
    else:
        st.write("공고에서 지원 대상을 추출하지 못했습니다.")

    st.subheader("자격 조건 잠정 검토")
    if result.eligibility:
        st.dataframe(
            [
                {
                    "조건": item.requirement,
                    "잠정 상태": item.status.value,
                    "신청자 정보": item.applicant_basis,
                    "원문 근거": f'{item.source_page}쪽: "{item.source_quote}"',
                }
                for item in result.eligibility
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("자격 조건을 추출하지 못했습니다.")

    st.subheader("제출 서류 확인 목록")
    if result.required_documents:
        st.dataframe(
            [
                {
                    "서류": item.name,
                    "확인 상태": item.status.value,
                    "신청자 정보": item.applicant_basis,
                    "원문 근거": f'{item.source_page}쪽: "{item.source_quote}"',
                }
                for item in result.required_documents
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("필수 서류를 추출하지 못했습니다.")

    st.subheader("추가 확인 질문")
    if result.follow_up_questions:
        for question in result.follow_up_questions:
            st.markdown(f"- {question}")
    else:
        st.write("추가 확인 질문이 없습니다.")

    st.subheader("신청서 초안")
    st.text_area("초안 (검토 및 수정 필요)", value=result.application_draft, height=280)
elif uploaded_pdf and consent and result is not None:
    st.info("입력한 공고나 신청자 정보가 바뀌었습니다. 변경된 내용으로 다시 분석해 주세요.")
