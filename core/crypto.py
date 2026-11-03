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
    """
    Derive a URL-safe base64-encoded 32-byte Fernet key.
    Inspects settings.FIELD_ENCRYPTION_KEY / ENCRYPTION_KEY before falling back to SECRET_KEY.
    """
    custom_key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or getattr(settings, "ENCRYPTION_KEY", "")
    if custom_key:
        clean_key = custom_key.strip()
        # If already a valid 32-byte base64-encoded Fernet key (44 chars ending with =)
        try:
            if len(clean_key) == 44 and base64.urlsafe_b64decode(clean_key.encode("utf-8")):
                return Fernet(clean_key.encode("utf-8"))
        except Exception:
            pass
        key_bytes = hashlib.sha256(clean_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)

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
