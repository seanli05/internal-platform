"""Logging setup shared by the API and the worker."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(level: str) -> None:
    """Configure root logging once, for whichever process is starting up."""
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)
