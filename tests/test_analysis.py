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

    async def test_rejects_empty_applicant_information(self) -> None:
        with self.assertRaisesRegex(AnalysisError, "신청자 정보를 입력"):
            await analyze_announcement(
                StubAgent(json.dumps(valid_result(), ensure_ascii=False)),
                [PdfPage(number=1, text="신청일 기준 만 18세 이상 40세 미만. 사업계획서 1부.")],
                "  ",
            )


if __name__ == "__main__":
    unittest.main()
