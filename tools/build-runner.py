#!/usr/bin/env python3
"""Assemble MW4-Proton from the verified GE runner and locally built renderer."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BASE_NAME = "GE-Proton11-11"
BASE_REVISION = "c0c2ee35e6d4d3bff4d39c6246ac46636434feb8"
BASE_ARCHIVE_SHA256 = "aa85986cada5709aa8bbfa8add7f3bfb925cbe15710c98995898d308ff2ca3c1"
VKD3D_REVISION = "4522cc1a8b1347f1ab1b0f7b14a23ed9444d95d1"
DXIL_REVISION = "4e4c4be90b7e8008194ae70243d54c762aba021f"
WINE_DLLS = Path("files/lib/wine/x86_64-windows")
RENDERER_DLLS = Path("files/lib/wine/vkd3d-proton/x86_64-windows")
BASE_HASHES = {
    "msvcrt.dll": "e9bc2f0f21850933959ff5abdc538f99d56c615e9a8ce69a9762fec96c87ffcf",
    "ntdll.dll": "d50809647f78e121fc807c2db39b4827da34848e1eb0686590919251509b5189",
    "winhttp.dll": "82dc1e9c22032a822dfc79adaa0a98da9ae42acf8ac15e043a6e4f7590bb628c",
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_files():
    files = [ROOT / name for name in ("Makefile", "VERSION", "LICENSE", "THIRD_PARTY.md", "DISCLAIMER.md")]
    if (ROOT / "README.md").is_file():
        files.append(ROOT / "README.md")
    for name in ("src", "patches", "runtime", "tools", "docs", "licenses", "vendor", "tests"):
        files.extend(path for path in (ROOT / name).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts
                     and path.suffix != ".pyc")
    return sorted(files)


def check_inputs(base, renderer):
    stamp, name = (base / "version").read_text().strip().split(maxsplit=1)
    if name != BASE_NAME or not stamp.isdecimal():
        raise ValueError(f"Expected an extracted {BASE_NAME} x86_64 runner")
    if (base / "proton-base").exists() or (base / "user_settings.py").exists():
        raise ValueError("Use a fresh upstream runner without local user_settings.py")
    for name, expected in BASE_HASHES.items():
        if sha256(base / WINE_DLLS / name) != expected:
            raise ValueError(f"Unrecognized base {name}; its SHA-256 must match {BASE_NAME}")
    toolmanifest = (base / "toolmanifest.vdf").read_text()
    if not re.search(r'"require_tool_appid"\s+"4183110"', toolmanifest):
        raise ValueError("The base runner does not select the expected Steam runtime")
    metadata = json.loads((renderer / "build-info.json").read_text())
    if (metadata.get("vkd3d_proton") != VKD3D_REVISION or
            metadata.get("dxil_spirv") != DXIL_REVISION):
        raise ValueError("Renderer revisions differ from the validated source pins")
    renderer_hashes = {}
    for name in ("d3d12.dll", "d3d12core.dll"):
        relative = f"x64/{name}"
        actual = sha256(renderer / relative)
        if metadata.get("files", {}).get(relative) != actual:
            raise ValueError(f"Renderer manifest does not match {name}")
        renderer_hashes[name] = actual
    return stamp, renderer_hashes


def replace_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Break copied aliases before replacing a DLL; never follow a symlink into
    # another runner or modify a second file through a preserved hard link.
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    shutil.copy2(source, destination)


def build(base, renderer, output, prebuilt=None):
    output = Path(os.path.abspath(output))
    output = output.parent.resolve() / output.name
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    if output.is_relative_to(base) or output.is_relative_to(renderer):
        raise ValueError("Output must be outside both input directories")
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version):
        raise ValueError("VERSION must contain a semantic version")
    name = f"MW4-Proton-{version}"
    stamp, renderer_hashes = check_inputs(base, renderer)
    sources = {str(path.relative_to(ROOT)): sha256(path) for path in source_files()}
    binaries = ROOT / "build"
    if prebuilt is None:
        subprocess.run(["make", "all"], cwd=ROOT, check=True)
    else:
        payload = json.loads((prebuilt / "manifest.json").read_text())
        if payload.get("version") != version or payload.get("source_files") != sources:
            raise ValueError("Prebuilt payload does not match this source snapshot")
        for filename in ("controller.exe", "randgrid.sys", "crt_adapter.dll", "winhttp_adapter.dll"):
            if sha256(prebuilt / filename) != payload.get("files", {}).get(filename):
                raise ValueError(f"Prebuilt payload hash mismatch: {filename}")
        binaries = prebuilt

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=output.parent) as temporary:
        temporary = Path(temporary)
        runner = temporary / name
        runner.mkdir()
        subprocess.run(["cp", "-a", "--reflink=auto", "--", str(base) + "/.", str(runner)], check=True)
        for directory, subdirectories, files in os.walk(runner):
            if "__pycache__" in subdirectories:
                cache = Path(directory) / "__pycache__"
                if cache.is_symlink():
                    cache.unlink()
                else:
                    shutil.rmtree(cache)
                subdirectories.remove("__pycache__")
            for filename in files:
                if filename.endswith(".pyc"):
                    (Path(directory) / filename).unlink()

        share = runner / "files/share/mw4"
        manifests = share / "manifests"
        manifests.mkdir(parents=True)
        patch_arguments = {
            "msvcrt.dll": ["patch_msvcrt.py", binaries / "crt_adapter.dll"],
            "ntdll.dll": ["patch_dispatcher.py"],
            "winhttp.dll": ["patch_winhttp.py", binaries / "winhttp_adapter.dll"],
        }
        changed = []
        for dll, (script, *adapters) in patch_arguments.items():
            patched = temporary / dll
            subprocess.run([sys.executable, str(ROOT / "patches" / script),
                            str(base / WINE_DLLS / dll), *map(str, adapters), str(patched)], check=True)
            replace_file(patched, runner / WINE_DLLS / dll)
            shutil.copy2(patched.with_suffix(".json"), manifests / f"{Path(dll).stem}.json")
            changed.append(WINE_DLLS / dll)

        for dll in renderer_hashes:
            replace_file(renderer / "x64" / dll, runner / RENDERER_DLLS / dll)
            changed.append(RENDERER_DLLS / dll)
        for filename in ("controller.exe", "randgrid.sys"):
            replace_file(binaries / filename, share / filename)
            changed.append(Path("files/share/mw4") / filename)

        (runner / "proton").rename(runner / "proton-base")
        shutil.copy2(ROOT / "runtime/proton", runner / "proton")
        (runner / "proton").chmod(0o755)
        (runner / "version").write_text(f"{stamp} {name}\n")
        (runner / "compatibilitytool.vdf").write_text(
            '"compatibilitytools"\n{\n  "compat_tools"\n  {\n'
            f'    "{name}"\n    {{\n'
            '      "install_path" "."\n'
            f'      "display_name" "MW4-Proton {version}"\n'
            '      "from_oslist" "windows"\n      "to_oslist" "linux"\n'
            '    }\n  }\n}\n')
        changed.extend(map(Path, ("proton", "proton-base", "version", "compatibilitytool.vdf")))

        for relative, expected in sources.items():
            source = ROOT / relative
            if sha256(source) != expected:
                raise ValueError(f"Source changed during the build: {relative}; retry the build")
            destination = share / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.copytree(renderer / "licenses", share / "licenses/renderer")
        shutil.copy2(ROOT / "LICENSE", share / "licenses/MW4-Proton-LGPL-2.1.txt")

        manifest = {
            "name": name,
            "version": version,
            "base": {
                "name": BASE_NAME,
                "revision": BASE_REVISION,
                "source": f"https://github.com/GloriousEggroll/proton-ge-custom/tree/{BASE_REVISION}",
                "release_archive_sha256": BASE_ARCHIVE_SHA256,
                "inputs": {str(WINE_DLLS / dll): digest for dll, digest in BASE_HASHES.items()},
            },
            "renderer": {"vkd3d_proton": VKD3D_REVISION, "dxil_spirv": DXIL_REVISION},
            "source_files": sources,
            "files": {str(path): sha256(runner / path) for path in sorted(changed)},
            "toolmanifest_sha256": sha256(runner / "toolmanifest.vdf"),
        }
        (share / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        subprocess.run(["mv", "-T", "--no-clobber", "--", str(runner), str(output)], check=True)
        if runner.exists():
            raise FileExistsError(f"Output appeared during the build: {output}")
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-runner", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New runner directory, e.g. dist/MW4-Proton-0.1.0")
    parser.add_argument("--prebuilt", type=Path,
                        help="Use an overlay's hash-checked payload instead of compiling")
    args = parser.parse_args()
    try:
        output = Path(os.path.abspath(args.output))
        output = output.parent.resolve() / output.name
        build(args.base_runner.resolve(strict=True), args.renderer.resolve(strict=True), output,
              args.prebuilt.resolve(strict=True) if args.prebuilt else None)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"build-runner: {error}\n")


if __name__ == "__main__":
    main()
