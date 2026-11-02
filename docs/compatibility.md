# Compatibility fixes

## CRT stream ownership

The installed loader passes a UCRT standard stream to `msvcrt.freopen_s`. It can also use the stream object itself as the output-pointer slot. Stock Wine treats that object as an msvcrt stream, corrupting its state.

`crt_adapter.c` recognizes only UCRT's three standard streams and calls their owning runtime's `freopen_s`. It avoids writing an output pointer over the stream. Other streams and invalid parameters follow the original msvcrt path. The patcher adds the adapter without replacing the original function and merges its unwind records into the PE exception table.

The probe checks ordinary msvcrt streams, UCRT streams, and the aliased output slot. Each case reads known bytes through the owning CRT, checks EOF and error state, and closes the stream.

## Exception dispatcher

The campaign decodes the call displacement at a fixed Windows offset inside `KiUserExceptionDispatcher`. Wine computes the same call arguments with a shorter instruction sequence.

`patch_dispatcher.py` adds an equivalent dispatcher entry in unused executable padding and redirects the export. It preserves Wine's handler, the original entry, and unwind behavior. The probe checks the instruction offset, a CPU exception, `RaiseException`, and nonvolatile register restoration through `RtlVirtualUnwind`.

## WinHTTP option 133

The campaign sets `WINHTTP_OPTION_ENABLE_HTTP_PROTOCOL` to zero on a session handle. That requests HTTP/1.1 or earlier, already supported by this Wine version, but its session option handler rejects the request with error 12009.

The adapter calls the original function first. It accepts only the otherwise rejected zero DWORD on a valid session. It validates the session with a read-only redirect-policy query and preserves the original result for unsupported protocols, invalid handles, and malformed inputs. Tests cover those boundaries and an actual loopback HTTP/1.1 request and response.

## Wine device

`randgrid_driver.c` runs in Wine's userspace driver host. It creates the `Randgrid` device and implements the observed buffered IOCTL `0x8231214c`. It is not a Linux kernel module.

`randgrid_protocol.c` derives the per-request key and nonce from the requester's PID, PEB, and Wine shared-user-data fields. It authenticates the 32-byte request with Ascon-128 v1.2 and returns the expected 24-byte authenticated reply. The implementation preserves the original request-size, output-capacity, prior-time-bucket, marker, and unknown-command behavior.

The frozen vector in `tests/handshake.json` comes from the original driver's response to a captured request. Host tests cover that response, input/output aliasing, short buffers, a modified authentication tag, a prior time bucket, an unexpected marker, and an unknown command. The Windows controller also checks the device in a live Wine process before starting the game.

Only the observed single-player campaign handshake is implemented. Multiplayer and online modes are unsupported. Unsupported IOCTLs fail without producing output. The [campaign validation record](validation.md#campaign-coverage) defines the actual gameplay coverage.

## Shader translation

VKD3D-Proton 3.1 is built with dxil-spirv revision `4e4c4be90b7e8008194ae70243d54c762aba021f`. Its newer control-flow reconstruction resolves a campaign shader that triggers `assert(frontier)` in the older structurizer. All 334 shaders captured before the failure convert with the new translator and pass independent SPIR-V validation.

The renderer is installed in Proton's source DLL directory, so normal prefix synchronization copies the intended version. Installing only a DLL in a prefix is insufficient: Proton replaces it on launch.

## Sparse CPU numbering

With some host CPUs offline, GE-Proton 11-11 can return a raw Linux CPU ID from `GetCurrentProcessorNumber` while `CallNtPowerInformation` initializes only an online-count-sized array. The campaign indexes that array by the reported CPU ID to obtain its current MHz. An out-of-range selection can read a zero MHz value and lead to division by zero during checkpoint loading.

The pinned Wine source shows the array fill and the topology parser in [`system.c`](https://github.com/ValveSoftware/wine/blob/c53678ab22a85f0fad3588dd34f0452a463bd015/dlls/ntdll/unix/system.c), and raw versus mapped processor IDs in [`thread.c`](https://github.com/ValveSoftware/wine/blob/c53678ab22a85f0fad3588dd34f0452a463bd015/dlls/ntdll/unix/thread.c). A live API probe on the test host confirmed that a thread on host CPU14 received ID14 while only records0–13 were initialized. A dense topology override returned IDs within the initialized array.

For campaign launches on a sparse host, the wrapper intersects the existing process affinity with online CPU IDs accepted by Wine's parser: IDs below the online CPU count, capped at 64. It maps that subset densely and gives the child matching affinity. For example, host CPUs `0-1,4-15` become `6s:0,1,4,5,6,7,8,9,10,11,12,13`. Host CPUs14/15 are excluded because this Wine parser rejects them. This reduces the available CPU count from fourteen to twelve and can affect performance. It does not enable offline CPUs or change system settings.

The wrapper retains SMT pairs when every selected core has two available threads; otherwise it keeps the selected CPUs with one reported thread per core. Dense hosts retain their normal topology. An explicit `WINE_CPU_TOPOLOGY` environment variable takes precedence and leaves affinity unchanged, so a custom mapping must itself fit the host and launch affinity. If the automatic mapping has no usable CPUs, the runner stops with a diagnostic before launching Wine. The host tests cover sparse numbering, affinity restrictions, SMT, dense hosts, explicit overrides, and an empty usable subset.

## Maintenance

The PE patchers reject unknown layouts, signed inputs, missing header space, and already patched images. The runner builder additionally requires the exact input hashes from GE-Proton 11-11. Upgrade the base by reviewing those assumptions and rerunning the runtime probes; do not disable the checks to accept another Wine version.
