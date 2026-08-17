"""Agent API key generation/hashing, and user password hashing/session tokens.

Keys, session tokens, and temporary passwords are shown to the caller
exactly once (at creation) -- only a hash is persisted, so a stolen database
dump doesn't hand out usable credentials.
"""

import hashlib
import hmac
import secrets

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
