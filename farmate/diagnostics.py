from __future__ import annotations

import re


_UNEXPECTED_ARGUMENT = re.compile(
    r"got an unexpected keyword argument ['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]"
)
_MISSING_ARGUMENT = re.compile(
    r"missing \d+ required positional argument[s]?: ['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]"
)


def safe_error_detail(error: Exception) -> str:
    """Return a short diagnostic without exposing arbitrary input or credentials."""
    if isinstance(error, TypeError):
        message = str(error)
        unexpected = _UNEXPECTED_ARGUMENT.search(message)
        if unexpected:
            return f"SDK 호출에서 지원되지 않는 인자 `{unexpected.group(1)}`를 사용했습니다."
        missing = _MISSING_ARGUMENT.search(message)
        if missing:
            return f"SDK 호출에 필수 인자 `{missing.group(1)}`가 누락됐습니다."
        if "object is not callable" in message:
            return "SDK 객체를 호출하는 과정에서 호출 대상이 함수가 아닌 것으로 확인됐습니다."
        if "positional argument" in message and "given" in message:
            return "SDK 호출의 위치 인자 개수가 맞지 않습니다."
        return "호출 인자 또는 SDK 반환 타입이 예상과 다릅니다. 자세한 내용은 서버 터미널의 traceback을 확인하세요."
    return "자세한 내용은 서버 터미널의 traceback을 확인하세요."
