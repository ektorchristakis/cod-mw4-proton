# MW4-Proton

A Proton runner for the **Modern Warfare 4 single-player campaign only**, based on GE-Proton 11-11. It targets campaign build `29465156` and starts `sp26-cod.exe` from an existing Windows installation with the offline loader already present. Multiplayer, online modes, and other game builds are unsupported. Game files stay in their original location; use a dedicated Wine prefix on a Linux filesystem.

The runner includes a Wine device implementation, CRT and WinHTTP fixes, a compatible exception-dispatcher layout, and VKD3D-Proton 3.1 with a newer dxil-spirv translator. It does not contain game files, saves, the original Windows driver, or Microsoft DLLs.

The software is supplied without warranty. Account restrictions, suspensions, or bans cannot be ruled out; see the [warranty and liability notice](DISCLAIMER.md).

## Install and launch

You need the existing campaign installation, Python 3.12 or newer with the `pefile` package, GNU coreutils and GNU tar, and either Steam or `umu-run` to launch the installed runner. Download `MW4-Proton-0.1.0-overlay.tar.xz` and `SHA256SUMS` from the [0.1.0 release](https://github.com/ektorchristakis/cod-mw4-proton/releases/tag/v0.1.0). From the directory containing both downloads, verify and extract the overlay, then run its installer:

```sh
sha256sum --check SHA256SUMS
tar -xf MW4-Proton-0.1.0-overlay.tar.xz
cd MW4-Proton-0.1.0-overlay
python3 tools/install-runner.py \
  --output "$HOME/.local/share/Steam/compatibilitytools.d/MW4-Proton-0.1.0"
```

The installer downloads the official GE-Proton base and verifies its pinned SHA-256. It refuses to replace an existing runner. See [build and installation](docs/build.md) for offline installation and the complete source build recipe.

For Steam, install under `~/.local/share/Steam/compatibilitytools.d/` as shown above, then restart Steam. If your Steam installation uses another data directory, install under its `compatibilitytools.d/` instead. Add the existing `sp26/sp26-cod.exe` as a non-Steam game, select **MW4-Proton 0.1.0** in its compatibility settings, and set the shortcut’s **Start In** directory to the game installation root, one directory above `sp26`. Use a separate Steam shortcut and prefix for this game.

For UMU, install `umu-run` and replace the example game path with the absolute path to your existing installation. `WINEPREFIX` names this game’s dedicated Linux prefix:

```sh
WINEPREFIX="$HOME/Games/prefixes/mw4" \
PROTONPATH="$HOME/.local/share/Steam/compatibilitytools.d/MW4-Proton-0.1.0" \
GAMEID=umu-default \
umu-run '/path/to/Call of Duty - Modern Warfare 4/sp26/sp26-cod.exe'
```

The wrapper starts the compatibility device, launches the campaign with its standard argument, waits for it to exit, and removes the temporary Wine service. Other executable names and Proton verbs pass through to GE-Proton without this campaign device; that pass-through does not add support for other game modes.

Use a separate prefix for this game. The runtime DLL changes apply throughout that prefix. The wrapper prevents two campaign launches from sharing it at once. On hosts with offline CPUs and sparse CPU numbering, it applies a process-local CPU mapping; see [CPU topology](docs/compatibility.md#sparse-cpu-numbering) for the CPU-count tradeoff and override.

## Existing Windows progress

The campaign stores observed checkpoint and progression files under the Windows user’s `AppData/Local/Activision/Call of Duty/players/<profile>/SteamCloud/sp26` and `.../SteamCloud/7501`. `SteamCloud` is a directory name here, not a promise of automatic cloud synchronization. Back up the Windows `SteamCloud` directory before changing save paths.

Sharing progress is optional and manual. The corresponding location in a Linux Wine prefix is typically `<prefix>/drive_c/users/<Wine user>/AppData/Local/Activision/Call of Duty/players/<profile>/SteamCloud/`; inspect the actual Wine user and profile names first. For UMU, `<prefix>` is the `WINEPREFIX` shown above; for Steam, find the `pfx` directory in that non-Steam shortcut’s compatibility data. With the game closed on both systems, back up the Windows `SteamCloud` directory and any existing Linux `sp26` or `7501` directories. Inspect and record the exact source and destination paths. Move existing Linux `sp26` or `7501` directories aside under distinct backup names outside the Linux `SteamCloud` directory; do not delete them. Create links at the original Linux `sp26` and `7501` path names pointing to the matching directories in the Windows profile, and confirm both links resolve to the intended targets before launching. Sharing this way lets the game write to the Windows profile, so retain the backups. To stop sharing, close the game on both systems, remove those Linux-side links, and restore the moved-aside Linux directories. Keep graphics, audio, and keybinding files private to each operating system. The runner never creates save links or synchronizes profiles; this manual shared-link workflow has not been qualified for ongoing cross-OS use.

## Compatibility

The campaign-specific device implements requests observed in build `29465156`; unknown requests fail. Testing so far covers the menu, Mayhem cinematic playback, and a Stranded checkpoint with movement, mouse look, pause/resume, and volume control. Later missions, campaign completion, and stable frame rate are not yet established. The [campaign-only device scope](docs/compatibility.md#wine-device) and [tested campaign coverage](docs/validation.md#campaign-coverage) give the exact limits.

[Compatibility details](docs/compatibility.md) explains the fixes and their tests. [Validation](docs/validation.md) records the tested runtime, hardware, and gameplay coverage.

## Development

Development happens on `main`. Keep changes small, run `make check`, and exercise affected Windows probes through the assembled runner. Runtime changes also need a real campaign test. Release versions follow SemVer, with `VERSION` as the source of truth and tags named `vMAJOR.MINOR.PATCH`.

Project code is licensed under LGPL-2.1-or-later. Third-party code retains its own notices; see [THIRD_PARTY.md](THIRD_PARTY.md).
