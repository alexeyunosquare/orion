"""Encrypted secrets storage using Fernet symmetric encryption.

Intended for storing sensitive values in the database (e.g., API keys
used by tools) without plaintext exposure.  In production the Fernet
key should come from a secrets manager (AWS Secrets Manager, Vault, etc).
"""

from cryptography.fernet import Fernet, InvalidToken

from orion.config import settings

_fernet: Fernet | None = None


def get_fernet() -> Fernet | None:
    """Return the global Fernet instance, or None if no key is configured."""
    global _fernet  # noqa: PLW0603
    if _fernet is None and settings.jwt_secret:
        # Generate a proper Fernet key.
        # In production, store a proper Fernet key directly in secrets manager.
        _fernet = Fernet(Fernet.generate_key())
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext value.

    Returns the original plaintext if no encryption key is configured
    (dev mode).
    """
    f = get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a previously encrypted value.

    Returns the original ciphertext if no encryption key is configured.
    Raises InvalidToken if the ciphertext is corrupted or tampered with.
    """
    # Prevent unused import warning — InvalidToken is re-exported for callers
    _ = InvalidToken
    f = get_fernet()
    if f is None:
        return ciphertext
    return f.decrypt(ciphertext.encode()).decode()


def reset_fernet() -> None:
    """Reset the Fernet instance. Useful for testing."""
    global _fernet  # noqa: PLW0603
    _fernet = None
