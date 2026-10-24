"""Unit tests for the pieces behind auth: the rate limiter, require_role and password hashing."""

import asyncio

import pytest
from argon2 import Type

from sanad.core import passwords
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.models import Language, User
from sanad.core.ratelimit import LoginRateLimiter
from sanad.core.security import Role, require_role
from tests.api.conftest import PRODUCTION_HASHER

# --- rate limiter ------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _limiter(clock: Clock) -> LoginRateLimiter:
    return LoginRateLimiter(
        window_seconds=60, max_failures_per_email=3, max_failures_per_ip=5, clock=clock
    )


def test_limiter_counts_failures_in_a_sliding_window() -> None:
    clock = Clock()
    limiter = _limiter(clock)
    for t in (0, 10, 20):
        clock.now = t
        assert limiter.retry_after("a@x.org", "ip1") is None
        limiter.record_failure("a@x.org", "ip1")

    clock.now = 30
    assert limiter.retry_after("a@x.org", "ip1") == 30  # the failure at t=0 leaves at t=60
    assert limiter.retry_after(" A@X.ORG ", "ip2") == 30  # same email, any IP
    assert limiter.retry_after("b@x.org", "ip1") is None

    clock.now = 60
    assert limiter.retry_after("a@x.org", "ip1") is None


def test_limiter_ip_limit_spans_emails() -> None:
    clock = Clock()
    limiter = _limiter(clock)
    for n in range(5):
        limiter.record_failure(f"user{n}@x.org", "ip1")
    assert limiter.retry_after("fresh@x.org", "ip1") == 60
    assert limiter.retry_after("fresh@x.org", "ip2") is None


def test_limiter_reset_clears_the_email_only() -> None:
    clock = Clock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("a@x.org", "ip1")
    limiter.reset_email("A@x.org")
    assert limiter.retry_after("a@x.org", "ip9") is None
    for _ in range(2):
        limiter.record_failure("b@x.org", "ip1")
    assert limiter.retry_after("c@x.org", "ip1") == 60  # 3 + 2 failures from ip1


def test_limiter_forgets_old_keys() -> None:
    clock = Clock()
    limiter = _limiter(clock)
    limiter.record_failure("a@x.org", "ip1")
    clock.now = 61
    limiter.retry_after("a@x.org", "ip1")
    assert limiter._failures == {}


# --- require_role ------------------------------------------------------------------------


def _user(role: Role, *, is_guest: bool = False) -> User:
    return User(
        name="Probe",
        email="probe@sanad.example",
        password_hash=passwords.UNUSABLE_PASSWORD_HASH,
        role=role,
        preferred_language=Language.EN,
        is_guest=is_guest,
    )


@pytest.mark.parametrize(
    ("roles", "user", "allowed"),
    [
        ((Role.ADMIN,), _user(Role.ADMIN), True),
        ((Role.ADMIN,), _user(Role.EDITOR), False),
        ((Role.EDITOR, Role.ADMIN), _user(Role.EDITOR), True),
        ((Role.EDITOR, Role.ADMIN), _user(Role.VIEWER), False),
        ((Role.VIEWER, Role.EDITOR, Role.ADMIN), _user(Role.VIEWER, is_guest=True), True),
        # A guest is refused wherever viewers are, even if its role were somehow raised.
        ((Role.EDITOR, Role.ADMIN), _user(Role.EDITOR, is_guest=True), False),
    ],
)
def test_require_role(roles: tuple[Role, ...], user: User, allowed: bool) -> None:
    check = require_role(*roles)
    if allowed:
        assert asyncio.run(check(user)) is user
    else:
        with pytest.raises(ApiError) as excinfo:
            asyncio.run(check(user))
        assert (excinfo.value.status_code, excinfo.value.code) == (403, ErrorCode.FORBIDDEN)


# --- passwords ---------------------------------------------------------------------------


def test_production_hasher_is_argon2id_with_real_cost() -> None:
    assert PRODUCTION_HASHER.type is Type.ID
    assert PRODUCTION_HASHER.memory_cost >= 19 * 1024  # OWASP minimum: 19 MiB
    assert PRODUCTION_HASHER.time_cost >= 2


def test_password_round_trip() -> None:
    stored = passwords.hash_password("correct horse")
    assert stored.startswith("$argon2id$")
    assert passwords.verify_password(stored, "correct horse")
    assert not passwords.verify_password(stored, "wrong horse")
    assert not passwords.needs_rehash(stored)


def test_unusable_hash_never_verifies() -> None:
    assert not passwords.verify_password(passwords.UNUSABLE_PASSWORD_HASH, "!")
    assert not passwords.needs_rehash(passwords.UNUSABLE_PASSWORD_HASH)
    passwords.burn_verify_time("anything")  # must not raise
