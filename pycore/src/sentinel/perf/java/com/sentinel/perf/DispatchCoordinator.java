package com.sentinel.perf;

import java.util.List;
import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Java 26 performance layer: high-throughput, cross-platform fan-out coordinator.
 *
 * The Python core owns all decision logic. This class is invoked (via jpype)
 * only to coordinate large parallel batches of independent tool dispatches and
 * concurrent sub-agent monitoring, where the JVM's mature concurrency model and
 * consistent cross-platform behavior provide a measurable speedup over the
 * pure-asyncio fallback.
 *
 * It performs no security decisions and enforces no policy: scope, risk and
 * audit are owned by the separately-maintained security layer.
 */
public final class DispatchCoordinator {

    private final AtomicLong completed = new AtomicLong();

    /**
     * Run a batch of dispatch tasks concurrently using virtual threads + a
     * structured concurrency scope, bounded by {@code maxParallelism}.
     *
     * @param tasks          dispatch units (opaque to this layer; executed by callbacks)
     * @param maxParallelism upper bound on concurrent in-flight tasks
     * @return number of tasks that completed successfully
     */
    public long runBatch(List<Runnable> tasks, int maxParallelism) throws InterruptedException {
        java.util.concurrent.Semaphore gate = new java.util.concurrent.Semaphore(Math.max(1, maxParallelism));
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            for (Runnable task : tasks) {
                scope.fork(() -> {
                    gate.acquire();
                    try {
                        task.run();
                        completed.incrementAndGet();
                    } finally {
                        gate.release();
                    }
                    return null;
                });
            }
            scope.join();
            scope.throwIfFailed();
        }
        return completed.get();
    }

    public long completedCount() {
        return completed.get();
    }
}
