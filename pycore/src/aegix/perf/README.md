# Java performance layer

This directory hosts the optional Java performance layer used *alongside* the
Python core for high-throughput, cross-platform, performance-critical paths:
parallel tool dispatch fan-out and concurrent sub-agent monitoring.

The Python core bridges to it via `jpype` (see `aegix.util.accel`). It is
entirely optional: when the `aegix-perf.jar` is absent or `jpype` is not
installed, the router falls back to a bounded `asyncio` gather with identical
behavior.

## Build

Requires **JDK 21+** (uses virtual threads via
`Executors.newVirtualThreadPerTaskExecutor()`, a stable, non-preview API since
JDK 21 — no `--enable-preview` flag needed).

```bash
javac -d out java/com/aegix/perf/DispatchCoordinator.java
jar --create --file aegix-perf.jar -C out .
```

Place the resulting `aegix-perf.jar` in this directory. The core detects and
loads it automatically.
