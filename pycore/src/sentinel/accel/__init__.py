"""Native C/Assembly accelerator artifacts.

This package holds the source for the optional ``libsentinel`` shared library
(C + hand-tuned Assembly). It is built via the Makefile here and loaded at
runtime by ``sentinel.util.accel`` when present. The Python core works without
it via a pure-Python fallback.
"""
