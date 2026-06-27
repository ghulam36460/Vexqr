# Build the optional C/Assembly accelerator shared library.
#
# The Python core runs fine without this (pure-Python fallback). Building it
# unlocks the native fast paths used by sentinel.util.accel.
#
#   make            # build with the hand-tuned Assembly inner loop (x86-64)
#   make portable   # build portable C only (any arch)
#   make clean

CC ?= cc
CFLAGS ?= -O3 -shared -fPIC
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
  LIB := libsentinel.dylib
else
  LIB := libsentinel.so
endif

.PHONY: all portable clean

all: $(LIB)

$(LIB): sentinel_accel.c sentinel_count.S
	$(CC) $(CFLAGS) -DSENTINEL_ASM sentinel_accel.c sentinel_count.S -o $(LIB)

portable: sentinel_accel.c
	$(CC) $(CFLAGS) sentinel_accel.c -o $(LIB)

clean:
	rm -f libsentinel.so libsentinel.dylib sentinel.dll
