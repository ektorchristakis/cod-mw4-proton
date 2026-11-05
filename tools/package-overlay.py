#!/usr/bin/env python3
"""Package runtime additions and rebuilt graphics sources without the GE base."""

import argparse
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_runner", ROOT / "tools/build-runner.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def git(repository, *arguments):
    return subprocess.check_output(["git", "-C", str(repository), *arguments])


def archive_renderer(source, destination, metadata):
    if git(source, "rev-parse", "HEAD").decode().strip() != builder.VKD3D_REVISION:
        raise ValueError("Renderer source does not match VKD3D's pinned revision")
    revisions = {".": builder.VKD3D_REVISION, **metadata["submodules"]}
    if revisions.get("subprojects/dxil-spirv") != builder.DXIL_REVISION:
        raise ValueError("Renderer source manifest does not select the expected dxil-spirv")
    epoch = int(git(source, "show", "-s", "--format=%ct", "HEAD"))
    archived_repositories = {}

    def normalize(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = epoch
        return info

    def add_repository(repository, relative, archive):
        revision = git(repository, "rev-parse", "HEAD").decode().strip()
        key = str(relative) if relative.parts else "."
        if revisions.get(key) != revision:
            raise ValueError(f"Source revision mismatch or unrecorded submodule: {key}")
        for arguments in (("diff", "--quiet", "--ignore-submodules=all"),
                          ("diff", "--cached", "--quiet", "--ignore-submodules=all")):
            subprocess.run(["git", "-C", str(repository), *arguments], check=True)
        archived_repositories[key] = revision
        for entry in git(repository, "ls-files", "--stage", "-z").split(b"\0"):
            if not entry:
                continue
            attributes, name = entry.split(b"\t", 1)
            mode, _, stage = attributes.split()
            if stage != b"0":
                raise ValueError("Unmerged renderer source")
            path = Path(name.decode())
            if mode == b"160000":
                add_repository(repository / path, relative / path, archive)
            else:
                archive.add(repository / path, arcname=str(Path("vkd3d-proton") / relative / path),
                            recursive=False, filter=normalize)

    with tarfile.open(destination, "w:xz") as archive:
        add_repository(source, Path(), archive)
        patch = ROOT / "patches/vkd3d-aligned-heaps.patch"
        if builder.sha256(patch) != metadata["local_source_patches"][0]["sha256"]:
            raise ValueError("Renderer patch changed during packaging")
        archive.add(patch, arcname="MW4-PATCHES/" + patch.name, recursive=False, filter=normalize)
        data = (json.dumps({"repositories": archived_repositories,
                            "local_source_patches": metadata["local_source_patches"]}, indent=2) + "\n").encode()
        info = normalize(tarfile.TarInfo("SOURCE-MANIFEST.json"))
        info.size = len(data)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(data))
    if set(archived_repositories) != set(revisions):
        raise ValueError("Renderer source manifest contains missing or extra repositories")


def package(renderer, renderer_source, dxgi, dxgi_source, output, nvapi_archive=None):
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    metadata = json.loads((renderer / "build-info.json").read_text())
    builder.check_renderer_metadata(metadata)
    if not metadata.get("normalized_build_paths"):
        raise ValueError("Use the portable renderer build with normalized compiler paths")
    dxgi_metadata = builder.dxgi.check_build(dxgi)
    if builder.dxgi.check_source(dxgi_source) != dxgi_metadata.get("submodules"):
        raise ValueError("DXGI source does not match its build manifest")
    nvapi_archive = builder.nvapi.release_archive(nvapi_archive)
    source_hashes = {str(path.relative_to(ROOT)): builder.sha256(path) for path in builder.source_files()}
    subprocess.run(["make", "all"], cwd=ROOT, check=True)
    version = (ROOT / "VERSION").read_text().strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mw4-overlay-", dir=output.parent) as directory:
        overlay = Path(directory) / f"MW4-Proton-{version}-overlay"
        overlay.mkdir()
        for relative, digest in source_hashes.items():
            if builder.sha256(ROOT / relative) != digest:
                raise ValueError(f"Source changed during packaging: {relative}")
            destination = overlay / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        payload = overlay / "payload"
        payload.mkdir()
        hashes = {}
        for name in ("controller.exe", "randgrid.sys", "crt_adapter.dll", "winhttp_adapter.dll"):
            shutil.copy2(ROOT / "build" / name, payload / name)
            hashes[name] = builder.sha256(payload / name)
        (payload / "manifest.json").write_text(json.dumps(
            {"version": version, "files": hashes, "source_files": source_hashes}, indent=2) + "\n")
        (overlay / "renderer/x64").mkdir(parents=True)
        for name in ("d3d12.dll", "d3d12core.dll"):
            if builder.sha256(renderer / "x64" / name) != metadata["files"][f"x64/{name}"]:
                raise ValueError(f"Renderer hash mismatch: {name}")
            shutil.copy2(renderer / "x64" / name, overlay / "renderer/x64" / name)
        shutil.copy2(renderer / "build-info.json", overlay / "renderer/build-info.json")
        shutil.copytree(renderer / "licenses", overlay / "renderer/licenses")
        archive = overlay / "renderer/source.tar.xz"
        archive_renderer(renderer_source, archive, metadata)
        for relative in (*dxgi_metadata["files"], "build-info.json"):
            destination = overlay / "dxgi" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dxgi / relative, destination)
        builder.dxgi.check_build(overlay / "dxgi")
        dxgi_archive = overlay / "dxgi/source.tar.xz"
        builder.dxgi.archive_source(dxgi_source, dxgi, dxgi_archive)
        (overlay / "nvapi").mkdir()
        shutil.copy2(nvapi_archive, overlay / "nvapi" / builder.nvapi.ARCHIVE)
        if builder.sha256(overlay / "nvapi" / builder.nvapi.ARCHIVE) != builder.nvapi.ARCHIVE_SHA256:
            raise ValueError("DXVK-NVAPI archive changed during packaging")
        (overlay / "release-manifest.json").write_text(json.dumps({
            "version": version,
            "base_download_sha256": builder.BASE_ARCHIVE_SHA256,
            "renderer_source_sha256": builder.sha256(archive),
            "payload": hashes,
            "renderer": metadata["files"],
            "dxgi": {"dxvk": builder.dxgi.REVISION, "ge_proton": builder.dxgi.GE_REVISION,
                     "source_patch_sha256": builder.dxgi.PREPARED_PATCH_SHA256,
                     "files": dxgi_metadata["files"],
                     "source_archive_sha256": builder.sha256(dxgi_archive)},
            "dxvk_nvapi": {
                "version": builder.nvapi.VERSION,
                "revision": builder.nvapi.REVISION,
                "release_archive_sha256": builder.nvapi.ARCHIVE_SHA256,
            },
        }, indent=2) + "\n")
        subprocess.run(["mv", "-T", "--no-clobber", "--", str(overlay), str(output)], check=True)
        if overlay.exists():
            raise FileExistsError(f"Output appeared during packaging: {output}")
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--renderer-source", type=Path, required=True)
    parser.add_argument("--dxgi", type=Path, required=True)
    parser.add_argument("--dxgi-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--nvapi-archive", type=Path,
                        help="Use the pinned DXVK-NVAPI release archive without downloading")
    args = parser.parse_args()
    try:
        package(args.renderer.resolve(strict=True), args.renderer_source.resolve(strict=True),
                args.dxgi.resolve(strict=True), args.dxgi_source.resolve(strict=True),
                args.output.absolute(), args.nvapi_archive)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"package-overlay: {error}\n")


if __name__ == "__main__":
    main()
