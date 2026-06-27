"""Minimal, dependency-free leveled logger with optional color."""

from __future__ import annotations

import logging
import os
import sys

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}

_COLORS = {
    logging.DEBUG: "\x1b[90m",
    logging.INFO: "\x1b[36m",
    logging.WARNING: "\x1b[33m",
    logging.ERROR: "\x1b[31m",
}
_RESET = "\x1b[0m"


class _Formatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-5s [%(name)s] %(message)s", "%Y-%m-%dT%H:%M:%S")
        self._color = sys.stderr.isatty() and "NO_COLOR" not in os.environ

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self._color:
            color = _COLORS.get(record.levelno, "")
            return f"{color}{text}{_RESET}"
        return text


_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_Formatter())
    root = logging.getLogger("sentinel")
    root.addHandler(handler)
    level = os.environ.get("SENTINEL_LOG_LEVEL", "info").lower()
    root.setLevel(_LEVELS.get(level, logging.INFO))
    root.propagate = False
    _configured = True


def set_log_level(level: str) -> None:
    _configure()
    logging.getLogger("sentinel").setLevel(_LEVELS.get(level.lower(), logging.INFO))


def get_logger(scope: str) -> logging.Logger:
    _configure()
    return logging.getLogger(f"sentinel.{scope}")
