# Install in Bottles

Use the release overlay to install **MW4-Bottles**, the Bottles adapter for the
same patched Wine, renderer and DXVK-NVAPI shipped by MW4-Proton. Python 3.12 or
newer and `pefile` are required, as for the Steam installer. Start Bottles once,
then close it.

Choose the payload and filesystem options **before the first installation**.
The installer never overwrites an existing adapter, so include every needed
flag in that first command. It detects native or Flatpak Bottles; if both exist,
add `--target native` or `--target flatpak`. Add `--dry-run` to your chosen command
to inspect its paths, then remove that flag to install.

## Choose one install command

Run **one** of these alternatives from the extracted overlay directory, replacing
the example paths. `--runner` and `--game` can be combined; they are not separate
installation steps.

**New payload, game already accessible to Bottles:**

```sh
python3 tools/install-bottles.py
```

**Reuse an assembled runner, game already accessible to Bottles:**

```sh
python3 tools/install-bottles.py \
  --runner '/path/to/MW4-Proton-0.1.0-beta.2'
```

**New payload, external game needing Flatpak access:**

```sh
python3 tools/install-bottles.py --target flatpak \
  --game '/path/to/Call of Duty - Modern Warfare 4/sp26/sp26-cod.exe'
```

**Reuse an assembled runner and grant Flatpak access to the external game:**

```sh
python3 tools/install-bottles.py --target flatpak \
  --runner '/path/to/MW4-Proton-0.1.0-beta.2' \
  --game '/path/to/Call of Duty - Modern Warfare 4/sp26/sp26-cod.exe'
```

Without `--runner`, the installer downloads and verifies the GE base when needed
and keeps its assembled payload inside the selected Bottles data directory,
outside the list of selectable runners. With `--runner`, it checks that runner's
version and recorded hashes and links to it without another runtime copy. Keep
the reused MW4-Proton directory at its installed path.

For Flatpak, the selected command grants read access to a reused runner outside
the sandbox and, when `--game` is supplied, access to that game's installation
directory. It checks access from inside the sandbox before installing the
adapter. Include `--no-flatpak-permissions` in your chosen command to keep
permissions unchanged; the access check must still pass. External save folders
need their own Flatpak permission. No game files are copied or changed by the
installer.

## Create the bottle

1. Restart Bottles and create a **Custom**, **64-bit** bottle. Select
   **MW4-Bottles-0.1.0-beta.2** as its runner. Use a dedicated bottle for this game.
2. Leave Bottles' **DXVK**, **VKD3D**, and **DXVK NVAPI** switches off. The adapter
   installs the pinned campaign DLLs itself. Keep **WineBridge** and **virtual
   desktop** disabled so launches go through the adapter. Enable the discrete GPU
   setting on a hybrid laptop if needed.
3. Add the existing `sp26/sp26-cod.exe` as a program. Leave its launch arguments
   empty, then start it from Bottles. The controller supplies the campaign argument
   and sets the working directory to the installation root above `sp26`.

The adapter leaves Wine configuration tools available and seeds the two private
CRT/WinHTTP DLLs before Wine initializes a new bottle. At campaign launch it
replaces the bottle's renderer/NVAPI and patched CRT/WinHTTP DLL entries, applies
the required overrides, and starts the compatibility device controller. Its
prefix lock remains held until the game's Wine server exits. The launch report
is `drive_c/mw4-launch.log` inside the bottle. Prefix creation, saves and graphics
settings remain separate from runner installation; installing this adapter does
not import or change a Windows profile.

This is a campaign beta. The [compatibility limits](compatibility.md),
[validation record](validation.md), and [disclaimer](../DISCLAIMER.md) apply to
Bottles too. A working launcher fixture does not establish gameplay performance
or qualify a Flatpak GPU/runtime combination.

## Why Bottles needs an adapter

Bottles recognizes a Proton `toolmanifest.vdf`, but its direct Wine launch path
uses `files/bin/wine` rather than the top-level `proton` script. Registering the
Steam directory alone would skip MW4's campaign controller. MW4-Bottles preserves
the Proton manifest for Bottles' runtime selection and replaces that Wine entry
point with the campaign adapter, while linking the shared libraries and assets.

The implementation was checked against the official Bottles source at
[`47b3db2309e10b1dcc13de7e4040f53d9ecc470c`](https://github.com/bottlesdevs/Bottles/tree/47b3db2309e10b1dcc13de7e4040f53d9ecc470c):
[`WineCommand._get_runner_info`](https://github.com/bottlesdevs/Bottles/blob/47b3db2309e10b1dcc13de7e4040f53d9ecc470c/bottles/backend/wine/winecommand.py),
[`SteamUtils`](https://github.com/bottlesdevs/Bottles/blob/47b3db2309e10b1dcc13de7e4040f53d9ecc470c/bottles/backend/utils/steam.py),
and the [`Start` launch form](https://github.com/bottlesdevs/Bottles/blob/47b3db2309e10b1dcc13de7e4040f53d9ecc470c/bottles/backend/wine/start.py).
The installer supports the native `$XDG_DATA_HOME/bottles` directory and Flatpak's
`~/.var/app/com.usebottles.bottles/data/bottles`; pass `--bottles-root PATH` for a
custom data directory. The [validation record](validation.md#flatpak-bottles-675-2026-11-03)
documents prefix creation and a visible campaign menu with Flatpak Bottles 67.5.
Resume and movement were not qualified in that session. Other Bottles versions
and runtime/GPU combinations need their own checks.

For a repeatable native adapter check, run this from the source checkout with a
MinGW x86-64 compiler installed:

```sh
python3 tests/bottles-smoke.py --runner /path/to/MW4-Proton-0.1.0-beta.2
```

It creates a disposable prefix under `/tmp`, initializes it through the adapter,
and starts a small compiled CRT probe named `sp26-cod.exe` through Bottles'
`start /wait /unix` command form. The probe checks the controller's argument and
working directory; the actual controller checks device replies and cleanup.
It never launches an installed game. This tests native Wine and the adapter.
The [live client record](validation.md#flatpak-bottles-675-2026-11-03) separately
describes the observed Flatpak Bottles rendering path and its limits.
