"""Java performance layer artifacts (optional).

Holds the Java source for ``vexqr-perf.jar`` (built separately, see
README.md). Bridged from the Python core via jpype in ``vexqr.util.accel``.
Optional: the core falls back to asyncio fan-out when the jar/jpype are absent.
"""
