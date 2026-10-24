"""Ingestion worker loop. M0: idles until stopped. B3 replaces the body with the claim loop."""

import logging
import threading

logger = logging.getLogger(__name__)


def run(stop: threading.Event, idle_seconds: float) -> None:
    logger.info("worker started; no ingestion pipeline yet, idling")
    while not stop.wait(idle_seconds):
        logger.debug("worker idle")
    logger.info("worker stopped")
