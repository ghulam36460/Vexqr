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
  LIB := libaegix.dylib
else
  LIB := libaegix.so
endif

.PHONY: all portable clean

all: $(LIB)

$(LIB): aegix_accel.c aegix_count.S
	$(CC) $(CFLAGS) -DAEGIX_ASM aegix_accel.c aegix_count.S -o $(LIB)

portable: aegix_accel.c
	$(CC) $(CFLAGS) aegix_accel.c -o $(LIB)

clean:
	rm -f libaegix.so libaegix.dylib aegix.dll
