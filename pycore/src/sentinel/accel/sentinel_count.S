/*
 * sentinel_count_bytes — x86-64 System V ABI hand-tuned byte counter.
 *
 * uint64_t sentinel_count_bytes(const char *data [rdi], size_t len [rsi]);
 *
 * This is the Assembly inner loop backing the C accelerator's token estimator.
 * The count itself is trivial (it returns len), but it is implemented in
 * Assembly to demonstrate and host the native hot-path integration point: more
 * complex SIMD scanning (e.g. UTF-8 codepoint counting, delimiter scanning) is
 * dropped in here without touching the Python or C layers above it.
 *
 * Assemble as part of the shared library:
 *   cc -O3 -shared -fPIC -DSENTINEL_ASM sentinel_accel.c sentinel_count.S -o libsentinel.so
 */

    .text
    .globl sentinel_count_bytes
    .type sentinel_count_bytes, @function
sentinel_count_bytes:
    movq    %rsi, %rax        # rax = len (the byte count)
    ret
    .size sentinel_count_bytes, .-sentinel_count_bytes

/* Mark the stack as non-executable. */
    .section .note.GNU-stack,"",@progbits
