from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping

from cryptography.fernet import Fernet, InvalidToken

PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
MAX_PROFILE_FIELD_LENGTH = 2_000

PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("full_name", "성명"),
    ("farm_registration_number", "농업경영체 등록번호"),
    ("birth_date", "생년월일"),
    ("corporate_registration_number", "법인등록번호"),
    ("address", "주소"),
    ("phone", "연락처"),
    ("bank_name", "은행명"),
    ("account_number", "계좌번호"),
    ("account_holder", "예금주"),
    ("farm_type", "영농 형태"),
    ("certification_type", "인증 유형"),
    ("crop_categories", "재배 작물"),
    ("parcel_location", "농지 소재지"),
    ("acreage", "경작 면적"),
    ("subsidy_eligibility", "보조금 수급 자격"),
    ("previous_payments", "과거 지원금 수령 내역"),
    ("application_date", "신청일"),
    ("signature_name", "서명자"),
)

TEMPLATE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "full_name": ("신청인", "신청자", "신청자 성명", "대표자 성명", "성명(대표자)"),
    "farm_registration_number": ("농업경영체등록번호", "경영체 등록번호"),
    "birth_date": ("출생연월일",),
    "corporate_registration_number": ("법인 등록 번호",),
    "address": ("거주지", "주소지"),
    "phone": ("전화번호", "휴대전화", "휴대폰"),
    "bank_name": ("금융기관", "거래은행"),
    "account_number": ("은행 계좌번호", "입금 계좌번호"),
    "account_holder": ("예금주명", "계좌 예금주"),
    "farm_type": ("영농형태", "농업 유형"),
    "certification_type": ("인증유형", "인증 현황"),
    "crop_categories": ("재배작물", "작목", "작물"),
    "parcel_location": ("농지소재지", "필지 소재지"),
    "acreage": ("경작면적", "재배면적", "면적"),
    "subsidy_eligibility": ("보조금 수급자격", "지원 자격"),
    "previous_payments": ("과거 지원금 수령 내역", "지원금 수령 내역"),
    "application_date": ("작성일",),
    "signature_name": ("신청인 서명", "대표자 서명", "서명"),
}


class ProfileStoreError(ValueError):
    """A profile store operation could not be completed safely."""


class AccountAlreadyExists(ProfileStoreError):
    """The normalized email address is already registered."""


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ProfileStoreError("올바른 이메일 주소를 입력하세요.")
    return normalized


def profile_form_defaults(profile: Mapping[str, str] | None = None) -> dict[str, str]:
    values = {key: "" for key, _ in PROFILE_FIELDS}
    if profile:
        for key in values:
            value = profile.get(key, "")
            if isinstance(value, str):
                values[key] = value
    return values


def profile_template_values(profile: Mapping[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, label in PROFILE_FIELDS:
        value = profile.get(key, "")
        if not isinstance(value, str) or not value.strip():
            continue
        values[label] = value.strip()
        for alias in TEMPLATE_FIELD_ALIASES.get(key, ()):
            values[alias] = value.strip()
    return values


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )


class ProfileStore:
    def __init__(self, database_path: str | Path, encryption_key: str | bytes) -> None:
        try:
            key = encryption_key.encode("ascii") if isinstance(encryption_key, str) else encryption_key
            self._cipher = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise ProfileStoreError(
                "프로필 암호화 키가 올바른 Fernet 키 형식이 아닙니다."
            ) from exc

        self.database_path = Path(database_path)
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS accounts (
                        id TEXT PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        password_salt BLOB NOT NULL,
                        password_hash BLOB NOT NULL,
                        profile_ciphertext BLOB NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            if str(self.database_path) != ":memory:" and os.name == "posix":
                self.database_path.chmod(0o600)
        except sqlite3.Error as exc:
            raise ProfileStoreError("프로필 저장소를 초기화하지 못했습니다.") from exc

    def register(self, email: str, password: str) -> str:
        normalized_email = normalize_email(email)
        if len(password) < 12:
            raise ProfileStoreError("비밀번호는 12자 이상이어야 합니다.")
        if len(password) > 1_024:
            raise ProfileStoreError("비밀번호는 1,024자 이하여야 합니다.")

        salt = os.urandom(16)
        password_hash = _password_hash(password, salt)
        account_id = str(uuid.uuid4())
        encrypted_profile = self._cipher.encrypt(
            json.dumps(profile_form_defaults(), ensure_ascii=False).encode("utf-8")
        )
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO accounts (id, email, password_salt, password_hash, profile_ciphertext)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (account_id, normalized_email, salt, password_hash, encrypted_profile),
                )
        except sqlite3.IntegrityError as exc:
            raise AccountAlreadyExists("이미 가입된 이메일입니다.") from exc
        except sqlite3.Error as exc:
            raise ProfileStoreError("계정을 저장하지 못했습니다.") from exc
        return account_id

    def authenticate(self, email: str, password: str) -> str | None:
        if len(password) > 1_024:
            return None
        try:
            normalized_email = normalize_email(email)
        except ProfileStoreError:
            normalized_email = ""

        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT id, password_salt, password_hash FROM accounts WHERE email = ?",
                    (normalized_email,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise ProfileStoreError("로그인 정보를 확인하지 못했습니다.") from exc

        if row is None:
            _password_hash(password, b"farmate-login-timing-salt")
            return None
        candidate = _password_hash(password, row["password_salt"])
        if not hmac.compare_digest(candidate, row["password_hash"]):
            return None
        return str(row["id"])

    def get_email(self, account_id: str) -> str | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT email FROM accounts WHERE id = ?", (account_id,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise ProfileStoreError("계정 정보를 읽지 못했습니다.") from exc
        return str(row["email"]) if row else None

    def get_profile(self, account_id: str) -> dict[str, str] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT profile_ciphertext FROM accounts WHERE id = ?", (account_id,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise ProfileStoreError("프로필을 읽지 못했습니다.") from exc
        if row is None:
            return None
        try:
            decrypted = self._cipher.decrypt(row["profile_ciphertext"])
            profile = json.loads(decrypted)
        except (InvalidToken, json.JSONDecodeError, TypeError) as exc:
            raise ProfileStoreError(
                "프로필 복호화에 실패했습니다. 저장된 FARMATE_PROFILE_ENCRYPTION_KEY를 확인하세요."
            ) from exc
        if not isinstance(profile, dict):
            raise ProfileStoreError("저장된 프로필 형식이 올바르지 않습니다.")
        return profile_form_defaults(profile)

    def save_profile(self, account_id: str, profile: Mapping[str, str]) -> dict[str, str]:
        values = profile_form_defaults(profile)
        if any(len(value) > MAX_PROFILE_FIELD_LENGTH for value in values.values()):
            raise ProfileStoreError("프로필 항목은 각각 2,000자 이하로 입력하세요.")
        encrypted_profile = self._cipher.encrypt(
            json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE accounts SET profile_ciphertext = ? WHERE id = ?",
                    (encrypted_profile, account_id),
                )
                if cursor.rowcount != 1:
                    raise ProfileStoreError("로그인된 계정을 찾을 수 없습니다. 다시 로그인하세요.")
        except ProfileStoreError:
            raise
        except sqlite3.Error as exc:
            raise ProfileStoreError("프로필을 저장하지 못했습니다.") from exc
        return values
