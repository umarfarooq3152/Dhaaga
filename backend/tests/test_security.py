"""Tests for password hashing and JWT helpers."""

from uuid import uuid4

import pytest

from app.security import create_access_token, decode_access_token, hash_password, verify_password


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        assert hash_password("SecurePass123") != "SecurePass123"

    def test_verify_correct_password(self):
        hashed = hash_password("SecurePass123")
        assert verify_password("SecurePass123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("SecurePass123")
        assert verify_password("WrongPassword", hashed) is False

    def test_same_password_hashes_differently_each_time(self):
        # bcrypt salts each hash — two hashes of the same password must
        # differ, otherwise a leaked hash table trivially reveals repeats.
        assert hash_password("SecurePass123") != hash_password("SecurePass123")


class TestAccessToken:
    def test_decode_returns_the_encoded_user_id(self, fake_settings, monkeypatch):
        monkeypatch.setattr("app.security.get_settings", lambda: fake_settings)
        user_id = uuid4()
        token = create_access_token(user_id)
        assert decode_access_token(token) == user_id

    def test_decode_rejects_tampered_token(self, fake_settings, monkeypatch):
        monkeypatch.setattr("app.security.get_settings", lambda: fake_settings)
        token = create_access_token(uuid4())
        header, payload, signature = token.split(".")
        tampered_signature = ("a" if signature[0] != "a" else "b") + signature[1:]
        tampered = ".".join((header, payload, tampered_signature))
        assert decode_access_token(tampered) is None

    def test_decode_rejects_garbage(self, fake_settings, monkeypatch):
        monkeypatch.setattr("app.security.get_settings", lambda: fake_settings)
        assert decode_access_token("not-a-real-token") is None

    def test_decode_rejects_token_signed_with_a_different_secret(self, fake_settings, monkeypatch):
        monkeypatch.setattr("app.security.get_settings", lambda: fake_settings)
        token = create_access_token(uuid4())

        other_settings = fake_settings.model_copy(update={"jwt_secret_key": "a-different-secret"})
        monkeypatch.setattr("app.security.get_settings", lambda: other_settings)
        assert decode_access_token(token) is None
