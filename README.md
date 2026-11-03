# MW4-Proton

An experimental beta Proton runner for the **Modern Warfare 4 single-player campaign only**, based on GE-Proton 11-11. It targets campaign build `29465156` and starts `sp26-cod.exe` from an existing Windows installation with the offline loader already present. Multiplayer, online modes, and other game builds are unsupported. Game files stay in their original location; use a dedicated Wine prefix on a Linux filesystem.

The runner includes a Wine device implementation, CRT and WinHTTP fixes, a compatible exception-dispatcher layout, VKD3D-Proton 3.1 with a newer dxil-spirv translator, and DXVK-NVAPI 0.9.3 with its upstream memory-reporting corrections. It does not contain game files, saves, the original Windows driver, or Microsoft DLLs.

Testing is incomplete. This beta is for users willing to try the observed campaign path; stable performance, the complete campaign, audible quality, and a shared-save roundtrip between Linux and Windows remain unqualified. Native Steam and Flatpak Bottles 67.5 reached the campaign menu with beta.2; Resume and movement were not qualified in either client session. See the [beta.2 launcher checks](docs/validation.md#beta2-launcher-checks) and the earlier [test record and gaps](docs/validation.md).

The software is supplied without warranty. Account restrictions, suspensions, or bans cannot be ruled out; see the [warranty and liability notice](DISCLAIMER.md).

## Install and launch

You need the existing campaign installation, Python 3.12 or newer with the `pefile` package, GNU coreutils, GNU tar and `xz`, plus Steam, Bottles, or `umu-run`. Download `MW4-Proton-0.1.0-beta.2-overlay.tar.xz` and `SHA256SUMS` from the [0.1.0-beta.2 release](https://github.com/ektorchristakis/cod-mw4-proton/releases/tag/v0.1.0-beta.2). From the directory containing both downloads, verify and extract the overlay:

```sh
sha256sum --check SHA256SUMS
tar -xf MW4-Proton-0.1.0-beta.2-overlay.tar.xz
cd MW4-Proton-0.1.0-beta.2-overlay
```

For Steam, start Steam once if it is newly installed. Choose **one** command below: install a new runner, or register an existing assembled runner without another copy. If both native and Flatpak Steam are present, add `--steam native` or `--steam flatpak` to your chosen command before running it. Add `--dry-run` to inspect the destination first, then remove that flag to install.

**New runner:**

```sh
python3 tools/install-steam.py
```

**Reuse an existing assembled runner:** Keep its directory in place after registration. If Flatpak Steam cannot read that directory outside its sandbox, grant read access to that specific folder before registering it. Use the runner's resolved absolute path in both commands; if it is a symlink, `realpath /path/to/runner` shows that path:

```sh
flatpak override --user \
  --filesystem='/absolute/path/to/MW4-Proton-0.1.0-beta.2:ro' \
  com.valvesoftware.Steam
```

Native Steam needs no Flatpak grant. Once the selected Steam installation can read the runner, register it with one command, adding the `--steam` selection above if needed:

```sh
python3 tools/install-steam.py \
  --runner '/absolute/path/to/MW4-Proton-0.1.0-beta.2'
```

For either a new or reused runner, Flatpak Steam also needs access to the existing game installation. If that directory is outside its current filesystem permissions, grant read/write access to that specific installation root, one directory above `sp26`. Use its resolved absolute path; `realpath '/path/to/Call of Duty - Modern Warfare 4'` shows it:

```sh
flatpak override --user \
  --filesystem='/absolute/path/to/Call of Duty - Modern Warfare 4:rw' \
  com.valvesoftware.Steam
```

This grants access without copying game files. If you later link saves from outside the installation, grant those resolved save directories their own read/write access separately.

Restart Steam after installation. Add the existing `sp26/sp26-cod.exe` as a non-Steam game, select **MW4-Proton 0.1.0-beta.2** in its Compatibility settings, and set **Start In** to the installation root, one directory above `sp26`. Use a separate shortcut and prefix for this game. Steam installs Steam Linux Runtime 4 on first launch if needed; let that download finish.

For Bottles, start Bottles once and close it, then follow [Bottles installation](docs/bottles.md) to choose **one installer command before running it** from the extracted overlay. Include `--runner` if reusing an assembled runner and `--game` if Flatpak needs access to an external game; combine both flags in that one command when needed. The guide also explains how to select **MW4-Bottles-0.1.0-beta.2**, configure its DLL switches, and add the executable.

Both installers download the official GE-Proton base when needed, verify its pinned SHA-256, and refuse to replace an existing runner. See [build and installation](docs/build.md) for offline installation and the complete source build recipe.

The campaign installation also needs its matching content patch. A missing patch can leave the menu and mission playable while silently rejecting an existing checkpoint and starting the mission again. The runner installer does not supply or verify game content. Before importing Windows progress, see [checkpoint content mismatch](docs/compatibility.md#checkpoint-content-mismatch) for the exact-build checks and the tested manual repair using official content files and a locally constructed version cache.

For a standalone UMU setup, install `umu-run`. If you already have an assembled runner, use its actual path as `PROTONPATH` and skip the installation below. Otherwise, install the runner from the extracted overlay into a new dedicated directory:

```sh
python3 tools/install-runner.py \
  --output "$HOME/Games/runners/MW4-Proton-0.1.0-beta.2"
```

This installation needs no Steam client or Steam data directory. Launch with that same runner path, replacing the game path with the absolute path to your existing installation. `WINEPREFIX` names this game's separate Linux prefix:

```sh
WINEPREFIX="$HOME/Games/prefixes/mw4" \
PROTONPATH="$HOME/Games/runners/MW4-Proton-0.1.0-beta.2" \
GAMEID=umu-default \
umu-run '/path/to/Call of Duty - Modern Warfare 4/sp26/sp26-cod.exe'
```

The wrapper starts the compatibility device, launches the campaign with its standard argument, waits for it to exit, and removes the temporary Wine service. Other executable names and Proton verbs pass through to GE-Proton without this campaign device; that pass-through does not add support for other game modes.

Use a separate prefix for this game. The runtime DLL changes apply throughout that prefix. The wrapper prevents two campaign launches from sharing it at once. On hosts with offline CPUs and sparse CPU numbering, it applies a process-local CPU mapping; see [CPU topology](docs/compatibility.md#sparse-cpu-numbering) for the CPU-count tradeoff and override.

## Existing Windows progress

The campaign stores observed checkpoint and progression files under the Windows user’s `AppData/Local/Activision/Call of Duty/players/<profile>/SteamCloud/sp26` and `.../SteamCloud/7501`. `SteamCloud` is a directory name here, not a promise of automatic cloud synchronization. Back up the Windows `SteamCloud` directory before changing save paths.

Windows and Linux must load matching campaign content as well as the same save. After the matching patch was loaded in the tested Stranded case, the user confirmed that the original Windows checkpoint restored the completed objectives, position, and loadout. This does not establish an ongoing cross-OS save roundtrip. If Resume starts with lost objectives or equipment, preserve the original save and follow the [content mismatch checks](docs/compatibility.md#checkpoint-content-mismatch) before playing further.

Sharing progress is optional and manual. The corresponding location in a Linux Wine prefix is typically `<prefix>/drive_c/users/<Wine user>/AppData/Local/Activision/Call of Duty/players/<profile>/SteamCloud/`; inspect the actual Wine user and profile names first. For UMU, `<prefix>` is the `WINEPREFIX` shown above; for Steam, find the `pfx` directory in that non-Steam shortcut’s compatibility data. With the game closed on both systems, back up the Windows `SteamCloud` directory and any existing Linux `sp26` or `7501` directories. Inspect and record the exact source and destination paths. Move existing Linux `sp26` or `7501` directories aside under distinct backup names outside the Linux `SteamCloud` directory; do not delete them. Create links at the original Linux `sp26` and `7501` path names pointing to the matching directories in the Windows profile, and confirm both links resolve to the intended targets before launching. Sharing this way lets the game write to the Windows profile, so retain the backups. To stop sharing, close the game on both systems, remove those Linux-side links, and restore the moved-aside Linux directories. Keep graphics, audio, and keybinding files private to each operating system. The runner never creates save links or synchronizes profiles; this manual shared-link workflow has not been qualified for ongoing cross-OS use.

## Compatibility

The campaign-specific device implements requests observed in build `29465156`; unknown requests fail. Testing so far covers the menu, Mayhem cinematic playback, and a Stranded checkpoint with movement, mouse look, and pause/resume; master volume was set to zero during that session. Later missions, campaign completion, and stable frame rate are not yet established. The [campaign-only device scope](docs/compatibility.md#wine-device) and [tested campaign coverage](docs/validation.md#campaign-coverage) give the exact limits.

Following the `0.1.0-beta.1` release, that runner selected its CPU mapping automatically and loaded Stranded, where keyboard movement was observed; that run exited with code zero. A local GNOME desktop entry activated with `gio launch` reached the game menu. Actual icon double-click, audible output, and a shared-save roundtrip remain unverified. These observations do not qualify the complete campaign or sustained performance; see the [post-beta record](docs/validation.md#post-beta-observations-2026-11-03).

[Compatibility details](docs/compatibility.md) explains the fixes and their tests. [Validation](docs/validation.md) records the tested runtime, hardware, and gameplay coverage.

## Development

Development happens on `main`. Keep changes small, run `make check`, and exercise affected Windows probes through the assembled runner. Runtime changes also need a real campaign test. Release versions follow SemVer, with `VERSION` as the source of truth and tags named `v<VERSION>`, including prereleases such as `v0.1.0-beta.1`.

Project code is licensed under LGPL-2.1-or-later. Third-party code retains its own notices; see [THIRD_PARTY.md](THIRD_PARTY.md).
