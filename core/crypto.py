"""
Cryptographic utilities for securing credentials at rest.
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256 authenticated encryption)
derived from the server's DJANGO_SECRET_KEY.
"""

import base64
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    """Derive a URL-safe base64-encoded 32-byte Fernet key from settings.SECRET_KEY."""
    secret = getattr(settings, "SECRET_KEY", "fallback-secret-key-change-in-production")
    key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_credential(raw_text: str) -> str:
    """Encrypt a plaintext credential string into an armored Fernet token."""
    if not raw_text:
        return ""
    f = _get_fernet()
    return f.encrypt(str(raw_text).encode("utf-8")).decode("utf-8")


def decrypt_credential(encrypted_text: str) -> str:
    """Decrypt an armored Fernet token back into plaintext. Returns empty string on failure."""
    if not encrypted_text:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(str(encrypted_text).encode("utf-8")).decode("utf-8")
    except Exception:
        return ""
