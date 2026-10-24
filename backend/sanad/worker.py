"""Worker entry point: `python -m sanad.worker`. Stops cleanly on SIGTERM or SIGINT."""

import logging
import signal
import threading
from types import FrameType

from sanad.core.config import get_settings
from sanad.ingest import worker


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    stop = threading.Event()

    def _stop(signum: int, _frame: FrameType | None) -> None:
        logging.getLogger(__name__).info("received %s", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    worker.run(stop, settings.worker_idle_seconds)


if __name__ == "__main__":
    main()
