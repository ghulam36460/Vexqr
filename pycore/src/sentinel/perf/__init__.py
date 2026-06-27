"""Java 26 performance layer artifacts (optional).

Holds the Java source for ``sentinel-perf.jar`` (built separately, see
README.md). Bridged from the Python core via jpype in ``sentinel.util.accel``.
Optional: the core falls back to asyncio fan-out when the jar/jpype are absent.
"""
