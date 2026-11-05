from __future__ import annotations

import html
import http.cookiejar
import json
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener
from typing import Any, Mapping

PUBLIC_LISTING_URL = "https://www.nongupez.go.kr/nsm/bizAply/wholeBiz/wholeBizMain"
PUBLIC_SEARCH_API = "https://www.nongupez.go.kr/nsm/bizAply/wholeBiz/retrieveListBizSrch"
MAX_RESULTS_PER_REQUEST = 36
MAX_RESPONSE_BYTES = 2_000_000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
NOTICE_PROFILE_FIELDS: tuple[tuple[str, str, int], ...] = (
    ("crop_categories", "재배 작물", 4),
    ("farm_type", "영농 형태", 3),
    ("certification_type", "인증 유형", 3),
    ("address", "지역", 2),
    ("parcel_location", "농지 소재지", 2),
)


class NoticeSourceError(RuntimeError):
    """The public announcement listing could not be read or parsed."""


@dataclass(frozen=True)
class Notice:
    code: str
    title: str
    summary: str
    year: str
    start_date: date | None
    end_date: date | None
    date_confirmation_required: bool
    date_note: str
    office: str
    online_application: bool | None
    source_url: str


@dataclass(frozen=True)
class NoticeRecommendation:
    notice: Notice
    match_score: int
    matched_profile_fields: tuple[str, ...]
    application_status: str


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    without_tags = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    for pattern in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(normalized, pattern).date()
        except ValueError:
            continue
    return None


def _notice_from_row(row: Mapping[str, Any]) -> Notice | None:
    code = _clean_text(row.get("afbzCd"))
    title = _clean_text(row.get("afbzNm"))
    if not code or not title:
        return None

    return Notice(
        code=code,
        title=title,
        summary=_clean_text(row.get("bizCn")),
        year=_clean_text(row.get("bizYr")),
        start_date=_parse_date(row.get("bizAplyBgngYmd")),
        end_date=_parse_date(row.get("bizAplyEndYmd")),
        date_confirmation_required=(
            row.get("bizAplyYmdNtcYn") == "Y"
            or "접수기관문의" in _clean_text(row.get("bizAplyYmdIndctNm"))
        ),
        date_note=_clean_text(row.get("bizAplyYmdIndctNm")),
        office=_clean_text(row.get("bizAtrbDtlNm")),
        online_application=(
            row.get("onlnAplyPsbltyYn") == "Y"
            if row.get("onlnAplyPsbltyYn") in ("Y", "N")
            else None
        ),
        source_url=f"{PUBLIC_LISTING_URL}?bizSearch={quote(title, safe='')}",
    )


def fetch_notices(
    *,
    today: date | None = None,
    timeout: float = 12.0,
    page_size: int = MAX_RESULTS_PER_REQUEST,
) -> list[Notice]:
    """Fetch one small page from the site's anonymous public program listing."""
    current_date = today or date.today()
    page_size = min(max(int(page_size), 1), MAX_RESULTS_PER_REQUEST)
    payload = {
        "srchCnd": {
            "srchKeyword": "",
            "srchBizYr": str(current_date.year),
            "srchAplyBgngYmd": "",
            "srchAplyEndYmd": "",
            "srchH": "",
            "srchJ1": "",
            "srchJ2": "",
            "srchA": "",
            "srchG": "",
            "srchI": "",
            "srchBizPbancExstYn": "",
            "srchOnlnAplyPsbltyYn": "",
            "sortCnd": "M",
            "srchF2": "",
            "srchKeywordCnd": "ALL",
        },
        "paging": {
            "curPage": 1,
            "pageSize": page_size,
            "totalPage": 0,
            "pageCount": 0,
        },
    }
    request = Request(
        PUBLIC_SEARCH_API,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Referer": PUBLIC_LISTING_URL,
            "Origin": "https://www.nongupez.go.kr",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    try:
        # Open the public listing first to establish the same anonymous web
        # session that the site's own frontend uses for its JSON search.
        with opener.open(
            Request(
                PUBLIC_LISTING_URL,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "User-Agent": USER_AGENT,
                },
            ),
            timeout=timeout,
        ) as listing_response:
            if not 200 <= getattr(listing_response, "status", 200) < 300:
                raise NoticeSourceError(
                    "농업e지 공개 목록 페이지가 정상 응답하지 않았습니다."
                )
            listing_response.read(MAX_RESPONSE_BYTES + 1)

        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise NoticeSourceError(f"농업e지 공고 목록 요청이 HTTP {status}로 실패했습니다.")
            response_bytes = response.read(MAX_RESPONSE_BYTES + 1)
    except NoticeSourceError:
        raise
    except HTTPError as exc:
        raise NoticeSourceError(
            f"농업e지 공개 목록 요청이 HTTP {exc.code}으로 거부되었습니다."
        ) from exc
    except (URLError, TimeoutError, OSError, ssl.SSLError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.gaierror):
            message = "Codespace에서 농업e지 도메인을 찾지 못했습니다(DNS 오류)."
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            message = "농업e지 연결 시간이 초과되었습니다."
        elif isinstance(reason, ssl.SSLError):
            message = "농업e지 HTTPS 인증서 연결에 실패했습니다(TLS 오류)."
        else:
            detail = str(reason).replace("\r", " ").replace("\n", " ")[:180]
            message = (
                "농업e지 공개 목록 연결에 실패했습니다. "
                f"네트워크 오류: {type(reason).__name__}: {detail or '세부 원인 없음'}"
            )
        raise NoticeSourceError(message) from exc

    if len(response_bytes) > MAX_RESPONSE_BYTES:
        raise NoticeSourceError("농업e지 공고 응답이 허용 크기를 초과했습니다.")
    try:
        result = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NoticeSourceError("농업e지 공고 응답을 읽을 수 없습니다.") from exc
    if not isinstance(result, dict) or not isinstance(result.get("bizList"), list):
        raise NoticeSourceError("농업e지 공고 응답 형식이 예상과 다릅니다.")

    notices = [
        notice
        for row in result["bizList"]
        if isinstance(row, dict)
        if (notice := _notice_from_row(row)) is not None
    ]
    return notices


def _profile_terms(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    return tuple(dict.fromkeys(re.findall(r"[가-힣A-Za-z0-9]{2,}", value.casefold())))


def _application_status(notice: Notice, today: date) -> str | None:
    if notice.end_date and notice.end_date < today:
        return None
    if notice.date_confirmation_required:
        return (
            f"일정 확인 필요 · {notice.date_note}"
            if notice.date_note
            else "일정 확인 필요 · 접수기관에 문의하세요"
        )
    if notice.start_date and notice.start_date > today:
        if notice.date_note:
            return f"예정 · {notice.date_note}"
        return "신청 예정"
    if notice.start_date and notice.end_date:
        if notice.date_note:
            return f"기간 표기 내 · {notice.date_note}"
        return "사이트 표기상 신청기간"
    if notice.date_note:
        return f"일정 확인 필요 · {notice.date_note}"
    return "정확한 일정 확인 필요"


def recommend_notices(
    notices: list[Notice],
    profile: Mapping[str, Any],
    *,
    today: date | None = None,
    limit: int = 5,
) -> list[NoticeRecommendation]:
    current_date = today or date.today()
    matches: list[NoticeRecommendation] = []
    for notice in notices:
        status = _application_status(notice, current_date)
        if status is None:
            continue

        source_text = f"{notice.title} {notice.summary} {notice.office}".casefold()
        score = 0
        matched_fields: list[str] = []
        for field_key, label, weight in NOTICE_PROFILE_FIELDS:
            terms = _profile_terms(profile.get(field_key, ""))
            field_matched = False
            for term in terms:
                if term in source_text:
                    score += weight
                    field_matched = True
            if field_matched:
                matched_fields.append(label)
        matches.append(
            NoticeRecommendation(
                notice=notice,
                match_score=score,
                matched_profile_fields=tuple(matched_fields),
                application_status=status,
            )
        )

    matches.sort(
        key=lambda item: (
            -item.match_score,
            item.notice.end_date or date.max,
            item.notice.title,
        )
    )
    return matches[: max(0, limit)]
