from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from streamlit.testing.v1 import AppTest

from farmate.notices import Notice
from farmate.profiles import ProfileStore


class ProfileAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "app-profiles.sqlite3"
        self.key = Fernet.generate_key().decode("ascii")
        self.previous_db_path = os.environ.get("FARMATE_PROFILE_DB")
        self.previous_key = os.environ.get("FARMATE_PROFILE_ENCRYPTION_KEY")
        os.environ["FARMATE_PROFILE_DB"] = str(self.database_path)
        os.environ["FARMATE_PROFILE_ENCRYPTION_KEY"] = self.key

    def tearDown(self) -> None:
        if self.previous_db_path is None:
            os.environ.pop("FARMATE_PROFILE_DB", None)
        else:
            os.environ["FARMATE_PROFILE_DB"] = self.previous_db_path
        if self.previous_key is None:
            os.environ.pop("FARMATE_PROFILE_ENCRYPTION_KEY", None)
        else:
            os.environ["FARMATE_PROFILE_ENCRYPTION_KEY"] = self.previous_key
        self.temp_dir.cleanup()

    def test_registration_login_and_profile_fields_autofill(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)

        app.text_input(key="farmate_register_email").set_value("farmer@example.com")
        app.text_input(key="farmate_register_password").set_value("strong-password-123")
        app.text_input(key="farmate_register_confirm").set_value("strong-password-123")
        next(button for button in app.button if button.label == "계정 만들기").click().run()
        self.assertEqual(len(app.exception), 0)

        next(button for button in app.button if button.label == "신청서 작성").click().run()
        self.assertEqual(len(app.exception), 0)
        app.text_input(key="farmate_profile_form_full_name").set_value("홍길동")
        app.text_input(key="farmate_profile_form_account_number").set_value("123456789012")
        next(button for button in app.button if button.label == "프로필 저장").click().run()
        self.assertEqual(len(app.exception), 0)

        account_id = app.session_state["farmate_account_id"]
        store = ProfileStore(self.database_path, self.key)
        self.assertEqual(store.get_profile(account_id)["full_name"], "홍길동")

        app.text_area(key=f"farmate_applicant_info_{account_id}").set_value("이전 사용자 임시 입력")
        next(button for button in app.button if button.label == "로그아웃").click().run()
        self.assertNotIn("farmate_account_id", app.session_state)
        self.assertNotIn(f"farmate_applicant_info_{account_id}", app.session_state)
        app.text_input(key="farmate_login_email").set_value("farmer@example.com")
        app.text_input(key="farmate_login_password").set_value("strong-password-123")
        next(button for button in app.button if button.label == "로그인").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.text_input(key="farmate_profile_form_full_name").value, "홍길동")
        self.assertEqual(
            app.text_input(key="farmate_profile_form_account_number").value,
            "123456789012",
        )

    def test_chatbot_choices_recommendation_view_and_application_navigation(self) -> None:
        store = ProfileStore(self.database_path, self.key)
        account_id = store.register("farmer@example.com", "strong-password-123")
        store.save_profile(
            account_id,
            {"crop_categories": "복숭아", "address": "경북 청도군"},
        )
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path), default_timeout=20)
        app.session_state["farmate_account_id"] = account_id

        sample_notice = Notice(
            code="TEST-1",
            title="복숭아 청년농 지원",
            summary="경북 지역 농업인을 위한 공개 사업 안내",
            year="2026",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            date_confirmation_required=False,
            date_note="",
            office="농업기관",
            online_application=True,
            source_url="https://www.nongupez.go.kr/nsm/bizAply/wholeBiz/wholeBizMain",
        )
        with patch("farmate.notices.fetch_notices", return_value=[sample_notice]):
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("공고 추천", [button.label for button in app.button])
            self.assertIn("신청서 작성", [button.label for button in app.button])
            self.assertEqual(len(app.chat_input), 1)
            self.assertTrue(
                any("farmate-chat-window" in item.value for item in app.markdown)
            )

            next(button for button in app.button if button.label == "공고 추천").click().run()
            self.assertEqual(len(app.exception), 0)
            chat = app.session_state["farmate_chat_messages"]
            self.assertEqual(chat[-2]["role"], "user")
            self.assertEqual(chat[-2]["content"], "공고 추천")
            self.assertEqual(chat[-1]["role"], "assistant")
            self.assertIn(sample_notice.title, [item.value for item in app.subheader])
            self.assertTrue(
                any("프로필 키워드 일치" in item.value for item in app.caption)
            )

            next(button for button in app.button if button.label == "처음으로").click().run()
            next(button for button in app.button if button.label == "신청서 작성").click().run()
            self.assertEqual(len(app.exception), 0)
            chat = app.session_state["farmate_chat_messages"]
            self.assertEqual(chat[-2]["role"], "user")
            self.assertEqual(chat[-2]["content"], "신청서 작성")
            self.assertEqual(chat[-1]["role"], "assistant")
            self.assertTrue(any("지원사업 공고 PDF" in item.label for item in app.file_uploader))

    def test_guest_demo_works_without_encryption_secret_or_login(self) -> None:
        os.environ.pop("FARMATE_PROFILE_ENCRYPTION_KEY", None)
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        next(button for button in app.button if button.label == "로그인 없이 공개 데모 사용").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("공고 추천", [button.label for button in app.button])
        next(button for button in app.button if button.label == "신청서 작성").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("가상 데모" in item.value for item in app.info))
        next(button for button in app.button if button.label == "답변 반영").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("가상 검토 결과" in item.value for item in app.markdown))


if __name__ == "__main__":
    unittest.main()
