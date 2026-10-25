"""The eval's HTTP client: the same calls a browser makes, plus `debug: true` on ask.

Every POST carries B2's CSRF header (`X-Sanad: 1`) and a JSON body. The session cookie
(`sanad_session`) lives in the client's cookie jar after login. Questions are asked one at a
time, so queueing never skews the measured latency.
"""

import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import httpx2

CSRF_HEADERS = {"X-Sanad": "1"}
SESSION_COOKIE = "sanad_session"
DOCUMENTS_PAGE_SIZE = 100  # the API's maximum
OLLAMA_PROBE_SECONDS = 3.0

# Report-only labels for failures that never reached a server error envelope.
EVAL_TIMEOUT = "EVAL_TIMEOUT"
EVAL_TRANSPORT_ERROR = "EVAL_TRANSPORT_ERROR"
EVAL_BAD_RESPONSE = "EVAL_BAD_RESPONSE"


class EvalClientError(RuntimeError):
    """The stack can't be used for an eval run (unreachable, login refused, bad reply)."""


@dataclass(frozen=True)
class AskReply:
    status: int | None  # HTTP status; None if no response arrived
    data: dict[str, Any] | None  # the AskResult body on success
    wall_ms: int  # measured by the runner, request to response
    error_code: str | None = None


def _error_code(response: httpx2.Response) -> str:
    """The server's error envelope code, or HTTP_<status> if the body has none."""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        code = body["error"].get("code")
        if isinstance(code, str) and code:
            return code
    return f"HTTP_{response.status_code}"


class SanadClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._http = httpx2.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx2.Timeout(timeout, connect=10.0),
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, **kwargs: Any) -> httpx2.Response:
        try:
            return self._http.request(method, path, **kwargs)
        except httpx2.TransportError as exc:
            raise EvalClientError(f"{method} {path}: {type(exc).__name__}: {exc}") from exc

    def _post(self, path: str, body: dict[str, Any]) -> httpx2.Response:
        return self._call("POST", path, json=body, headers=CSRF_HEADERS)

    def _signed_in(self, response: httpx2.Response, who: str) -> dict[str, Any]:
        if response.status_code != 200:
            raise EvalClientError(f"sign-in as {who} refused: {_error_code(response)}")
        if not self._http.cookies.get(SESSION_COOKIE):
            raise EvalClientError(f"sign-in as {who} set no {SESSION_COOKIE} cookie")
        me = response.json()
        return me if isinstance(me, dict) else {}

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Sign in and keep the session cookie; returns the `Me` body."""
        response = self._post("/api/auth/login", {"email": email, "password": password})
        return self._signed_in(response, email)

    def login_guest(self) -> dict[str, Any]:
        return self._signed_in(self._post("/api/auth/guest", {}), "guest")

    def health(self) -> dict[str, Any]:
        """`GET /api/health`. Raises unless the stack reports itself healthy."""
        response = self._call("GET", "/api/health")
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code != 200 or not isinstance(body, dict):
            raise EvalClientError(f"/api/health answered {response.status_code}: {body}")
        return body

    def documents(self) -> list[dict[str, Any]]:
        """Every document the signed-in user can see, archived ones included."""
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            params = {"include_archived": "true", "page_size": DOCUMENTS_PAGE_SIZE, "page": page}
            response = self._call("GET", "/api/documents", params=params)
            if response.status_code != 200:
                raise EvalClientError(f"/api/documents answered {_error_code(response)}")
            body = response.json()
            batch = body.get("items") if isinstance(body, dict) else None
            if not isinstance(batch, list):
                raise EvalClientError("/api/documents returned no `items` list")
            items.extend(i for i in batch if isinstance(i, dict))
            if not batch or len(items) >= int(body.get("total", 0)):
                return items
            page += 1

    def ask(self, question: str, *, debug: bool) -> AskReply:
        body: dict[str, Any] = {"question": question}
        if debug:
            body["debug"] = True
        started = time.perf_counter()
        try:
            response = self._http.post("/api/ask", json=body, headers=CSRF_HEADERS)
        except httpx2.TimeoutException:
            return AskReply(None, None, _since(started), EVAL_TIMEOUT)
        except httpx2.TransportError:
            return AskReply(None, None, _since(started), EVAL_TRANSPORT_ERROR)
        wall_ms = _since(started)
        if not response.is_success:
            return AskReply(response.status_code, None, wall_ms, _error_code(response))
        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            return AskReply(response.status_code, None, wall_ms, EVAL_BAD_RESPONSE)
        return AskReply(response.status_code, data, wall_ms)

    def ollama_version(self, ollama_url: str) -> str | None:
        """Ask Ollama itself (`/api/version`), on the internal network. None if unreachable."""
        try:
            response = self._http.get(
                f"{ollama_url.rstrip('/')}/api/version", timeout=OLLAMA_PROBE_SECONDS
            )
            body = response.json() if response.status_code == 200 else None
        except (httpx2.TransportError, ValueError):
            return None
        version = body.get("version") if isinstance(body, dict) else None
        return str(version) if version else None


def _since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
