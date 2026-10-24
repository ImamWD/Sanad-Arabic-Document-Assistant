"""Password hashing with argon2id (argon2-cffi defaults: the RFC 9106 low-memory profile).

These calls are CPU-bound (tens of milliseconds); async code runs them in a threadpool.
"""

from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Stored for the guest, who has no password: no argon2 hash ever matches it.
UNUSABLE_PASSWORD_HASH = "!"  # noqa: S105 - deliberately not a hash of anything


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


@cache
def _dummy_hash() -> str:
    return _hasher.hash("sanad-timing-equaliser")


def burn_verify_time(password: str) -> None:
    """Spend as long as a real verification, so an unknown email can't be told apart by timing."""
    verify_password(_dummy_hash(), password)
