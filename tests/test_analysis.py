from __future__ import annotations

import json
import unittest

from farmate.analysis import (
    AnalysisError,
    analyze_announcement,
)
from farmate.pdf import PdfPage


class StubAgent:
    def __init__(self, response_text: str) -> None:
        self.response = type("Response", (), {"text": response_text})()
        self.prompt = ""

    async def run(self, prompt: str) -> object:
        self.prompt = prompt
        return self.response


def valid_result() -> dict[str, object]:
    return {
        "program_name": "청년농업인 지원사업",
        "target_applicants": ["청년농업인"],
        "eligibility": [
            {
                "requirement": "만 18세 이상 40세 미만",
                "status": "확인 필요",
                "applicant_basis": "나이 확인 필요",
                "source_page": 1,
                "source_quote": "신청일 기준 만 18세 이상 40세 미만",
            }
        ],
        "required_documents": [
            {
                "name": "사업계획서",
                "status": "확인 필요",
                "applicant_basis": "보유 여부 확인 필요",
                "source_page": 1,
                "source_quote": "사업계획서 1부",
            }
        ],
        "follow_up_questions": ["현재 만 나이를 알려주세요."],
        "application_draft": "사업계획: [추가 입력 필요]",
    }


class AnalyzeAnnouncementTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_json_with_grounded_citations_is_parsed(self) -> None:
        agent = StubAgent(json.dumps(valid_result(), ensure_ascii=False))
        pages = [
            PdfPage(
                number=1,
                text="신청일 기준 만 18세 이상 40세 미만인 청년농업인. 사업계획서 1부 제출.",
            )
        ]

        result = await analyze_announcement(agent, pages, "경북 청도군 거주")

        self.assertEqual(result.program_name, "청년농업인 지원사업")
        self.assertEqual(result.eligibility[0].status.value, "확인 필요")
        self.assertIn("신뢰할 수 없는 입력", agent.prompt)

    async def test_rejects_citation_not_in_source_page(self) -> None:
        response = valid_result()
        response["eligibility"] = [
            {
                **valid_result()["eligibility"][0],
                "source_quote": "지원 대상은 누구나 가능",
            }
        ]
        agent = StubAgent(json.dumps(response, ensure_ascii=False))

        with self.assertRaisesRegex(AnalysisError, "원문에서 확인"):
            await analyze_announcement(
                agent,
                [PdfPage(number=1, text="신청일 기준 만 18세 이상 40세 미만")],
                "청도군 거주",
            )

    async def test_accepts_ocr_line_break_and_spacing_variations(self) -> None:
        response = valid_result()
        response["eligibility"] = [
            {
                **valid_result()["eligibility"][0],
                "source_quote": "신 청 일기준 만18세 이상 40세 미만",
            }
        ]
        response["required_documents"] = [
            {
                **valid_result()["required_documents"][0],
                "source_page": 2,
                "source_quote": "사업계획서 1부 제출",
            }
        ]
        agent = StubAgent(json.dumps(response, ensure_ascii=False))

        result = await analyze_announcement(
            agent,
            [
                PdfPage(number=1, text="신청일 기준 만 18세 이상\n40세 미만"),
                PdfPage(number=2, text="사업계획서 1부 제출"),
            ],
            "청도군 거주",
        )

        self.assertEqual(result.eligibility[0].source_page, 1)
        self.assertIn("[PAGE 1]", agent.prompt)
        self.assertIn("[PAGE 2]", agent.prompt)

    async def test_accepts_hyphenated_line_wrap_from_pdf(self) -> None:
        response = valid_result()
        response["eligibility"] = [
            {
                **valid_result()["eligibility"][0],
                "requirement": "Applicant must be a farmhouse resident",
                "applicant_basis": "residence requires confirmation",
                "source_quote": "eligible farmhouse residents",
            }
        ]
        response["required_documents"] = []
        agent = StubAgent(json.dumps(response, ensure_ascii=False))

        await analyze_announcement(
            agent,
            [
                PdfPage(
                    number=1,
                    text="eligible farm-\nhouse residents with registered farmland",
                )
            ],
            "청도군 거주",
        )

    async def test_spacing_normalization_does_not_allow_unquoted_claims(self) -> None:
        response = valid_result()
        response["eligibility"] = [
            {
                **valid_result()["eligibility"][0],
                "source_quote": "신청일 기준 100세까지 지원",
            }
        ]
        agent = StubAgent(json.dumps(response, ensure_ascii=False))

        with self.assertRaisesRegex(AnalysisError, "원문에서 확인"):
            await analyze_announcement(
                agent,
                [PdfPage(number=1, text="신청일 기준 만 18세 이상 40세 미만")],
                "청도군 거주",
            )

    async def test_rejects_empty_applicant_information(self) -> None:
        with self.assertRaisesRegex(AnalysisError, "신청자 정보를 입력"):
            await analyze_announcement(
                StubAgent(json.dumps(valid_result(), ensure_ascii=False)),
                [PdfPage(number=1, text="신청일 기준 만 18세 이상 40세 미만. 사업계획서 1부.")],
                "  ",
            )

    async def test_answer_turn_updates_analysis_with_template_and_history(self) -> None:
        initial = valid_result()
        updated = valid_result()
        updated["eligibility"] = [
            {
                **valid_result()["eligibility"][0],
                "status": "충족",
                "applicant_basis": "신청자가 만 32세라고 답변함",
            }
        ]
        updated["follow_up_questions"] = []
        updated["template_fields"] = {"성명": "홍길동"}

        class TurnAgent:
            def __init__(self) -> None:
                self.prompts: list[str] = []
                self.responses = [initial, updated]

            async def run(self, prompt: str) -> object:
                self.prompts.append(prompt)
                response = type(
                    "Response",
                    (),
                    {"text": json.dumps(self.responses.pop(0), ensure_ascii=False)},
                )()
                return response

        agent = TurnAgent()
        pages = [
            PdfPage(
                number=1,
                text="신청일 기준 만 18세 이상 40세 미만. 사업계획서 1부 제출.",
            )
        ]
        first = await analyze_announcement(
            agent, pages, "경북 청도군 거주", "성명\n만 나이"
        )
        history = [
            {"role": "assistant", "content": "현재 만 나이는 몇 세인가요?"},
            {"role": "user", "content": "만 32세입니다."},
        ]
        second = await analyze_announcement(
            agent,
            pages,
            "경북 청도군 거주",
            "성명\n만 나이",
            conversation_history=history,
        )

        self.assertEqual(first.eligibility[0].status.value, "확인 필요")
        self.assertEqual(second.eligibility[0].status.value, "충족")
        self.assertEqual(second.template_fields["성명"], "홍길동")
        self.assertIn("성명\n만 나이", agent.prompts[0])
        self.assertIn("만 32세입니다.", agent.prompts[1])
        self.assertIn("<application_template_fields", agent.prompts[1])


if __name__ == "__main__":
    unittest.main()
