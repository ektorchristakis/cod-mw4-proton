#!/usr/bin/env python3
"""Run the Bottles adapter with real Wine in an isolated, disposable prefix."""

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_bottles", ROOT / "tools/install-bottles.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def smoke(runner, directory):
    with tempfile.TemporaryDirectory(prefix="mw4-bottles-smoke-", dir=directory) as temporary:
        temporary = Path(temporary)
        adapter = temporary / "adapter"
        installer.install_adapter(runner, adapter)
        prefix = temporary / "isolated prefix"
        game = temporary / "isolated game/sp26/sp26-cod.exe"
        game.parent.mkdir(parents=True)
        subprocess.run([os.environ.get("MINGW_CC", "x86_64-w64-mingw32-gcc"),
                        "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(game),
                        str(ROOT / "tests/bottles_campaign_probe.c")], check=True)
        env = dict(os.environ, WINEPREFIX=str(prefix), WINEARCH="win64", WINEDEBUG="-all",
                   WINEDLLOVERRIDES="winemenubuilder=d")
        try:
            for arguments in (["wineboot", "-i"], ["start", "/wait", "/unix", str(game)]):
                result = subprocess.run([str(adapter / "bin/wine"), *arguments], env=env,
                                        capture_output=True, text=True, timeout=60)
                print(result.stdout, end="")
                print(result.stderr, end="")
                if result.returncode:
                    raise ValueError(f"{arguments[0]} exited with {result.returncode}")
            report = (prefix / "drive_c/mw4-launch.log").read_text()
            print(report, end="")
            required = ("PASS: device opens; unsupported request fails without output",
                        "PASS: authenticated reply contains the expected marker",
                        "PASS: altered ciphertext rejected without output", "Game exit=0;")
            if not all(marker in report for marker in required):
                raise ValueError("Controller report is missing a required result")
            print("PASS: isolated Wineboot, campaign argument/working directory, CRT alias, device and cleanup")
        finally:
            subprocess.run([str(runner / "files/bin/wineserver"), "-k"], env=env,
                           capture_output=True, check=False, timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True, help="Assembled MW4-Proton runner to exercise")
    parser.add_argument("--work-dir", type=Path, default=Path("/tmp"), help="Temporary parent with room for a Wine prefix")
    args = parser.parse_args()
    try:
        smoke(args.runner.resolve(strict=True), args.work_dir.resolve(strict=True))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"bottles-smoke: {error}\n")


if __name__ == "__main__":
    main()
