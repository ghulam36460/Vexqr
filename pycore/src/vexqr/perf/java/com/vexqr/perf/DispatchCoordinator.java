package com.vexqr.perf;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Java performance layer: high-throughput, cross-platform fan-out coordinator.
 *
 * The Python core owns all decision logic. This class is invoked (via jpype)
 * only to coordinate large parallel batches of independent tool dispatches and
 * concurrent sub-agent monitoring, where the JVM's mature concurrency model and
 * consistent cross-platform behavior provide a measurable speedup over the
 * pure-asyncio fallback.
 *
 * It performs no security decisions and enforces no policy: scope, risk and
 * audit are owned by the separately-maintained security layer.
 *
 * Implementation note: this uses a per-task virtual thread executor
 * ({@link Executors#newVirtualThreadPerTaskExecutor()}), a stable, non-preview
 * API since JDK 21. Parallelism is bounded by a {@link Semaphore} so the JVM
 * runs at most {@code maxParallelism} dispatches in flight at once.
 */
public final class DispatchCoordinator {

    private final AtomicLong completed = new AtomicLong();

    /**
     * Run a batch of dispatch tasks concurrently using virtual threads,
     * bounded by {@code maxParallelism}.
     *
     * @param tasks          dispatch units (opaque to this layer; executed by callbacks)
     * @param maxParallelism upper bound on concurrent in-flight tasks
     * @return number of tasks that completed successfully
     * @throws InterruptedException if interrupted while awaiting completion
     */
    public long runBatch(List<Runnable> tasks, int maxParallelism) throws InterruptedException {
        Semaphore gate = new Semaphore(Math.max(1, maxParallelism));
        List<Future<?>> futures = new ArrayList<>(tasks.size());

        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (Runnable task : tasks) {
                Callable<Void> unit = () -> {
                    gate.acquire();
                    try {
                        task.run();
                        completed.incrementAndGet();
                    } finally {
                        gate.release();
                    }
                    return null;
                };
                futures.add(executor.submit(unit));
            }
            // Closing the try-with-resources executor blocks until all tasks
            // finish (ExecutorService.close() awaits termination).
        }

        // Surface the first failure, if any, so callers can react.
        for (Future<?> f : futures) {
            try {
                f.get();
            } catch (ExecutionException e) {
                throw new RuntimeException("dispatch task failed", e.getCause());
            }
        }

        return completed.get();
    }

    public long completedCount() {
        return completed.get();
    }
}
