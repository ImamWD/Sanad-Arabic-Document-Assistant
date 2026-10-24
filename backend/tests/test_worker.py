import os
import signal
import subprocess
import sys
import threading
import time

from sanad.ingest import worker


def test_run_returns_once_stopped() -> None:
    stop = threading.Event()
    timer = threading.Timer(0.05, stop.set)
    timer.start()
    started = time.monotonic()

    worker.run(stop, idle_seconds=10)

    assert time.monotonic() - started < 5


def test_entry_point_exits_cleanly_on_sigterm() -> None:
    env = {**os.environ, "WORKER_IDLE_SECONDS": "0.05", "LOG_LEVEL": "INFO"}
    with subprocess.Popen(
        [sys.executable, "-m", "sanad.worker"],
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    ) as proc:
        try:
            assert proc.stderr is not None
            # Wait until the loop is running, then ask it to stop the way docker does.
            assert "worker started" in proc.stderr.readline()
            proc.send_signal(signal.SIGTERM)
            assert proc.wait(timeout=5) == 0
            assert "worker stopped" in proc.stderr.read()
        finally:
            proc.kill()
