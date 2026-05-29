"""Tests for encrypted secrets storage."""

import pytest
from cryptography.fernet import Fernet

from orion.security.secrets import (
    decrypt_secret,
    encrypt_secret,
    get_fernet,
    reset_fernet,
)


@pytest.fixture(autouse=True)
def _reset_fernet_instance():
    """Reset Fernet between tests."""
    reset_fernet()
    yield
    reset_fernet()


class TestSecretsNoKey:
    def test_encrypt_returns_plaintext_without_key(self):
        """Without encryption key, encrypt returns plaintext."""
        result = encrypt_secret("my-secret")
        assert result == "my-secret"

    def test_decrypt_returns_plaintext_without_key(self):
        """Without encryption key, decrypt returns ciphertext as-is."""
        result = decrypt_secret("my-secret")
        assert result == "my-secret"

    def test_get_fernet_returns_none_without_key(self):
        """No jwt_secret means no Fernet instance."""
        assert get_fernet() is None


class TestSecretsWithKey:
    def test_encrypt_decrypt_roundtrip(self, monkeypatch):
        """Encrypted value decrypts to original."""
        # Set up a proper Fernet key
        key = Fernet.generate_key()
        reset_fernet()

        # Manually set _fernet for testing
        from orion.security import secrets
        secrets._fernet = Fernet(key)

        original = "sensitive-api-key-123"
        encrypted = encrypt_secret(original)
        assert encrypted != original  # Value was actually encrypted
        assert decrypt_secret(encrypted) == original

    def test_decrypt_invalid_token(self, monkeypatch):
        """Decrypting invalid ciphertext raises InvalidToken."""
        from cryptography.fernet import InvalidToken

        key = Fernet.generate_key()
        reset_fernet()

        from orion.security import secrets
        secrets._fernet = Fernet(key)

        with pytest.raises(InvalidToken):
            decrypt_secret("invalid-ciphertext")

    def test_different_values_produce_different_ciphertext(self, monkeypatch):
        """Different inputs produce different encrypted outputs."""
        key = Fernet.generate_key()
        reset_fernet()

        from orion.security import secrets
        secrets._fernet = Fernet(key)

        enc1 = encrypt_secret("secret1")
        enc2 = encrypt_secret("secret2")
        assert enc1 != enc2

    def test_same_value_produces_different_ciphertext_each_time(self, monkeypatch):
        """Fernet uses random IV, so same input produces different output."""
        key = Fernet.generate_key()
        reset_fernet()

        from orion.security import secrets
        secrets._fernet = Fernet(key)

        enc1 = encrypt_secret("same-secret")
        enc2 = encrypt_secret("same-secret")
        # Both decrypt to the same value but ciphertexts differ
        assert enc1 != enc2
        assert decrypt_secret(enc1) == decrypt_secret(enc2)
