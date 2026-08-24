"""Agent API key generation/hashing, user password hashing, session tokens,
and symmetric encryption for stored upstream MCP server credentials.

Keys, session tokens, and temporary passwords are shown to the caller
exactly once (at creation) -- only a hash is persisted, so a stolen database
dump doesn't hand out usable credentials.

Upstream server credentials (bearer tokens, API keys, etc.) are stored
encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256). The encryption
key is derived from the FALCON_SECRET_KEY environment variable. If unset,
a warning is logged and a process-local ephemeral key is used (credentials
are lost on restart -- only suitable for development).
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# ── Credential encryption ────────────────────────────────────────────────────

def _build_fernet() -> Fernet:
    raw = os.environ.get('FALCON_SECRET_KEY', '')
    if raw:
        # Derive a 32-byte key from the secret using SHA-256, then base64url-encode
        key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    else:
        logger.warning(
            'FALCON_SECRET_KEY is not set. Server credentials will be encrypted with a '
            'process-local ephemeral key and will be unreadable after a restart. '
            'Set FALCON_SECRET_KEY in production.'
        )
        key = Fernet.generate_key()
    return Fernet(key)


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _build_fernet()
    return _fernet


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential string for storage. Returns a base64url token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_credential(token: str) -> str:
    """Decrypt a stored credential token. Raises ValueError on failure."""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception as exc:
        raise ValueError('Failed to decrypt credential — wrong key or corrupted data') from exc

_PBKDF2_ITERATIONS = 200_000


def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, hash) -- persist the hash, return the raw key to the caller."""
    raw_key = f'mcp_{secrets.token_urlsafe(32)}'
    return raw_key, hash_api_key(raw_key)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


def generate_temp_password() -> str:
    """A short, readable-ish one-time password for newly-created users."""
    return secrets.token_urlsafe(9)


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 with a random per-user salt; stdlib-only (no bcrypt/passlib dependency).

    Stored as `<salt-hex>$<digest-hex>` in a single column.
    """
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), _PBKDF2_ITERATIONS).hex()
    return f'{salt}${digest}'


def verify_password(password: str, stored: str) -> bool:
    salt, _, digest = stored.partition('$')
    if not salt or not digest:
        return False
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), _PBKDF2_ITERATIONS).hex()
    return hmac.compare_digest(candidate, digest)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)
