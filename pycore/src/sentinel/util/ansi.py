"""Strip ANSI / terminal control sequences from raw PTY output."""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"[\x1B\x9B][\[\]()#;?]*(?:(?:\d{1,4}(?:;\d{0,4})*)?[0-9A-PRZcf-ntqry=><~])")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)
