"""ID generation, hashing and token estimation helpers.

``estimate_tokens`` transparently uses the native (C/Assembly) accelerator when
available, falling back to a pure-Python heuristic otherwise. Real client
adapters override token counting with the client's native tokenizer
(cl100k_base for Claude, o200k_base for GPT-4o, SentencePiece for Gemini).
"""

from __future__ import annotations

import hashlib
import math
import uuid as _uuid

from .accel import accel


def uuid() -> str:
    return str(_uuid.uuid4())


def short_id(prefix: str = "") -> str:
    s = str(_uuid.uuid4()).split("-")[0]
    return f"{prefix}_{s}" if prefix else s


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Approximate token count (~4 chars/token), accelerated when possible."""
    if not text:
        return 0
    fast = accel.estimate_tokens(text)
    if fast is not None:
        return fast
    return math.ceil(len(text) / 4)


_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3
_FNV_MASK = 0xFFFFFFFFFFFFFFFF


def fnv1a(text: str) -> int:
    """FNV-1a 64-bit hash, accelerated via the native library when available.

    Used by the loop detector to turn a (tool, target, params) signature into a
    compact integer for cheap repeat detection. The pure-Python fallback yields
    the identical value as the C implementation.
    """
    fast = accel.fnv1a(text)
    if fast is not None:
        return fast
    h = _FNV_OFFSET
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & _FNV_MASK
    return h
