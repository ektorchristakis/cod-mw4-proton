MINGW_CC ?= x86_64-w64-mingw32-gcc
MINGW_DDK ?= $(dir $(shell $(MINGW_CC) -print-file-name=libntoskrnl.a))../include/ddk
HOST_CC ?= cc
PYTHON ?= python3
CFLAGS := -std=c11 -O2 -Wall -Wextra -Werror
INCLUDES := -Isrc -Ivendor
PROTOCOL := src/randgrid_protocol.c vendor/ascon/aead.c
PE_FLAGS := -Wl,--no-insert-timestamp
ADAPTER_FLAGS := -shared -nostdlib -fno-stack-protector -Wl,--entry,0

.PHONY: all check clean
all: build/randgrid.sys build/controller.exe build/crt_adapter.dll build/winhttp_adapter.dll \
     build/crt_probe.exe build/dispatcher_probe.exe build/winhttp_probe.exe

build:
	mkdir -p $@

build/randgrid.sys: src/randgrid_driver.c $(PROTOCOL) src/randgrid_protocol.h | build
	$(MINGW_CC) $(CFLAGS) $(INCLUDES) -I"$(MINGW_DDK)" $(PE_FLAGS) -shared -nostdlib -fno-builtin \
	    -fno-stack-protector -Wl,--subsystem,native -Wl,--entry,DriverEntry \
	    -o $@ src/randgrid_driver.c $(PROTOCOL) -lntoskrnl

build/controller.exe: src/controller.c $(PROTOCOL) src/randgrid_protocol.h | build
	$(MINGW_CC) $(CFLAGS) $(INCLUDES) $(PE_FLAGS) -municode \
	    -o $@ src/controller.c $(PROTOCOL) -ladvapi32

build/crt_adapter.dll: src/crt_adapter.c | build
	$(MINGW_CC) $(CFLAGS) $(PE_FLAGS) $(ADAPTER_FLAGS) -ffreestanding -fno-builtin \
	    -Wl,--disable-auto-import -o $@ $<

build/winhttp_adapter.dll: src/winhttp_adapter.c | build
	$(MINGW_CC) $(CFLAGS) $(PE_FLAGS) $(ADAPTER_FLAGS) -Wl,--image-base,0x180000000 -o $@ $<

build/crt_probe.exe: tests/crt_probe.c | build
	$(MINGW_CC) $(CFLAGS) $(PE_FLAGS) -o $@ $<

build/dispatcher_probe.exe: tests/dispatcher_probe.c | build
	$(MINGW_CC) $(CFLAGS) $(PE_FLAGS) -o $@ $< -lntdll

build/winhttp_probe.exe: tests/winhttp_probe.c | build
	$(MINGW_CC) $(CFLAGS) $(PE_FLAGS) -o $@ $< -lwinhttp -lws2_32

build/protocol.so: $(PROTOCOL) src/randgrid_protocol.h | build
	$(HOST_CC) $(CFLAGS) $(INCLUDES) -shared -fPIC -o $@ $(PROTOCOL)

check: all build/protocol.so
	$(PYTHON) -m unittest discover -s tests -p '*_test.py'

clean:
	rm -rf build
