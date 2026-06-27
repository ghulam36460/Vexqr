"""Native acceleration bridge: C / Assembly fast paths + Java performance layer.

The Python core is the brain; the heavy, repetitive work is offloaded to faster
runtimes when they are present:

  * ``libsentinel`` — a C shared library (with hand-tuned Assembly inner loops)
    that accelerates hot paths: token estimation, fuzzy-signature hashing for the
    loop detector, and ANSI stripping. Loaded via ``cffi`` if installed.
  * A Java 26 performance layer (``sentinel-perf.jar``) used for high-throughput,
    cross-platform fan-out (parallel tool dispatch, concurrent sub-agent
    monitoring). Bridged via ``jpype`` if installed.

Everything degrades gracefully: if a native component is missing, the pure-Python
implementation is used and the platform behaves identically (just slower on the
hot paths). This keeps ``pip install sentinel-core`` working with zero native
build steps, while ``pip install 'sentinel-core[accel]'`` unlocks the fast paths.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from .logger import get_logger

_log = get_logger("accel")


class NativeAccelerator:
    """Loads optional C/Assembly and Java accelerators; no-ops if absent."""

    def __init__(self) -> None:
        self._c = self._load_c_library()
        self._jvm_ready = False  # lazily started on first parallel dispatch

    # ---- C / Assembly fast paths -------------------------------------------------

    def _load_c_library(self) -> ctypes.CDLL | None:
        if os.environ.get("SENTINEL_NO_NATIVE"):
            return None
        names = {
            "linux": "libsentinel.so",
            "darwin": "libsentinel.dylib",
            "win32": "sentinel.dll",
        }
        lib_name = names.get(sys.platform, "libsentinel.so")
        here = Path(__file__).resolve().parent.parent / "accel"
        candidates = [here / lib_name, Path(lib_name)]
        for path in candidates:
            try:
                if path.exists():
                    lib = ctypes.CDLL(str(path))
                    lib.sentinel_estimate_tokens.restype = ctypes.c_uint64
                    lib.sentinel_estimate_tokens.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
                    lib.sentinel_fnv1a.restype = ctypes.c_uint64
                    lib.sentinel_fnv1a.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
                    _log.info("loaded native accelerator: %s", path.name)
                    return lib
            except OSError as exc:  # pragma: no cover - platform dependent
                _log.debug("native lib %s not usable: %s", path, exc)
        _log.debug("native C/Assembly accelerator not present; using pure Python")
        return None

    @property
    def has_native(self) -> bool:
        return self._c is not None

    def estimate_tokens(self, text: str) -> int | None:
        if self._c is None:
            return None
        try:
            data = text.encode("utf-8")
            return int(self._c.sentinel_estimate_tokens(data, len(data)))
        except Exception:  # pragma: no cover - defensive
            return None

    def fnv1a(self, text: str) -> int | None:
        """Native FNV-1a 64-bit hash used by the loop detector's fuzzy signature.

        Returns ``None`` when no native library is present so callers fall back
        to a pure-Python hash. The value matches the C implementation exactly.
        """
        if self._c is None:
            return None
        try:
            data = text.encode("utf-8")
            return int(self._c.sentinel_fnv1a(data, len(data)))
        except Exception:  # pragma: no cover - defensive
            return None

    # ---- Java 26 performance layer ----------------------------------------------

    def jvm_available(self) -> bool:
        """True if the Java performance layer can be bridged (jpype + jar present)."""
        if os.environ.get("SENTINEL_NO_JVM"):
            return False
        try:
            import jpype  # type: ignore  # noqa: F401
        except Exception:
            return False
        jar = Path(__file__).resolve().parent.parent / "perf" / "sentinel-perf.jar"
        return jar.exists()

    def ensure_jvm(self) -> bool:
        """Start the JVM bridge on demand. Returns True when the bridge is live."""
        if self._jvm_ready:
            return True
        if not self.jvm_available():
            return False
        try:  # pragma: no cover - requires a real JVM + jar
            import jpype  # type: ignore

            jar = Path(__file__).resolve().parent.parent / "perf" / "sentinel-perf.jar"
            if not jpype.isJVMStarted():
                jpype.startJVM(classpath=[str(jar)])
            self._jvm_ready = True
            _log.info("Java 26 performance layer online (%s)", jar.name)
            return True
        except Exception as exc:  # pragma: no cover
            _log.warning("Java performance layer unavailable: %s", exc)
            return False


accel = NativeAccelerator()
