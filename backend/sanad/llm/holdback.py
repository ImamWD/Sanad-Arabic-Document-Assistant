"""Hold streamed tokens back until the `NO_ANSWER` sentinel is ruled out (SYSTEM_DESIGN §6).

Validation wins over streaming:
- Nothing is released until the output holds `min_chars` non-space characters without the
  sentinel. A bare `NO_ANSWER` (or `**NO_ANSWER**`) is therefore never streamed, and a refusal
  by sentinel emits no `token` event at all.
- After that, text is released as it arrives, except a trailing piece that could still grow
  into the sentinel. If the sentinel appears later, releasing stops; `final` then replaces
  whatever was streamed with the refusal.
- `finish()` returns what is still held. The caller releases it only if validation accepts the
  answer, so a short answer that never reached `min_chars` still streams before `final`.
"""

from sanad.llm.validate import SENTINEL, contains_sentinel

DEFAULT_MIN_CHARS = 16


def _held_suffix_length(text: str) -> int:
    """Length of the longest suffix of `text` that is a proper prefix of the sentinel."""
    upper = text.upper()
    for size in range(min(len(SENTINEL) - 1, len(text)), 0, -1):
        if SENTINEL.startswith(upper[-size:]):
            return size
    return 0


class SentinelHoldback:
    def __init__(self, min_chars: int = DEFAULT_MIN_CHARS) -> None:
        self._min_chars = min_chars
        self._buffer = ""  # received, not yet released
        self._started = False
        self.sentinel_seen = False

    def feed(self, text: str) -> str:
        """Add generated text; return the part that may be shown now (possibly empty)."""
        if self.sentinel_seen:
            return ""
        self._buffer += text
        if contains_sentinel(self._buffer):
            self.sentinel_seen = True
            self._buffer = ""
            return ""
        if not self._started:
            if sum(not ch.isspace() for ch in self._buffer) < self._min_chars:
                return ""
            self._started = True
        cut = len(self._buffer) - _held_suffix_length(self._buffer)
        released, self._buffer = self._buffer[:cut], self._buffer[cut:]
        return released

    def finish(self) -> str:
        """The text still held at the end of generation ("" after a sentinel)."""
        held, self._buffer = ("" if self.sentinel_seen else self._buffer), ""
        return held
