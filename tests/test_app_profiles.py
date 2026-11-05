from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet
from streamlit.testing.v1 import AppTest

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


if __name__ == "__main__":
    unittest.main()
