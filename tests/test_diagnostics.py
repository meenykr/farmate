from __future__ import annotations

import unittest

from farmate.diagnostics import safe_error_detail


class SafeErrorDetailTests(unittest.TestCase):
    def test_reports_unsupported_sdk_argument_without_echoing_full_error(self) -> None:
        detail = safe_error_detail(
            TypeError("run() got an unexpected keyword argument 'session_id'")
        )
        self.assertIn("session_id", detail)
        self.assertNotIn("unexpected keyword argument", detail)

    def test_reports_missing_sdk_argument(self) -> None:
        detail = safe_error_detail(
            TypeError("run() missing 1 required positional argument: 'messages'")
        )
        self.assertIn("messages", detail)
        self.assertIn("누락", detail)

    def test_hides_unrecognized_type_error_text(self) -> None:
        private_value = "농장주 이름: 홍길동"
        detail = safe_error_detail(TypeError(private_value))
        self.assertNotIn(private_value, detail)
        self.assertIn("traceback", detail)

    def test_non_type_error_does_not_expose_exception_text(self) -> None:
        detail = safe_error_detail(RuntimeError("private request body"))
        self.assertNotIn("private request body", detail)
        self.assertIn("traceback", detail)


if __name__ == "__main__":
    unittest.main()
