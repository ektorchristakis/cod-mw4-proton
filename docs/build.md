# Build MW4-Proton

Run the source-build and release-packaging commands below from the repository root on x86_64 Linux. The build needs Python 3.12 or newer with `pefile`, GNU Make, GNU coreutils, GNU tar, curl, a native C compiler, MinGW-w64 GCC and G++, MinGW DDK headers, MinGW WIDL, Git, Meson, Ninja, and glslang. The renderer uses `x86_64-w64-mingw32-*` tools. No game installation is needed to build the runner.

Download and extract the pinned upstream base:

```sh
mkdir -p build/downloads build/base
curl --fail --location \
  https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-11/GE-Proton11-11-x86_64.tar.gz \
  --output build/downloads/GE-Proton11-11-x86_64.tar.gz
printf '%s  %s\n' \
  aa85986cada5709aa8bbfa8add7f3bfb925cbe15710c98995898d308ff2ca3c1 \
  build/downloads/GE-Proton11-11-x86_64.tar.gz | sha256sum --check
tar -xf build/downloads/GE-Proton11-11-x86_64.tar.gz -C build/base
```

Build the renderer and assemble a new runner directory:

```sh
tools/build-vkd3d.sh --output build/renderer
python3 tools/build-runner.py \
  --base-runner build/base/GE-Proton11-11-x86_64 \
  --renderer build/renderer \
  --output "dist/MW4-Proton-$(cat VERSION)"
make check
```

Both tools refuse an existing output. The renderer keeps source and intermediate files under `build/vkd3d`; `--work-dir` selects another location. It builds VKD3D-Proton 3.1 with dxil-spirv revision `4e4c4be90b7e8008194ae70243d54c762aba021f`. That revision supplies the newer control-flow reconstruction required by a campaign shader. The build uses `debugoptimized`, disables trace instrumentation, normalizes compiler paths, and strips debug sections from the installed DLL copies while preserving their zero PE timestamps. The build directory retains full symbols.

The runner builder verifies the three stock Wine DLLs against their pinned GE hashes, runs `make all`, and copies the base with `cp -a --reflink=auto`. It patches only the copied `msvcrt.dll`, `ntdll.dll`, and `winhttp.dll`, installs the renderer where Proton's prefix synchronization reads it, adds the Wine driver and controller, and installs the launcher wrapper. The original Proton launcher becomes `proton-base`; `toolmanifest.vdf` retains Steam runtime app ID `4183110`. Neither build tool launches Wine or changes a prefix.

The package manifest is `files/share/mw4/manifest.json`. It records relative paths, source revisions, source-file hashes, input DLL hashes, and replaced-file hashes. The patch manifests record the original and added entry points and unwind-table details. `files/share/mw4/source` contains the project's corresponding source snapshot.

`make check` runs host-side protocol tests and builds the Windows probes. Run those probes and the actual campaign through Steam or UMU in a separate test prefix before labeling a release playable. Compilation and SPIR-V validation alone do not establish successful rendering, checkpoint loading, or gameplay.

## Package a release overlay

The downloadable package is an overlay containing this project's binaries and source, the rebuilt renderer, and the renderer's complete corresponding source. It excludes GE binaries. The installer downloads the official GE release and verifies its SHA-256 before assembling a full runner locally.

```sh
python3 tools/package-overlay.py \
  --renderer build/renderer \
  --renderer-source build/vkd3d/source \
  --output "dist/MW4-Proton-$(cat VERSION)-overlay"
tar -C dist -cJf "dist/MW4-Proton-$(cat VERSION)-overlay.tar.xz" \
  "MW4-Proton-$(cat VERSION)-overlay"
(cd dist && sha256sum "MW4-Proton-$(cat ../VERSION)-overlay.tar.xz" > SHA256SUMS)
(cd dist && sha256sum --check SHA256SUMS)
```

The `SHA256SUMS` file names the archive by basename, so a player can verify both downloaded release files from one directory. `package-overlay.py` runs `make all`, checks the renderer’s hashes and source pins, and includes every tracked file from its source tree and recursive submodules in `renderer/source.tar.xz`. The source archive includes `SOURCE-MANIFEST.json` with the exact revisions. The renderer archive rejects staged and unstaged changes to tracked files in VKD3D-Proton and its submodules. It archives tracked files at the pinned revisions; untracked renderer files are omitted. This project's selected source files come from the current checkout and are hash-checked for changes during packaging; the packager does not require a clean project Git tree. Its four compiled payload files are recorded in `payload/manifest.json`. `release-manifest.json` records the renderer, payload, and source-archive hashes.

After extracting the overlay, change into its root directory and run its installer. Installation needs Python 3.12 or newer, `pefile`, GNU coreutils, and enough space for the GE archive, its temporary extraction, and the assembled runner. GNU tar is also needed to extract the downloaded overlay; a compiler is unnecessary for installation:

```sh
python3 tools/install-runner.py \
  --output "$HOME/.local/share/Steam/compatibilitytools.d/MW4-Proton-$(cat VERSION)"
```

The installer caches the verified upstream archive under `$XDG_CACHE_HOME/mw4-proton`, or `~/.cache/mw4-proton` when that variable is unset. `--cache DIRECTORY` changes that location. For an offline installation, pass `--base-runner` with an already extracted GE-Proton 11-11 directory. This path checks the same three DLL hashes and runtime metadata as the local builder. Installation refuses to replace an existing runner and does not launch Wine or change a prefix.

## Rebuild the included renderer source

The pinned Git build above is the release recipe. To build the included renderer source offline, install the same build dependencies and run these commands from the root of the extracted release overlay (`MW4-Proton-0.1.0-overlay`):

```sh
mkdir -p build/included-source
tar -xf renderer/source.tar.xz -C build/included-source
meson setup build/included-x64 build/included-source/vkd3d-proton \
  --cross-file build/included-source/vkd3d-proton/build-win64.txt \
  --buildtype debugoptimized \
  -Denable_tests=false -Denable_extras=false -Denable_trace=false \
  -Dc_link_args=-Wl,--no-insert-timestamp \
  -Dcpp_link_args=-Wl,--no-insert-timestamp
meson compile -C build/included-x64
```

The two DLLs are under `build/included-x64/libs/d3d12/` and `libs/d3d12core/`. An archive build has no Git metadata, so upstream's fallback version strings differ from the release build. `tools/build-vkd3d.sh` supplies the compiler path normalization and stripping steps used for the packaged DLLs.

Publish the overlay and the generated `dist/SHA256SUMS` together after runtime qualification. Keep game files, original drivers, shader captures, saves, icons, diagnostic recordings, and local toolchains out of the package. A full runner assembled for local use contains the upstream GE distribution; publishing that full directory would additionally require covering the corresponding source and notices of every redistributed GE component.
