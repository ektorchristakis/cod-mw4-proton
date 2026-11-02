# MW4-Proton

A Proton runner for the **Modern Warfare 4 single-player campaign only**, based on GE-Proton 11-11. Multiplayer and online modes are unsupported. It starts `sp26-cod.exe` from an existing Windows installation and supplies the Wine compatibility fixes needed by that build. Game files stay in their original location; the Wine prefix belongs on a Linux filesystem.

The runner includes a Wine device implementation, CRT and WinHTTP fixes, a compatible exception-dispatcher layout, and VKD3D-Proton 3.1 with a newer dxil-spirv translator. It does not contain game files, saves, the original Windows driver, or Microsoft DLLs.

## Install and launch

Download `MW4-Proton-0.1.0-overlay.tar.xz` and `SHA256SUMS` from the [0.1.0 release](https://github.com/ektorchristakis/cod-mw4-proton/releases/tag/v0.1.0). Installation needs Python 3.12 or newer, the Python package `pefile`, and GNU coreutils. Verify and extract the overlay, then run its installer:

```sh
sha256sum --check SHA256SUMS
tar -xf MW4-Proton-0.1.0-overlay.tar.xz
cd MW4-Proton-0.1.0-overlay
python3 tools/install-runner.py \
  --output "$HOME/.local/share/Steam/compatibilitytools.d/MW4-Proton-0.1.0"
```

The installer downloads the official GE-Proton base and verifies its pinned SHA-256. It refuses to replace an existing runner. See [build and installation](docs/build.md) for offline installation and the complete source build recipe.

For Steam, place the runner under `~/.local/share/Steam/compatibilitytools.d/`, restart Steam, add the existing `sp26/sp26-cod.exe` as a non-Steam game, and select **MW4-Proton 0.1.0** in its compatibility settings. Set the working directory to the installation root, one directory above `sp26`.

For UMU:

```sh
WINEPREFIX="$HOME/Games/prefixes/mw4" \
PROTONPATH="$HOME/.local/share/Steam/compatibilitytools.d/MW4-Proton-0.1.0" \
GAMEID=umu-default \
umu-run '/path/to/Call of Duty - Modern Warfare 4/sp26/sp26-cod.exe'
```

The wrapper starts the compatibility device, launches the campaign, waits for it to exit, and removes the temporary Wine service. It supplies the campaign's standard launch argument. Other executable names and Proton verbs pass through to GE-Proton.

Use a separate prefix for this game. The runtime DLL changes apply throughout that prefix. The wrapper prevents two campaign launches from sharing it at once. On hosts with offline CPUs and sparse CPU numbering, it applies a process-local CPU mapping; see [CPU topology](docs/compatibility.md#sparse-cpu-numbering) for the CPU-count tradeoff and override.

## Existing Windows progress

The campaign stores progress under the Windows user's `AppData/Local/Activision/Call of Duty/players/<profile>/SteamCloud`. Back up that directory before configuring shared saves.

The `sp26` and `7501` subdirectories hold the observed checkpoint and progression files. Those two directories can be linked from the Linux prefix to the existing Windows profile. Keep graphics, audio, and keybinding files private to each operating system. The runner itself never creates save links or overwrites a Windows profile.

## Compatibility

The supported target is campaign build `29465156`, executable `sp26-cod.exe`, with the offline loader already present in the installation. This is a campaign-specific implementation of the device requests observed in that build. Unknown requests fail. Support is limited to this single-player campaign build; multiplayer, online modes, and other builds are unsupported. See the [campaign-only device scope](docs/compatibility.md#wine-device) and [tested campaign coverage](docs/validation.md#campaign-coverage).

[Compatibility details](docs/compatibility.md) explains the fixes and their tests. [Validation](docs/validation.md) records the tested runtime, hardware, and gameplay coverage.

## Development

Development happens on `main`. Keep changes small, run `make check`, and exercise affected Windows probes through the assembled runner. Runtime changes also need a real campaign test. Release versions follow SemVer, with `VERSION` as the source of truth and tags named `vMAJOR.MINOR.PATCH`.

Project code is licensed under LGPL-2.1-or-later. Third-party code retains its own notices; see [THIRD_PARTY.md](THIRD_PARTY.md).
