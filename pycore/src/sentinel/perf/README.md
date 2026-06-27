# Java 26 performance layer

This directory hosts the optional Java performance layer used *alongside* the
Python core for high-throughput, cross-platform, performance-critical paths:
parallel tool dispatch fan-out and concurrent sub-agent monitoring.

The Python core bridges to it via `jpype` (see `sentinel.util.accel`). It is
entirely optional: when the `sentinel-perf.jar` is absent or `jpype` is not
installed, the router falls back to a bounded `asyncio` gather with identical
behavior.

## Build

Requires JDK 26+.

```bash
javac -d out java/com/sentinel/perf/DispatchCoordinator.java
jar --create --file sentinel-perf.jar -C out .
```

Place the resulting `sentinel-perf.jar` in this directory. The core detects and
loads it automatically.
