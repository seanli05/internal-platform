"""Worker loop and entrypoint.

Run it with `python -m app.worker`. It shares this codebase with the API — same
settings, same models, same database — it is simply a different process.
"""

import asyncio
import contextlib
import logging
import signal

from app.config import Settings, get_settings
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


async def run_worker(settings: Settings, stop: asyncio.Event) -> None:
    """Log a liveness line every `worker_poll_interval_seconds` until `stop` is set.

    Phase 4 replaces the body of this loop with: claim a batch of
    `photos WHERE processing_status = 'pending'`, embed them, mark them done.
    """
    logger.info(
        "Worker started (environment=%s, poll interval=%ss)",
        settings.environment,
        settings.worker_poll_interval_seconds,
    )
    while not stop.is_set():
        logger.info("worker alive")
        # Sleep, but wake immediately when a shutdown signal arrives.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_seconds)
    logger.info("Worker stopped")


async def _main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await run_worker(settings, stop)


def main() -> None:
    """Process entrypoint."""
    asyncio.run(_main())


if __name__ == "__main__":  # pragma: no cover
    main()
