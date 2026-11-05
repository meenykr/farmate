from __future__ import annotations

import json
import unittest
from datetime import date
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from farmate import notices


class FakeResponse(BytesIO):
    status = 200


class FakeOpener:
    def __init__(self, response_body: bytes) -> None:
        self.response_body = response_body
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if request.get_method() == "GET":
            return FakeResponse(b"public listing")
        return FakeResponse(self.response_body)


def notice_row(
    code: str,
    title: str,
    *,
    start: str = "20261101",
    end: str = "20261231",
    summary: str = "",
    date_note: str = "",
    office: str = "",
) -> dict[str, str]:
    return {
        "afbzCd": code,
        "afbzNm": title,
        "bizYr": "2026",
        "bizCn": summary,
        "bizAplyBgngYmd": start,
        "bizAplyEndYmd": end,
        "bizAplyYmdNtcYn": "N",
        "bizAplyYmdIndctNm": date_note,
        "bizAtrbDtlNm": office,
        "onlnAplyPsbltyYn": "Y",
    }


class NoticeSourceTests(unittest.TestCase):
    def test_fetch_parses_official_public_result_and_builds_search_link(self) -> None:
        body = json.dumps({"bizList": [notice_row("A-1", "청년 농업 지원")]}).encode()
        opener = FakeOpener(body)
        with patch("farmate.notices.build_opener", return_value=opener):
            results = notices.fetch_notices(today=date(2026, 11, 5))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "청년 농업 지원")
        self.assertEqual(results[0].start_date, date(2026, 11, 1))
        self.assertTrue(results[0].online_application)
        self.assertEqual(
            parse_qs(urlparse(results[0].source_url).query)["bizSearch"],
            ["청년 농업 지원"],
        )
        self.assertEqual(len(opener.requests), 2)
        listing_request, _ = opener.requests[0]
        self.assertEqual(listing_request.full_url, notices.PUBLIC_LISTING_URL)
        self.assertEqual(listing_request.get_method(), "GET")
        request, _ = opener.requests[1]
        self.assertEqual(request.full_url, notices.PUBLIC_SEARCH_API)
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("Mozilla/5.0", request.get_header("User-agent"))
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("srchCnd", payload)
        self.assertIn("paging", payload)
        self.assertEqual(payload["paging"]["pageSize"], notices.MAX_RESULTS_PER_REQUEST)

    def test_fetch_caps_page_size_and_rejects_malformed_response(self) -> None:
        opener = FakeOpener(json.dumps({"bizList": "invalid"}).encode())
        with patch("farmate.notices.build_opener", return_value=opener):
            with self.assertRaises(notices.NoticeSourceError):
                notices.fetch_notices(page_size=10_000)
        payload = json.loads(opener.requests[1][0].data.decode("utf-8"))
        self.assertEqual(payload["paging"]["pageSize"], notices.MAX_RESULTS_PER_REQUEST)

    def test_fetch_reports_network_failure(self) -> None:
        opener = FakeOpener(b"")
        opener.open = unittest.mock.Mock(side_effect=URLError("offline"))
        with patch("farmate.notices.build_opener", return_value=opener):
            with self.assertRaisesRegex(notices.NoticeSourceError, "네트워크 오류"):
                notices.fetch_notices()

    def test_fetch_reports_http_restriction_without_hiding_status(self) -> None:
        opener = FakeOpener(b"")
        opener.open = unittest.mock.Mock(
            side_effect=HTTPError(
                notices.PUBLIC_LISTING_URL, 403, "Forbidden", {}, None
            )
        )
        with patch("farmate.notices.build_opener", return_value=opener):
            with self.assertRaisesRegex(notices.NoticeSourceError, "HTTP 403"):
                notices.fetch_notices()

    def test_recommendations_rank_profile_matches_exclude_expired_and_do_not_use_bank_data(self) -> None:
        notices_list = [
            notices._notice_from_row(
                notice_row(
                    "expired",
                    "청년농 복숭아 인증 지원",
                    end="20261001",
                )
            ),
            notices._notice_from_row(
                notice_row(
                    "match",
                    "청년농 복숭아 인증 지원",
                    summary="경북 청도군 영농 사업",
                )
            ),
            notices._notice_from_row(
                notice_row("other", "일반 농업 지원", summary="다른 지역"),
            ),
        ]
        profile = {
            "crop_categories": "복숭아",
            "certification_type": "친환경 인증",
            "address": "경북 청도군",
            "account_number": "청년농 복숭아 인증 지원",
            "subsidy_eligibility": "청년농",
        }

        results = notices.recommend_notices(
            [item for item in notices_list if item is not None],
            profile,
            today=date(2026, 11, 5),
        )

        self.assertEqual([item.notice.code for item in results], ["match", "other"])
        self.assertGreater(results[0].match_score, results[1].match_score)
        self.assertNotIn("계좌", results[0].matched_profile_fields)
        self.assertIn("신청기간", results[0].application_status)

    def test_unknown_date_is_kept_with_confirmation_warning(self) -> None:
        item = notices._notice_from_row(
            notice_row(
                "unknown",
                "농업 지원",
                start="",
                end="",
                date_note="접수기관문의",
            )
        )
        self.assertIsNotNone(item)
        assert item is not None
        results = notices.recommend_notices(
            [item], {}, today=date(2026, 11, 5)
        )
        self.assertEqual(len(results), 1)
        self.assertIn("확인 필요", results[0].application_status)

    def test_notice_date_flag_requires_institution_confirmation(self) -> None:
        row = notice_row(
            "confirm",
            "연중 농업 지원",
            start="20260101",
            end="20261231",
        )
        row["bizAplyYmdNtcYn"] = "Y"
        item = notices._notice_from_row(row)
        self.assertIsNotNone(item)
        assert item is not None
        results = notices.recommend_notices(
            [item], {}, today=date(2026, 11, 5)
        )
        self.assertEqual(len(results), 1)
        self.assertIn("접수기관에 문의", results[0].application_status)


if __name__ == "__main__":
    unittest.main()
