"""Shared by every backend test: the `live` marker.

A live test needs part of the running stack (`make up`). It names that part's health URL:

    pytestmark = pytest.mark.live(health="http://api:8000/api/health", what="the stack")

When the URL doesn't answer, the test is skipped with a reason, so local runs without a stack
stay green. With SANAD_REQUIRE_LIVE=1 it fails instead: CI sets it after `make up`, so an
unreachable stack can't turn the live tests into silent skips.
"""

import os
from functools import cache

import httpx2
import pytest

REQUIRE_LIVE = "SANAD_REQUIRE_LIVE"


@cache
def answers(url: str) -> bool:
    """True when `url` answers 200 within 3 s. Asked once per URL per run."""
    try:
        return httpx2.get(url, timeout=3).status_code == 200
    except httpx2.HTTPError:
        return False


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    marker = item.get_closest_marker("live")
    if marker is None:
        return
    health, what = marker.kwargs.get("health"), marker.kwargs.get("what")
    if not health or not what:
        pytest.fail("pytest.mark.live needs health= and what=", pytrace=False)
    if answers(health):
        return
    reason = f"{what} isn't running (make up): no answer from {health}"
    if os.environ.get(REQUIRE_LIVE) == "1":
        pytest.fail(f"{REQUIRE_LIVE}=1, but {reason}", pytrace=False)
    pytest.skip(reason)
