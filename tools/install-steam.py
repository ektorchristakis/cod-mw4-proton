#!/usr/bin/env python3
"""Install MW4-Proton into native or Flatpak Steam's compatibility tools."""

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_runner", ROOT / "tools/build-runner.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def steam_roots(home, data_home):
    candidates = [
        ("native", data_home / "Steam"),
        ("native", home / ".steam/root"),
        ("native", home / ".steam/steam"),
        ("flatpak", home / ".var/app/com.valvesoftware.Steam/data/Steam"),
        ("flatpak", home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"),
    ]
    found = {}
    for kind, path in candidates:
        if path.is_dir() and ((path / "steamapps").is_dir() or (path / "config").is_dir()):
            found.setdefault(path.resolve(), kind)
    return [(kind, path) for path, kind in found.items()]


def steam_root(kind, explicit=None):
    if explicit is not None:
        return explicit.resolve(strict=True)
    home = Path.home()
    data_home = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    roots = [(name, path) for name, path in steam_roots(home, data_home)
             if kind == "auto" or name == kind]
    if not roots:
        raise ValueError("No Steam data directory found; start Steam once or pass --steam-root PATH")
    if len(roots) != 1:
        raise ValueError("Multiple Steam installations found; select --steam native, --steam flatpak, or --steam-root PATH")
    return roots[0][1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steam", choices=("auto", "native", "flatpak"), default="auto")
    parser.add_argument("--steam-root", type=Path, help="Existing Steam data directory for a custom installation")
    parser.add_argument("--runner", type=Path, help="Register an already assembled runner by link, without another copy")
    parser.add_argument("--base-runner", type=Path, help="Use a separately extracted GE base instead of downloading")
    parser.add_argument("--cache", type=Path, help="Upstream download/extraction cache for a new installation")
    parser.add_argument("--dry-run", action="store_true", help="Show the destination without installing")
    args = parser.parse_args()
    try:
        if args.runner and (args.base_runner or args.cache):
            raise ValueError("--runner cannot be combined with --base-runner or --cache")
        root = steam_root(args.steam, args.steam_root)
        if not root.is_dir():
            raise ValueError("Steam root must be an existing directory")
        version = (ROOT / "VERSION").read_text().strip()
        if not version or "/" in version or "\\" in version:
            raise ValueError("Invalid runner version")
        output = root / "compatibilitytools.d" / f"MW4-Proton-{version}"
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"Runner destination already exists: {output}")
        existing = builder.check_installed_runner(args.runner) if args.runner else None
        print(f"Steam runner destination: {output}", flush=True)
        if args.dry_run:
            return 0
        if existing:
            flatpak_home = Path.home() / ".var/app/com.valvesoftware.Steam"
            if args.steam == "flatpak" or root.is_relative_to(flatpak_home):
                readable = subprocess.run(["flatpak", "run", "--command=test", "com.valvesoftware.Steam",
                                           "-r", str(existing / "proton")], check=False)
                if readable.returncode:
                    raise ValueError("Flatpak Steam cannot read this runner; install without --runner into its data directory, or grant this specific folder read access")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.symlink_to(existing, target_is_directory=True)
        else:
            command = [sys.executable, str(ROOT / "tools/install-runner.py"), "--output", str(output)]
            if args.base_runner:
                command.extend(("--base-runner", str(args.base_runner)))
            if args.cache:
                command.extend(("--cache", str(args.cache)))
            subprocess.run(command, check=True)
        print(f"Installed MW4-Proton {version}. Restart Steam to select it in the game's Compatibility settings.")
        print("Add sp26/sp26-cod.exe as a non-Steam game; set Start In to the installation root, one directory above sp26.")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"install-steam: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
