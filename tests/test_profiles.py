from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from farmate.profiles import (
    AccountAlreadyExists,
    PROFILE_FIELDS,
    ProfileStore,
    ProfileStoreError,
    profile_form_defaults,
    profile_template_values,
)


class ProfileStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "profiles.sqlite3"
        self.key = Fernet.generate_key()
        self.store = ProfileStore(self.database_path, self.key)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_registration_and_login_use_salted_password_hash(self) -> None:
        password = "correct horse battery"
        account_id = self.store.register("Farmer@example.com", password)
        other_account = self.store.register("other@example.com", password)

        connection = sqlite3.connect(self.database_path)
        try:
            salt, password_hash = connection.execute(
                "SELECT password_salt, password_hash FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            other_salt, other_hash = connection.execute(
                "SELECT password_salt, password_hash FROM accounts WHERE id = ?",
                (other_account,),
            ).fetchone()
        finally:
            connection.close()

        self.assertNotEqual(password_hash, password.encode("utf-8"))
        self.assertEqual(len(salt), 16)
        self.assertEqual(len(password_hash), 32)
        self.assertNotEqual(salt, other_salt)
        self.assertNotEqual(password_hash, other_hash)
        self.assertEqual(self.store.authenticate("farmer@example.com", password), account_id)
        self.assertIsNone(self.store.authenticate("farmer@example.com", "wrong password"))
        self.assertEqual(self.store.get_email(account_id), "farmer@example.com")

    def test_registration_rejects_duplicate_email_and_short_password(self) -> None:
        self.store.register("farmer@example.com", "long-enough-password")
        with self.assertRaises(AccountAlreadyExists):
            self.store.register("FARMER@example.com", "another-long-password")
        with self.assertRaises(ProfileStoreError):
            self.store.register("new@example.com", "short")

    def test_profiles_are_isolated_between_accounts(self) -> None:
        first = self.store.register("first@example.com", "first-long-password")
        second = self.store.register("second@example.com", "second-long-password")
        self.store.save_profile(first, {"full_name": "첫 사용자", "account_number": "123-456"})
        self.store.save_profile(second, {"full_name": "둘 사용자", "account_number": "987-654"})

        self.assertEqual(self.store.get_profile(first)["full_name"], "첫 사용자")
        self.assertEqual(self.store.get_profile(second)["full_name"], "둘 사용자")
        self.assertEqual(self.store.get_profile(first)["account_number"], "123-456")
        self.assertEqual(self.store.get_profile(second)["account_number"], "987-654")

    def test_profile_ciphertext_hides_sensitive_values_and_autofills(self) -> None:
        account_id = self.store.register("farmer@example.com", "long-enough-password")
        sensitive_values = {
            "full_name": "홍길동",
            "farm_registration_number": "FARM-998877",
            "account_number": "123456789012",
            "address": "경북 청도군 개인정보로 1",
        }
        saved = self.store.save_profile(account_id, sensitive_values)

        raw_database = self.database_path.read_bytes()
        for value in sensitive_values.values():
            self.assertNotIn(value.encode("utf-8"), raw_database)
        self.assertEqual(self.store.get_profile(account_id), profile_form_defaults(saved))
        reopened_store = ProfileStore(self.database_path, self.key)
        self.assertEqual(reopened_store.get_profile(account_id), profile_form_defaults(saved))

        template_values = profile_template_values(saved)
        self.assertEqual(template_values["성명"], "홍길동")
        self.assertEqual(template_values["신청인"], "홍길동")
        self.assertEqual(template_values["계좌번호"], "123456789012")
        self.assertEqual(template_values["주소"], "경북 청도군 개인정보로 1")

    def test_profile_form_defaults_include_every_editable_field(self) -> None:
        defaults = profile_form_defaults({"full_name": "홍길동", "unknown": "ignored"})
        self.assertEqual(set(defaults), {key for key, _ in PROFILE_FIELDS})
        self.assertEqual(defaults["full_name"], "홍길동")
        self.assertEqual(defaults["account_number"], "")

    def test_wrong_encryption_key_does_not_return_profile_data(self) -> None:
        account_id = self.store.register("farmer@example.com", "long-enough-password")
        self.store.save_profile(account_id, {"account_number": "secret-account"})
        other_store = ProfileStore(self.database_path, Fernet.generate_key())

        with self.assertRaisesRegex(ProfileStoreError, "복호화"):
            other_store.get_profile(account_id)


if __name__ == "__main__":
    unittest.main()
