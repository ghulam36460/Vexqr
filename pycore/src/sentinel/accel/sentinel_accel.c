/*
 * sentinel native accelerator — C hot paths for the Python core.
 *
 * Exposes a tiny, stable C ABI loaded by sentinel.util.accel via cffi/ctypes.
 * The token estimator's inner counting loop is delegated to hand-tuned
 * Assembly (see sentinel_count.S) when built with SENTINEL_ASM; otherwise a
 * portable C loop is used. Either way the result matches the pure-Python
 * heuristic (ceil(bytes / 4)) so behavior is identical, just faster.
 *
 * Build (Linux):
 *   cc -O3 -shared -fPIC -DSENTINEL_ASM sentinel_accel.c sentinel_count.S -o libsentinel.so
 * Build (portable C only):
 *   cc -O3 -shared -fPIC sentinel_accel.c -o libsentinel.so
 */

#include <stddef.h>
#include <stdint.h>

#ifdef SENTINEL_ASM
/* Implemented in sentinel_count.S — counts bytes via a tight SIMD-friendly loop. */
extern uint64_t sentinel_count_bytes(const char *data, size_t len);
#else
static uint64_t sentinel_count_bytes(const char *data, size_t len) {
    (void)data;
    return (uint64_t)len;
}
#endif

/* ceil(len / 4): conservative ~4 chars/token estimate, matching the Python path. */
uint64_t sentinel_estimate_tokens(const char *data, size_t len) {
    uint64_t bytes = sentinel_count_bytes(data, len);
    return (bytes + 3u) / 4u;
}

/* Fast FNV-1a hash used by the loop detector's fuzzy signature comparison. */
uint64_t sentinel_fnv1a(const char *data, size_t len) {
    uint64_t h = 14695981039346656037ULL;
    for (size_t i = 0; i < len; i++) {
        h ^= (uint8_t)data[i];
        h *= 1099511628211ULL;
    }
    return h;
}
