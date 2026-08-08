"""The worker stub must run its loop and shut down cleanly when signalled."""

import asyncio
import logging

import pytest

from app.config import Settings
from app.worker.main import run_worker


def test_worker_logs_liveness_and_stops_when_signalled(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def exercise() -> None:
        stop = asyncio.Event()
        worker = asyncio.create_task(run_worker(settings, stop))
        await asyncio.sleep(0)  # let the loop log at least once
        stop.set()
        # A clean shutdown returns promptly instead of waiting out the poll interval.
        await asyncio.wait_for(worker, timeout=1.0)

    with caplog.at_level(logging.INFO, logger="app.worker.main"):
        asyncio.run(exercise())

    assert "worker alive" in caplog.text
    assert "Worker stopped" in caplog.text
