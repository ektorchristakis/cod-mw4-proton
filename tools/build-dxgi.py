#!/usr/bin/env python3
"""Build and verify the pinned GE-prepared x64 DXGI budget-reporting variant."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REVISION = "2cb40186c43d617b5bd349a3756721aa4bd24b6d"
GE_REVISION = "c0c2ee35e6d4d3bff4d39c6246ac46636434feb8"
GE_TAG = "GE-Proton11-11"
GE_VERSION = "v3.1.1-134-g2cb40186c43d6170"
BUDGET_PATCH_SHA256 = "37eb56c26fba82979ec6a60884b45b25726bb4dc5db5e24b23dbb264e79b4f04"
PREPARED_PATCH_SHA256 = "328d0d4cf8f4ebc1518caf8f2dd4e4366c8abdb487f660bdb5cc2b30a768bb66"
DESTINATION = "files/lib/wine/dxvk/x86_64-windows/dxgi.dll"
GE_PATCHES = {
    "layered-overlay-dxvk.patch": "1022cdab19348775666a6e5318594900bd8638ca65673981733b0b96e369edca",
    "dxvk-preserve-swapchain-on-acquire-backpressure.patch": "40ea378a41ce97fbb8b9930e62461f8eb5495411a5f5109859969357801f453a",
    "dxgi-defer-initial-fullscreen-for-probe-swapchains.patch": "2e4dd044706574677ec6a85e123ca83322ae2ba1c6cef0bdeef62360842a3f06",
    "dxgi-follow-d3d12-fullscreen-client-resizes.patch": "aa0917b885c0f202469ab90cc123787a542080bb5c36a626916b978491e89583",
    "dxgi-keep-fullscreen-on-focus-loss.patch": "9535762125db52c76108b99af30ba597d35fa5527d11cb01f6848b8ee62a97e8",
    "black-desert-keep-fullscreen-on-focus-loss.patch": "bb9226fdac6583af41d7c994c6c2f0362902ac326d47e62fe3bc46e001351c13",
    "assassins-creed-keep-fullscreen-on-focus-loss.patch": "abfd89031ec64e78f25c6d04c37c471c4a6de4d4ed57922aacf9fd2ad78dd3da",
    "dxgi-respect-output-hdr-state.patch": "3db91143b8d604cda1ed99e3ecacd352633c489b09af8021aa6788692c4fa47d",
    "dxgi-auto-detect-hdr.patch": "6c5ea48c1ed6e23fe225f90ddb9fb38559503c253d0773f2f02c6b9a277361bc",
    "starcraft2-disable-constant-buffer-streaming.patch": "1a335465f9fed0a35d5a44ee369bad6ad056ab9a3dbb0029a4d4f8f9c5a2e76f"
}
GE_PREP_SHA256 = '1a3dfa1c3c6dbe6ada3323b9e6280b1e6db7bd3c639d5a2f775386818539b611'

LICENSES = {
    "LICENSE": "DXVK-LICENSE",
    "subprojects/dxbc-spirv/LICENSE": "dxbc-spirv-LICENSE",
    "subprojects/libdisplay-info/LICENSE": "libdisplay-info-LICENSE",
    "include/vulkan/LICENSE.md": "Vulkan-Headers-LICENSE.md",
    "include/spirv/LICENSE": "SPIRV-Headers-LICENSE",
    "include/native/directx/COPYING.MinGW-w64.txt": "MinGW-directx-COPYING",
}
BUILD_FILES = {"x64/dxgi.dll", "source-inputs/protonprep-valve-staging.sh",
               "source-inputs/dxgi-memory-budget.patch", "licenses/GE-Proton-LICENSE"}
BUILD_FILES.update("source-inputs/" + name for name in GE_PATCHES)
BUILD_FILES.update("licenses/" + name for name in LICENSES.values())


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args])


def check_source(source):
    if git(source, "rev-parse", "HEAD").decode().strip() != REVISION:
        raise ValueError("DXGI source revision differs from the GE gitlink")
    difference = git(source, "diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
                     "--no-renames", "--no-color", "--diff-algorithm=myers", "--no-indent-heuristic",
                     "--unified=3", "--inter-hunk-context=0",
                     "--src-prefix=a/", "--dst-prefix=b/", "--ignore-submodules=all", "HEAD")
    if hashlib.sha256(difference).hexdigest() != PREPARED_PATCH_SHA256:
        raise ValueError("DXGI source must contain exactly the GE prep, version processing and budget patch")
    submodules = {}
    for line in git(source, "submodule", "status", "--recursive").decode().splitlines():
        if not line.startswith(" "):
            raise ValueError("DXGI submodule is missing or differs from its gitlink")
        revision, name, *_ = line.split()
        repository = source / name
        for arguments in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
            subprocess.run(["git", "-C", str(repository), *arguments], check=True)
        submodules[name] = revision
    if not submodules:
        raise ValueError("DXGI recursive submodules are required")
    return submodules


def check_metadata(metadata):
    if (not isinstance(metadata, dict) or metadata.get("dxvk") != REVISION
            or metadata.get("ge_proton") != GE_REVISION
            or metadata.get("source_patch_sha256") != PREPARED_PATCH_SHA256
            or metadata.get("budget_patch_sha256") != BUDGET_PATCH_SHA256
            or metadata.get("buildtype") != "release"
            or not metadata.get("normalized_build_paths")
            or metadata.get("insert_pe_timestamp") is not False):
        raise ValueError("DXGI build does not match the pinned portable budget variant")
    if set(metadata.get("files", {})) != BUILD_FILES:
        raise ValueError("DXGI build manifest has missing or unexpected files")


def check_build(directory):
    metadata = json.loads((directory / "build-info.json").read_text())
    check_metadata(metadata)
    for name, digest in metadata["files"].items():
        if sha256(directory / name) != digest:
            raise ValueError(f"DXGI build hash mismatch: {name}")
    inputs = {**GE_PATCHES, "protonprep-valve-staging.sh": GE_PREP_SHA256,
              "dxgi-memory-budget.patch": BUDGET_PATCH_SHA256}
    for name, digest in inputs.items():
        if sha256(directory / "source-inputs" / name) != digest:
            raise ValueError(f"DXGI source input differs from the pinned recipe: {name}")
    data = (directory / "x64/dxgi.dll").read_bytes()
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("DXGI DLL is not a PE image")
    offset = struct.unpack_from("<I", data, 0x3c)[0]
    if (offset + 26 > len(data) or data[offset:offset + 4] != b"PE\0\0"
            or struct.unpack_from("<H", data, offset + 4)[0] != 0x8664
            or struct.unpack_from("<H", data, offset + 24)[0] != 0x20b):
        raise ValueError("DXGI DLL must be x86_64 PE32+")
    if struct.unpack_from("<I", data, offset + 8)[0] != 0:
        raise ValueError("DXGI DLL must have a zero PE timestamp")
    return metadata


def archive_source(source, build, destination):
    metadata = check_build(build)
    submodules = check_source(source)
    if metadata.get("submodules") != submodules:
        raise ValueError("DXGI source submodules differ from the build manifest")
    epoch = int(git(source, "show", "-s", "--format=%ct", "HEAD"))

    def normalize(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = epoch
        return info

    def add_repository(repository, relative, archive):
        for entry in git(repository, "ls-files", "--stage", "-z").split(b"\0"):
            if not entry:
                continue
            attributes, name = entry.split(b"\t", 1)
            mode, _, stage = attributes.split()
            if stage != b"0":
                raise ValueError("Unmerged DXGI source")
            path = Path(name.decode())
            if mode == b"160000":
                add_repository(repository / path, relative / path, archive)
            else:
                archive.add(repository / path, arcname=str(Path("dxvk") / relative / path),
                            recursive=False, filter=normalize)

    with tarfile.open(destination, "w:xz") as archive:
        add_repository(source, Path(), archive)
        for relative in sorted(metadata["files"]):
            name = Path(relative)
            if name.parts[0] != "source-inputs":
                continue
            archive.add(build / name, arcname=str(Path("MW4-PATCHES") / name.name),
                        recursive=False, filter=normalize)
        data = (json.dumps(metadata, indent=2) + "\n").encode()
        info = normalize(tarfile.TarInfo("SOURCE-MANIFEST.json"))
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))
    if check_source(source) != submodules:
        raise ValueError("DXGI source changed during packaging")
    check_build(build)


def build(output, work):
    output = output.parent.resolve() / output.name
    work = work.parent.resolve() / work.name
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    if work.exists() or work.is_symlink():
        raise FileExistsError(f"Choose a fresh DXGI work directory: {work}")
    if output.is_relative_to(work) or work.is_relative_to(output):
        raise ValueError("DXGI output and work directories must be separate")
    work.mkdir(parents=True)
    ge, source = work / "ge-proton", work / "source"
    subprocess.run(["git", "clone", "--depth", "1", "--branch", GE_TAG,
                    "https://github.com/GloriousEggroll/proton-ge-custom.git", str(ge)], check=True)
    if git(ge, "rev-parse", "HEAD").decode().strip() != GE_REVISION:
        raise ValueError("GE source tag differs from the pinned revision")
    subprocess.run(["git", "init", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "remote", "add", "origin",
                    "https://github.com/doitsujin/dxvk.git"], check=True)
    subprocess.run(["git", "-C", str(source), "fetch", "--depth", "1", "origin", REVISION], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--detach", REVISION], check=True)
    subprocess.run(["git", "-C", str(source), "submodule", "update", "--init", "--recursive",
                    "--depth", "1", "--jobs", "2"], check=True)
    prep = ge / "patches/protonprep-valve-staging.sh"
    if sha256(prep) != GE_PREP_SHA256:
        raise ValueError("GE prep script differs from the pinned source")
    section = prep.read_text().split("    pushd dxvk\n", 1)[1].split("    popd", 1)[0]
    if re.findall(r"\.\./patches/dxvk/([^\"\s]+\.patch)", section) != list(GE_PATCHES):
        raise ValueError("GE DXVK patch order differs from the pinned recipe")
    for name, digest in GE_PATCHES.items():
        patch = ge / "patches/dxvk" / name
        if sha256(patch) != digest:
            raise ValueError(f"GE patch differs from its pinned hash: {name}")
        subprocess.run(["patch", "-d", str(source), "-Np1", "--batch", "--fuzz=0",
                        "-i", str(patch)], check=True)
    patch = ROOT / "patches/dxgi-memory-budget.patch"
    if sha256(patch) != BUDGET_PATCH_SHA256:
        raise ValueError("Local DXGI budget patch differs from its pinned hash")
    subprocess.run(["git", "-C", str(source), "apply", str(patch)], check=True)
    version = source / "version.h.in"
    version.write_text(version.read_text().replace("@VCS_TAG@", GE_VERSION))
    submodules = check_source(source)
    arguments = [f"-ffile-prefix-map={work}=/usr/src/mw4-proton/dxgi"]
    sysroot = subprocess.check_output(["x86_64-w64-mingw32-g++", "-print-sysroot"], text=True).strip()
    if sysroot:
        arguments.append(f"-ffile-prefix-map={Path(sysroot).resolve()}=/usr/x86_64-w64-mingw32/sys-root")
    compiled = work / "x64"
    subprocess.run(["meson", "setup", str(compiled), str(source), "--cross-file",
                    str(source / "build-win64.txt"), "--buildtype", "release",
                    "-Denable_dxgi=true", "-Denable_d3d8=false", "-Denable_d3d9=false",
                    "-Denable_d3d10=false", "-Denable_d3d11=false",
                    "-Dc_args=" + json.dumps(arguments), "-Dcpp_args=" + json.dumps(arguments),
                    "-Dc_link_args=-Wl,--no-insert-timestamp",
                    "-Dcpp_link_args=-Wl,--no-insert-timestamp"], check=True)
    subprocess.run(["meson", "compile", "-C", str(compiled), "-j", "2", "dxgi"], check=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mw4-dxgi-", dir=output.parent) as temporary:
        packaged = Path(temporary) / "dxgi"
        (packaged / "x64").mkdir(parents=True)
        shutil.copy2(compiled / "src/dxgi/dxgi.dll", packaged / "x64/dxgi.dll")
        subprocess.run(["x86_64-w64-mingw32-strip", "--strip-debug", "--preserve-dates",
                        str(packaged / "x64/dxgi.dll")], check=True)
        (packaged / "licenses").mkdir()
        for name, destination in LICENSES.items():
            shutil.copy2(source / name, packaged / "licenses" / destination)
        shutil.copy2(ROOT / "licenses/GE-Proton-LICENSE", packaged / "licenses/GE-Proton-LICENSE")
        inputs = packaged / "source-inputs"
        inputs.mkdir()
        for name in GE_PATCHES:
            shutil.copy2(ge / "patches/dxvk" / name, inputs / name)
        shutil.copy2(prep, inputs / prep.name)
        shutil.copy2(patch, inputs / patch.name)
        metadata = {"dxvk": REVISION, "ge_proton": GE_REVISION,
                    "source_patch_sha256": PREPARED_PATCH_SHA256,
                    "budget_patch_sha256": BUDGET_PATCH_SHA256, "submodules": submodules,
                    "buildtype": "release", "normalized_build_paths": True,
                    "insert_pe_timestamp": False,
                    "toolchain": {name: subprocess.check_output(command, text=True).splitlines()[0]
                                  for name, command in (
                                      ("cxx", ["x86_64-w64-mingw32-g++", "--version"]),
                                      ("meson", ["meson", "--version"]),
                                      ("ninja", ["ninja", "--version"]))},
                    "files": {str(f.relative_to(packaged)): sha256(f)
                              for f in sorted(packaged.rglob("*")) if f.is_file()}}
        (packaged / "build-info.json").write_text(json.dumps(metadata, indent=2) + "\n")
        check_build(packaged)
        subprocess.run(["mv", "-T", "--no-clobber", "--", str(packaged), str(output)], check=True)
        if packaged.exists():
            raise FileExistsError(f"Output appeared during the build: {output}")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build/dxgi-build")
    args = parser.parse_args()
    try:
        build(args.output.absolute(), args.work_dir.absolute())
    except (OSError, ValueError, KeyError, IndexError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"build-dxgi: {error}\n")
