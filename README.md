# MW4-Proton

An experimental beta Proton runner for the **Modern Warfare 4 single-player campaign only**, based on GE-Proton 11-11. It targets campaign build `29465156` and starts `sp26-cod.exe` from an existing Windows installation with the offline loader already present. Multiplayer, online modes, and other game builds are unsupported. Game files stay in their original location; use a dedicated Wine prefix on a Linux filesystem.

The runner includes a Wine device implementation, CRT and WinHTTP fixes, a compatible exception-dispatcher layout, VKD3D-Proton 3.1 with a newer dxil-spirv translator, and DXVK-NVAPI 0.9.3 with its upstream memory-reporting corrections. It does not contain game files, saves, the original Windows driver, or Microsoft DLLs.

Version `0.1.0-beta.3` changes allocation of small, highly aligned heaps to avoid wasting large pools of video memory. It also adds a rebuilt, GE-prepared x64 DXGI DLL: its existing `dxgi.maxDeviceMemory` option now also caps dynamic LOCAL budget reports when set above zero. The default remains `0`; an existing nonzero value used with an older runner will also activate the new behavior in beta.3. No GPU profile is selected automatically. See [VRAM allocation](docs/vram.md) and [Optional memory budget](#optional-memory-budget).

Testing is incomplete. A private build of the aligned-heap fix reduced measured VRAM allocation on one RTX 3060 Laptop GPU, and the player reported better performance. The release candidate loaded the existing checkpoint through UMU and responded to brief movement. Earlier cinematic checks used a budget-only candidate without the aligned-heap fix. Neither the 5120 nor 4096 MiB memory-budget trial demonstrated stable 30 FPS; the latter fell to about 13 FPS. The option is not a qualified performance fix. The complete campaign, audible quality and an ongoing Windows/Linux shared-save roundtrip remain unqualified. Earlier native Steam and Flatpak Bottles 67.5 menu observations used beta.2. See the [beta.3 record](docs/validation.md#beta3-validation) and the separately labelled [beta.2 launcher checks](docs/validation.md#beta2-launcher-checks).

The software is supplied without warranty. Account restrictions, suspensions, or bans cannot be ruled out; see the [warranty and liability notice](DISCLAIMER.md).

## Install and launch

You need the existing campaign installation, Python 3.12 or newer with the `pefile` package, GNU coreutils, GNU tar and `xz`, plus Steam, Bottles, or `umu-run`. Download `MW4-Proton-0.1.0-beta.3-overlay.tar.xz` and `SHA256SUMS` from the [0.1.0-beta.3 release](https://github.com/ektorchristakis/cod-mw4-proton/releases/tag/v0.1.0-beta.3). From the directory containing both downloads, verify and extract the overlay:

```sh
sha256sum --check SHA256SUMS &&
  tar -xf MW4-Proton-0.1.0-beta.3-overlay.tar.xz &&
  cd MW4-Proton-0.1.0-beta.3-overlay
```

Continue only after the archive reports `OK`; stop if verification or extraction fails.

For Steam, start Steam once if it is newly installed. Choose **one** command below: install a new runner, or register an existing assembled runner without another copy. If both native and Flatpak Steam are present, add `--steam native` or `--steam flatpak` to your chosen command before running it. Add `--dry-run` to inspect the destination first, then remove that flag to install.

**New runner:**

```sh
python3 tools/install-steam.py
```

**Reuse an existing assembled runner:** It must be beta.3, matching this overlay; a beta.2 runner is not accepted by the beta.3 installer. Keep its directory in place after registration. If Flatpak Steam cannot read that directory outside its sandbox, grant read access to that specific folder before registering it. Use the runner's resolved absolute path in both commands; if it is a symlink, `realpath /path/to/runner` shows that path:

```sh
flatpak override --user \
  --filesystem='/absolute/path/to/MW4-Proton-0.1.0-beta.3:ro' \
  com.valvesoftware.Steam
```

Native Steam needs no Flatpak grant. Once the selected Steam installation can read the runner, register it with one command, adding the `--steam` selection above if needed:

```sh
python3 tools/install-steam.py \
  --runner '/absolute/path/to/MW4-Proton-0.1.0-beta.3'
```

For either a new or reused runner, Flatpak Steam also needs access to the existing game installation. If that directory is outside its current filesystem permissions, grant read/write access to that specific installation root, one directory above `sp26`. Use its resolved absolute path; `realpath '/path/to/Call of Duty - Modern Warfare 4'` shows it:

```sh
flatpak override --user \
  --filesystem='/absolute/path/to/Call of Duty - Modern Warfare 4:rw' \
  com.valvesoftware.Steam
```

This grants access without copying game files. If you later link saves from outside the installation, grant those resolved save directories their own read/write access separately.

Restart Steam after installation. Add the existing `sp26/sp26-cod.exe` as a non-Steam game, select **MW4-Proton 0.1.0-beta.3** in its Compatibility settings, and set **Start In** to the installation root, one directory above `sp26`. Use a separate shortcut and prefix for this game. Steam installs Steam Linux Runtime 4 on first launch if needed; let that download finish.

For Bottles, start Bottles once and close it, then follow [Bottles installation](docs/bottles.md) to choose **one installer command before running it** from the extracted overlay. Include `--runner` if reusing an assembled runner and `--game` if Flatpak needs access to an external game; combine both flags in that one command when needed. The guide also explains how to select **MW4-Bottles-0.1.0-beta.3**, configure its DLL switches, and add the executable.

Both installers download the official GE-Proton base when needed, verify its pinned SHA-256, and refuse to replace an existing runner. See [build and installation](docs/build.md) for offline installation and the complete source build recipe.

The campaign installation also needs its matching content patch. A missing patch can leave the menu and mission playable while silently rejecting an existing checkpoint and starting the mission again. The runner installer does not supply or verify game content. Before importing Windows progress, see [checkpoint content mismatch](docs/compatibility.md#checkpoint-content-mismatch) for the exact-build checks and the tested manual repair using official content files and a locally constructed version cache.

For a standalone UMU setup, install `umu-run`. If you already have an assembled **MW4-Proton 0.1.0-beta.3** runner, use its actual path as `PROTONPATH` and skip the installation below. An older runner remains usable as a deliberate version fallback, but does not provide beta.3's LOCAL-budget change. Otherwise, install beta.3 from the extracted overlay into a new dedicated directory:

```sh
python3 tools/install-runner.py \
  --output "$HOME/Games/runners/MW4-Proton-0.1.0-beta.3"
```

This installation needs no Steam client or Steam data directory. Launch with that same runner path, replacing the game path with the absolute path to your existing installation. `WINEPREFIX` names this game's separate Linux prefix:

```sh
WINEPREFIX="$HOME/Games/prefixes/mw4" \
PROTONPATH="$HOME/Games/runners/MW4-Proton-0.1.0-beta.3" \
GAMEID=umu-default \
umu-run '/path/to/Call of Duty - Modern Warfare 4/sp26/sp26-cod.exe'
```

On GNOME, the UMU command above is the portable launch path. The installer does not create a GNOME application-menu entry.

The wrapper starts the compatibility device, launches the campaign with its standard argument, waits for it to exit, and removes the temporary Wine service. Other executable names and Proton verbs pass through to GE-Proton without this campaign device; that pass-through does not add support for other game modes.

Use a separate prefix for this game. The runtime DLL changes apply throughout that prefix. The wrapper prevents two campaign launches from sharing it at once. On hosts with offline CPUs and sparse CPU numbering, it applies a process-local CPU mapping; see [CPU topology](docs/compatibility.md#sparse-cpu-numbering) for the CPU-count tradeoff and override.

## Optional memory budget

The manually selected `5120` and `4096` MiB values were investigated on one RTX 3060 Laptop GPU with 6 GiB VRAM. The 5120 MiB trial ended in the mid-20s with drops, and the 4096 MiB trial deteriorated to about 13 FPS. Neither is a recommended performance preset or a stable-30 fix. Other GPUs are unqualified. The `5120` example below shows how to set and revert the option; the [validation record](docs/validation.md#beta3-validation) gives the results and separates private diagnostic observations from the public binary's checks.

First retain the original `DXVK_CONFIG` value, if one is configured. With no existing options, the Steam launch setting is:

```text
DXVK_CONFIG='dxgi.maxDeviceMemory = 5120' %command%
```

If options already exist, keep them and separate assignments with `;`. For example, an existing `dxvk.maxFrameRate = 60` becomes:

```text
DXVK_CONFIG='dxvk.maxFrameRate = 60; dxgi.maxDeviceMemory = 5120' %command%
```

This illustrates preserving an existing frame limiter; it does not recommend adding one. Change an existing `dxgi.maxDeviceMemory` assignment instead of adding duplicate assignments. In Bottles, add environment key `DXVK_CONFIG` with the same complete value, without the shell's outer quote characters. For UMU, pass that complete value in the launch environment. See [the setting and reversion details](docs/compatibility.md#dxgi-memory-budget), including the case where a DXVK configuration file already sets a value.

To restore the original configuration, close the game and restore the saved original value or remove only the added assignment. To explicitly force default reporting, set that assignment to `dxgi.maxDeviceMemory = 0`, keeping other options. Restart the game. A lower reported budget is advisory to the game; it is not a physical VRAM cap or a frame-rate guarantee.

If changing runner version is needed, keep beta.2 installed, close the game and select that retained Steam runner or Bottles adapter, or use its previous `PROTONPATH` for UMU. The chosen runner synchronizes its DLLs into the prefix on launch. Do not reset the prefix or restore an older Windows save merely to disable a budget setting or select another runner. Preserve the latest shared saves and retain graphics/audio settings separately for each operating system. This fallback guidance does not establish an ongoing cross-OS save roundtrip.

## Existing Windows progress

The campaign stores observed checkpoint and progression files under the Windows user’s `AppData/Local/Activision/Call of Duty/players/<profile>/SteamCloud/sp26` and `.../SteamCloud/7501`. `SteamCloud` is a directory name here, not a promise of automatic cloud synchronization. Back up the Windows `SteamCloud` directory before changing save paths.

Windows and Linux must load matching campaign content as well as the same save. After the matching patch was loaded in the tested Stranded case, the user confirmed that the original Windows checkpoint restored the completed objectives, position, and loadout. This does not establish an ongoing cross-OS save roundtrip. If Resume starts with lost objectives or equipment, preserve the original save and follow the [content mismatch checks](docs/compatibility.md#checkpoint-content-mismatch) before playing further.

Sharing progress is optional and manual. The corresponding location in a Linux Wine prefix is typically `<prefix>/drive_c/users/<Wine user>/AppData/Local/Activision/Call of Duty/players/<profile>/SteamCloud/`; inspect the actual Wine user and profile names first. For UMU, `<prefix>` is the `WINEPREFIX` shown above; for Steam, find the `pfx` directory in that non-Steam shortcut’s compatibility data. With the game closed on both systems, back up the Windows `SteamCloud` directory and any existing Linux `sp26` or `7501` directories. Inspect and record the exact source and destination paths. Move existing Linux `sp26` or `7501` directories aside under distinct backup names outside the Linux `SteamCloud` directory; do not delete them. Create links at the original Linux `sp26` and `7501` path names pointing to the matching directories in the Windows profile, and confirm both links resolve to the intended targets before launching. Sharing this way lets the game write to the Windows profile, so retain the backups. To stop sharing while retaining current progress, close the game on both systems and make a fresh backup of the Windows `sp26` and `7501` directories. Verify that the two Linux paths are the links you created, remove only those links, and copy the latest Windows `sp26` and `7501` directories into those Linux paths as ordinary directories. Check that the copied files match their sources before launching, and keep the original moved-aside Linux backups. Matching copied files establishes their identity, not that the game accepts the checkpoint. Restoring the older Linux backups instead is a deliberate rollback to the progress they contained. Keep graphics, audio, and keybinding files private to each operating system. The runner never creates save links or synchronizes profiles; this manual shared-link workflow has not been qualified for ongoing cross-OS use.

## Compatibility

The campaign-specific device implements requests observed in build `29465156`; unknown requests fail. Earlier recorded sessions covered the menu, Mayhem cinematic playback and a Stranded checkpoint with movement, mouse look and pause/resume; master volume was zero during that session. Beta.3 has its own bounded local gameplay observations. See the [current beta.3 record](docs/validation.md#beta3-validation), [campaign-only device scope](docs/compatibility.md#wine-device) and the versioned [campaign coverage](docs/validation.md#campaign-coverage). Later missions, campaign completion and stable frame rate remain unqualified.

Following the `0.1.0-beta.1` release, that runner selected its CPU mapping automatically and loaded Stranded, where keyboard movement was observed; that run exited with code zero. A local GNOME desktop entry activated with `gio launch` reached the game menu. Actual icon double-click, audible output, and a shared-save roundtrip remain unverified. These observations do not qualify the complete campaign or sustained performance; see the [post-beta record](docs/validation.md#post-beta-observations-2026-11-03).

[Compatibility details](docs/compatibility.md) explains the fixes and their tests. [Validation](docs/validation.md) records the tested runtime, hardware, and gameplay coverage.

## Development

Development happens on `main`. Keep changes small, run `make check`, and exercise affected Windows probes through the assembled runner. Runtime changes also need a real campaign test. Release versions follow SemVer, with `VERSION` as the source of truth and tags named `v<VERSION>`, including prereleases such as `v0.1.0-beta.1`.

Project code is licensed under LGPL-2.1-or-later. Third-party code retains its own notices; see [THIRD_PARTY.md](THIRD_PARTY.md).
