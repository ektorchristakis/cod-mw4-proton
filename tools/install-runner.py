#!/usr/bin/env python3
"""Install the release overlay using a verified download of the official GE base."""

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_runner", ROOT / "tools/build-runner.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
ARCHIVE = "GE-Proton11-11-x86_64.tar.gz"
URL = f"https://github.com/GloriousEggroll/proton-ge-custom/releases/download/{builder.BASE_NAME}/{ARCHIVE}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New runner directory in compatibilitytools.d or another location")
    parser.add_argument("--cache", type=Path,
                        default=Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "mw4-proton")
    parser.add_argument("--base-runner", type=Path,
                        help="Use a separately extracted, verified GE runner instead of downloading")
    args = parser.parse_args()
    try:
        if importlib.util.find_spec("pefile") is None:
            raise ValueError("Python package pefile is required; install it before running the installer")
        args.cache = args.cache.resolve()
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError(f"Output already exists: {args.output}")
        if not (ROOT / "payload/manifest.json").is_file():
            raise ValueError("Run this installer from a packaged release overlay")
        nvapi_archive = builder.nvapi.release_archive(ROOT / "nvapi" / builder.nvapi.ARCHIVE)
        if args.base_runner:
            base = args.base_runner.resolve(strict=True)
        else:
            args.cache.mkdir(parents=True, exist_ok=True)
            archive = args.cache / ARCHIVE
            if not archive.exists() or builder.sha256(archive) != builder.BASE_ARCHIVE_SHA256:
                print(f"Downloading the official {builder.BASE_NAME} archive...", flush=True)
                request = urllib.request.Request(URL, headers={"User-Agent": "MW4-Proton installer"})
                with tempfile.NamedTemporaryFile(dir=args.cache, prefix="ge-download-", delete=False) as temporary:
                    download = Path(temporary.name)
                    try:
                        with urllib.request.urlopen(request, timeout=60) as response:
                            while chunk := response.read(1024 * 1024):
                                temporary.write(chunk)
                        temporary.flush()
                        if builder.sha256(download) != builder.BASE_ARCHIVE_SHA256:
                            raise ValueError("Downloaded GE archive has an unexpected SHA-256")
                        download.replace(archive)
                    finally:
                        download.unlink(missing_ok=True)
            print("Extracting the verified upstream archive...", flush=True)
            with tempfile.TemporaryDirectory(dir=args.cache, prefix="ge-extract-") as directory:
                with tarfile.open(archive, "r:gz") as package:
                    package.extractall(directory, filter="data")
                base = Path(directory) / "GE-Proton11-11-x86_64"
                builder.build(base, ROOT / "renderer", ROOT / "dxgi", args.output.absolute(),
                              ROOT / "payload", nvapi_archive)
                return 0
        builder.build(base, ROOT / "renderer", ROOT / "dxgi", args.output.absolute(),
                      ROOT / "payload", nvapi_archive)
    except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"install-runner: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
