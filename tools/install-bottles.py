#!/usr/bin/env python3
"""Install the MW4 campaign runner for native or Flatpak Bottles."""

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_runner", ROOT / "tools/build-runner.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
APP_ID = "com.usebottles.bottles"


def bottles_roots(home, data_home):
    candidates = [("native", data_home / "bottles"),
                  ("flatpak", home / ".var/app" / APP_ID / "data/bottles")]
    return [(kind, path) for kind, path in candidates if path.is_dir()]


def bottles_root(target, explicit=None):
    if explicit:
        return explicit.resolve(strict=True)
    home = Path.home()
    data_home = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    roots = [(kind, path) for kind, path in bottles_roots(home, data_home)
             if target == "auto" or target == kind]
    if len(roots) > 1:
        raise ValueError("Multiple Bottles installations found; select --target native or --target flatpak")
    if roots:
        return roots[0][1]
    raise ValueError("No Bottles data directory found; start Bottles once or pass --bottles-root PATH")


def install_adapter(runner, output):
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Runner destination already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mw4-bottles-", dir=output.parent) as directory:
        adapter = Path(directory) / output.name
        binaries = adapter / "files/bin"
        binaries.mkdir(parents=True)
        shutil.copy2(ROOT / "runtime/bottles-wine", binaries / "wine")
        (binaries / "wine").chmod(0o755)
        (binaries / "wine64").symlink_to("wine")
        for entry in (runner / "files/bin").iterdir():
            if entry.name not in ("wine", "wine64"):
                (binaries / entry.name).symlink_to(entry)
        for entry in (runner / "files").iterdir():
            if entry.name != "bin":
                (adapter / "files" / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
        (adapter / "bin").symlink_to("files/bin", target_is_directory=True)
        shutil.copy2(runner / "toolmanifest.vdf", adapter / "toolmanifest.vdf")
        shutil.copy2(runner / "version", adapter / "version")
        shutil.copy2(ROOT / "runtime/proton", adapter / "proton-helper")
        (adapter / "runner-path").write_text(str(runner) + "\n")
        subprocess.run(["mv", "-T", "--no-clobber", "--", str(adapter), str(output)], check=True)
        if adapter.exists():
            raise FileExistsError(f"Runner destination appeared during installation: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("auto", "native", "flatpak"), default="auto")
    parser.add_argument("--bottles-root", type=Path, help="Existing Bottles data directory for a custom installation")
    parser.add_argument("--runner", type=Path, help="Reuse a verified MW4-Proton runner without copying its payload")
    parser.add_argument("--base-runner", type=Path, help="Use an extracted GE base instead of downloading")
    parser.add_argument("--cache", type=Path, help="Upstream download/extraction cache")
    parser.add_argument("--game", type=Path, help="Existing sp26/sp26-cod.exe; also grants its directory to Flatpak Bottles")
    parser.add_argument("--no-flatpak-permissions", action="store_true", help="Keep Flatpak permissions unchanged; require existing access")
    parser.add_argument("--dry-run", action="store_true", help="Show paths without changing anything")
    args = parser.parse_args()
    try:
        if args.runner and (args.base_runner or args.cache):
            raise ValueError("--runner cannot be combined with --base-runner or --cache")
        root = bottles_root(args.target, args.bottles_root)
        if not root.is_dir():
            raise ValueError("Bottles root must be an existing directory")
        version = (ROOT / "VERSION").read_text().strip()
        if not version or "/" in version or "\\" in version:
            raise ValueError("Invalid runner version")
        output = root / "runners" / f"MW4-Bottles-{version}"
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"Runner destination already exists: {output}")
        source = builder.check_installed_runner(args.runner) if args.runner else root / "mw4-proton-payload" / f"MW4-Proton-{version}"
        game = args.game.resolve(strict=True) if args.game else None
        if game and (not game.is_file() or game.name.lower() != "sp26-cod.exe"):
            raise ValueError("--game must name the existing campaign sp26-cod.exe")
        flatpak_home = Path.home() / ".var/app" / APP_ID
        flatpak = args.target == "flatpak" or root.is_relative_to(flatpak_home)
        print(f"Bottles runner destination: {output}", flush=True)
        print(f"Shared MW4-Proton payload: {source}", flush=True)
        if args.dry_run:
            return 0
        if not args.runner:
            command = [sys.executable, str(ROOT / "tools/install-runner.py"), "--output", str(source)]
            if args.base_runner:
                command.extend(("--base-runner", str(args.base_runner)))
            if args.cache:
                command.extend(("--cache", str(args.cache)))
            subprocess.run(command, check=True)
            source = builder.check_installed_runner(source)
        if flatpak:
            paths = [(source, "ro")]
            if game:
                paths.append((game.parent.parent, "rw"))
            if not args.no_flatpak_permissions:
                command = ["flatpak", "override", "--user"]
                command.extend(f"--filesystem={path}:{mode}" for path, mode in paths
                               if not path.is_relative_to(flatpak_home))
                if len(command) > 3:
                    subprocess.run([*command, APP_ID], check=True)
            readable = [source / "files/bin/wine"]
            if game:
                readable.append(game)
            for path in readable:
                subprocess.run(["flatpak", "run", "--command=test", APP_ID,
                                "-r", str(path)], check=True)
        install_adapter(source, output)
        print(f"Installed {output.name}. Restart Bottles; create a Custom 64-bit bottle with this runner.")
        print("Keep WineBridge and virtual desktop disabled. Leave Bottles' DXVK, VKD3D and NVAPI switches off; the runner supplies its pinned DLLs.")
        print("Add sp26/sp26-cod.exe as a program. The controller sets the game's working directory and launch argument.")
        print("Keep the shared MW4-Proton payload at the path above; this adapter links to it.")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"install-bottles: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
