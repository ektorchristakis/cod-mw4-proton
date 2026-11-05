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

## NVAPI memory reporting

Version `0.1.0-beta.2` replaces GE-Proton 11-11's DXVK-NVAPI 0.9.2 components with the official 0.9.3 release. Upstream 0.9.3 [changes available/free VRAM reporting](https://github.com/jp7677/dxvk-nvapi/releases/tag/v0.9.3) to better match Windows NVAPI. The builder installs the full applicable x86/x64 runtime set and its notices. It records the pinned archive and installed component hashes in the runner manifest.

This dependency correction does not establish the cause of every slowdown or demonstrate a sustained frame rate. The [validation record](validation.md#beta2-launcher-checks) distinguishes launcher observations from gameplay and performance qualification.

## DXGI memory budget

Beta.3 extends DXVK's existing `dxgi.maxDeviceMemory` option to cap the LOCAL budget returned by `IDXGIAdapter3::QueryVideoMemoryInfo` in the x64 DXGI component. Upstream uses the option for adapter descriptions alone. With a positive limit, the modified query returns the smaller of the driver budget and that limit. The code leaves the actual-usage calculation and NON_LOCAL reporting unchanged. This is an advisory report to the game, not an allocation, residency or physical VRAM limit.

The option's upstream default remains `0`. If an existing environment value or DXVK configuration file already sets a nonzero value, beta.3 also applies that value to the new LOCAL report. No hardware profile is chosen automatically. The manually selected `5120` and `4096` MiB values were investigated on one RTX 3060 Laptop GPU with 6 GiB VRAM. The 5120 MiB trial had drops and ended in the mid-20s; 4096 MiB deteriorated to about 13 FPS. Neither is a recommended performance preset or a demonstrated stable-30 fix. Other GPUs remain unqualified. See [beta.3 validation](validation.md#beta3-validation) for the distinction between API behavior and gameplay evidence.

Before changing the setting, retain the original `DXVK_CONFIG` value, if any. With no existing options, a shell can export:

```sh
export DXVK_CONFIG='dxgi.maxDeviceMemory = 5120'
```

That export applies to subsequent child processes from that shell. In Steam's launch options, the equivalent is:

```text
DXVK_CONFIG='dxgi.maxDeviceMemory = 5120' %command%
```

Retain existing options and separate assignments with semicolons. For example, an existing `dxvk.maxFrameRate = 60` becomes `dxvk.maxFrameRate = 60; dxgi.maxDeviceMemory = 5120`. This is an illustrative existing value, not a recommendation to add a frame limiter. Replace an existing memory-size assignment instead of adding conflicting duplicates. For that example, the complete Steam launch setting is:

```text
DXVK_CONFIG='dxvk.maxFrameRate = 60; dxgi.maxDeviceMemory = 5120' %command%
```

In Bottles, use environment key `DXVK_CONFIG` and the complete value without the shell's outer quote characters. For UMU, export the complete value in the launching shell or put the assignment on the same launch command. Keep the runner and prefix paths from the [launch instructions](../README.md#install-and-launch).

To return to the original configuration, close the game and restore the saved original environment value, or remove only the assignment added for this experiment. If there was no previous value, the environment variable can be removed. Removing an environment override may expose a nonzero value from a DXVK configuration file again. To explicitly select default reporting regardless of that file value, set `dxgi.maxDeviceMemory = 0` in the environment value while retaining its other assignments, then restart the game. Do not remove unrelated options, reset a prefix, change campaign content or restore an older shared save merely to revert this option. Runtime-version fallback is described in [Optional memory budget](../README.md#optional-memory-budget).

## Sparse CPU numbering

With some host CPUs offline, GE-Proton 11-11 can return a raw Linux CPU ID from `GetCurrentProcessorNumber` while `CallNtPowerInformation` initializes only an online-count-sized array. The campaign indexes that array by the reported CPU ID to obtain its current MHz. An out-of-range selection can read a zero MHz value and lead to division by zero during checkpoint loading.

The pinned Wine source shows the array fill and the topology parser in [`system.c`](https://github.com/ValveSoftware/wine/blob/c53678ab22a85f0fad3588dd34f0452a463bd015/dlls/ntdll/unix/system.c), and raw versus mapped processor IDs in [`thread.c`](https://github.com/ValveSoftware/wine/blob/c53678ab22a85f0fad3588dd34f0452a463bd015/dlls/ntdll/unix/thread.c). A live API probe on the test host confirmed that a thread on host CPU14 received ID14 while only records0–13 were initialized. A dense topology override returned IDs within the initialized array.

For campaign launches on a sparse host, the wrapper intersects the existing process affinity with online CPU IDs accepted by Wine's parser: IDs below the online CPU count, capped at 64. It maps that subset densely and gives the child matching affinity. For example, host CPUs `0-1,4-15` become `6s:0,1,4,5,6,7,8,9,10,11,12,13`. Host CPUs14/15 are excluded because this Wine parser rejects them. This reduces the available CPU count from fourteen to twelve and can affect performance. It does not enable offline CPUs or change system settings.

The wrapper retains SMT pairs when every selected core has two available threads; otherwise it keeps the selected CPUs with one reported thread per core. Dense hosts retain their normal topology. An explicit `WINE_CPU_TOPOLOGY` environment variable takes precedence and leaves affinity unchanged, so a custom mapping must itself fit the host and launch affinity. If the automatic mapping has no usable CPUs, the runner stops with a diagnostic before launching Wine. The host tests cover sparse numbering, affinity restrictions, SMT, dense hosts, explicit overrides, and an empty usable subset.

## Checkpoint content mismatch

If Resume loads the right mission but resets objectives, position, or equipment, close the game and preserve the original save before another autosave can replace it. Windows and Linux need matching campaign content as well as the same save. Reaching the menu or seeing the correct mission name does not establish that the checkpoint was accepted.

The observed Stranded failure was a content mismatch: the game read all 7,330,182 bytes of the checkpoint payload and its body validation succeeded, but the loaded script aggregate was `e909037b` while the checkpoint required `cd2bd106`. Loading the matching campaign patch made the aggregates agree. The user confirmed that the completed objectives, position, and loadout were restored. See the [recovery record](validation.md#checkpoint-recovery) for the observations and remaining limits.

### Restore the tested campaign patch

This manual example applies only to campaign executable build `29465156` with content build `13.1.29269899_874`, campaign application `7501`, and manifest version `31`. These are different identifiers for the tested executable and its content; they are not interchangeable version numbers. The runner supplies neither the content nor its version-cache file. A storefront repair or update has not been verified to restore this exact historical combination.

1. **Close the game and back up saves.** Close it on both operating systems. Make an independent backup of the original Windows `SteamCloud` directory and any existing Linux campaign saves before changing shared links or content. Retain these backups through the recovery check; a retry can write a new autosave.

2. **Confirm the installation before applying this example.** Establish that the installed campaign executable is the supported build `29465156`. In that installation's `sp26/ccsconfig.json`, check the `sp26` entry for `engineVersion` `13.1`, `ccsRestrict` `29269899_874`, and the application-`7501` CDN path. Its `gvsURL` and `configId` must also match the cache values shown below. The configuration values alone do not prove the executable build. If the executable build is unknown or any value differs, stop: do not transplant this patch or cache into another build or substitute an arbitrary newer patch.

3. **Download into an empty staging directory outside the game installation.** These are the four recorded official source links for the tested patch. Keep their filenames unchanged. The SHA-256 values below were recorded during this recovery; they are file-identity checks, not publisher-signed checksums. The links' continued availability is not guaranteed.

   | File | Recorded official source |
   | --- | --- |
   | `manifest_patch_pc_13.1.29269899_874.txt` | [Main manifest](https://objectstore-publishers-rex.prod.demonware.net/7501/activision/tu1/31/manifest_patch_pc_13.1.29269899_874.txt) |
   | `pack_patch_pc_13.1.29269899_874.bin` | [Main pack](https://objectstore-publishers-rex.prod.demonware.net/7501/activision/tu1/31/pack_patch_pc_13.1.29269899_874.bin) |
   | `dev_manifest_patch_pc_13.1.29269899_874.txt` | [Development manifest](https://objectstore-publishers-rex.prod.demonware.net/7501/activision/tu1/31/dev_manifest_patch_pc_13.1.29269899_874.txt) |
   | `dev_pack_patch_pc_13.1.29269899_874.bin` | [Development pack](https://objectstore-publishers-rex.prod.demonware.net/7501/activision/tu1/31/dev_pack_patch_pc_13.1.29269899_874.bin) |

4. **Check all four downloads.** From the staging directory containing those files, run:

   ```sh
   sha256sum --check <<'SHA256SUMS'
   42d2ce8ab9a5dec0248a2019919d31ac079ac0c07757af8f56bf5bcccec0f368  manifest_patch_pc_13.1.29269899_874.txt
   3308f656312280d64fcdab69da50b483bcb3fd9fd61b8c5339f851303dfd6752  pack_patch_pc_13.1.29269899_874.bin
   34cb5ba1a3e22ded8288594283fdfcf77314374fd80109a2387fd51562c9adae  dev_manifest_patch_pc_13.1.29269899_874.txt
   4d40b448aa6965546c62a7ff41e13b9d35507d202106d53ba9611dd946e7313b  dev_pack_patch_pc_13.1.29269899_874.bin
   SHA256SUMS
   ```

   All four must report `OK`. Stop if a file is missing or differs; do not install a partial or mismatched set.

5. **Back up the five destination files, then install the four checked downloads.** The tree below starts at the game installation root, one directory above `sp26`. Before copying, back up any existing files at these five exact paths to a separate directory outside `extccs`, preserving their relative paths. Record which paths were absent so rollback can remove only newly added files. Leave unrelated `extccs` files and other version directories alone. Create `sp26/main/extccs/31/` if needed and copy the four checked downloads there. Run the same checksum command from the installed `31/` directory and require four `OK` results again.

   ```text
   sp26/
     sp26-cod.exe
     ccsconfig.json
     main/extccs/
       version_patch_pc_13.1.29269899_874.json
       31/
         manifest_patch_pc_13.1.29269899_874.txt
         pack_patch_pc_13.1.29269899_874.bin
         dev_manifest_patch_pc_13.1.29269899_874.txt
         dev_pack_patch_pc_13.1.29269899_874.bin
   ```

6. **Write the version-cache record at the `extccs` root.** After preserving any existing file in step 5, create `sp26/main/extccs/version_patch_pc_13.1.29269899_874.json` with this content:

   ```json
   {
       "formatVersion": 1,
       "version": 31,
       "gvsURL": "https://rex-gvs.prod.demonware.net/v1/public/",
       "gvsConfigId": "452de38822126ed008205a38b00a57ab"
   }
   ```

   This record was locally constructed in the existing downloader's cache schema using the campaign configuration and manifest version. It was not downloaded as official version metadata. It was included in the working setup; its independent necessity was not isolated. Do not use it as a template for other content builds.

7. **Launch normally and check the recovered state.** Use the regular Steam or UMU launch documented in the [README](../README.md#install-and-launch), without an experimental content mount. Compare Resume with the preserved checkpoint's expected objectives, location, and loadout. Correct filenames and matching hashes establish the input files, not that the game selected them or accepted the save. If the mission starts fresh again, close the game, retain the original backup, and investigate before continuing to another autosave.

8. **Roll back if needed.** With the game closed on both systems, restore only the five named destination files from step 5. Remove a named destination file only if it was recorded as absent before this procedure. Preserve unrelated `extccs` content and other version directories; do not delete the whole `extccs` or `31` directory. If a retry changed the save, retain that changed copy separately before restoring the preserved original. Keep the backups until you have checked the result.

This procedure describes the setup used for the observed recovery and subsequent regular launch from the permanent installation. It does not qualify other checkpoints or builds, future save writes, a Windows boot and cross-OS save roundtrip, sustained performance, or stability. Do not bypass the script compatibility check or edit a save header to force acceptance: the successful repair loaded matching content without changing the campaign executable or suppressing validation.

## Maintenance

The PE patchers reject unknown layouts, signed inputs, missing header space, and already patched images. The runner builder additionally requires the exact input hashes from GE-Proton 11-11. Upgrade the base by reviewing those assumptions and rerunning the runtime probes; do not disable the checks to accept another Wine version.
