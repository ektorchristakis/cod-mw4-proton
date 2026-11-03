"""Pinned upstream DXVK-NVAPI release used by the builder and overlay."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner_files", ROOT / "tools/runner_files.py")
runner_files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner_files)
VERSION = "0.9.3"
REVISION = "9c0f214cb66b543ed6604ef04c29fde98832dc77"
ARCHIVE = f"dxvk-nvapi-v{VERSION}.tar.gz"
URL = f"https://github.com/jp7677/dxvk-nvapi/releases/download/v{VERSION}/{ARCHIVE}"
ARCHIVE_SHA256 = "284033c38e463ba31d40466d650d0c411df6f64bbf8ed3d19c9ca0cadf31dfd3"
FILES = {
    "x32/nvapi.dll": "files/lib/wine/nvapi/i386-windows/nvapi.dll",
    "x64/nvapi64.dll": "files/lib/wine/nvapi/x86_64-windows/nvapi64.dll",
    "x64/nvofapi64.dll": "files/lib/wine/nvapi/x86_64-windows/nvofapi64.dll",
    "layer/libdxvk_nvapi_vkreflex_layer.so": "files/lib/x86_64-linux-gnu/libdxvk_nvapi_vkreflex_layer.so",
    "layer/VkLayer_DXVK_NVAPI_reflex.json": "files/share/dxvk-nvapi-vkreflex-layer/implicit_layer.d/VkLayer_DXVK_NVAPI_reflex.json",
    "LICENSE": "files/share/mw4/licenses/DXVK-NVAPI-LICENSE",
    "README.md": "files/share/mw4/dxvk-nvapi/README.md",
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def release_archive(path=None):
    if path is not None:
        archive = path.resolve(strict=True)
    elif (ROOT / "nvapi" / ARCHIVE).is_file():
        archive = ROOT / "nvapi" / ARCHIVE
    else:
        archive = ROOT / "build/downloads" / ARCHIVE
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists() or sha256(archive) != ARCHIVE_SHA256:
            print(f"Downloading the official DXVK-NVAPI {VERSION} archive...", flush=True)
            request = urllib.request.Request(URL, headers={"User-Agent": "MW4-Proton builder"})
            with tempfile.NamedTemporaryFile(dir=archive.parent, prefix="nvapi-download-", delete=False) as temporary:
                download = Path(temporary.name)
                try:
                    with urllib.request.urlopen(request, timeout=60) as response:
                        shutil.copyfileobj(response, temporary)
                    temporary.flush()
                    if sha256(download) != ARCHIVE_SHA256:
                        raise ValueError("Downloaded DXVK-NVAPI archive has an unexpected SHA-256")
                    download.replace(archive)
                finally:
                    download.unlink(missing_ok=True)
    if sha256(archive) != ARCHIVE_SHA256:
        raise ValueError("DXVK-NVAPI archive has an unexpected SHA-256")
    return archive


def install(archive, runner):
    if sha256(archive) != ARCHIVE_SHA256:
        raise ValueError("DXVK-NVAPI archive has an unexpected SHA-256")
    runner = runner.resolve()
    destinations = {source: runner_files.checked_destination(runner, runner / relative)
                    for source, relative in FILES.items()}
    inputs = {}
    with tarfile.open(archive, "r:gz") as package:
        for source in FILES:
            member = package.getmember("./" + source)
            if not member.isfile():
                raise ValueError(f"DXVK-NVAPI archive member is not a regular file: {source}")
            data = package.extractfile(member).read()
            inputs[source] = hashlib.sha256(data).hexdigest()
            if source.endswith("VkLayer_DXVK_NVAPI_reflex.json"):
                manifest = json.loads(data)
                manifest["layer"]["library_path"] = "../../../lib/x86_64-linux-gnu/libdxvk_nvapi_vkreflex_layer.so"
                data = (json.dumps(manifest, indent=2) + "\n").encode()
            destination = runner_files.prepare_destination(runner, destinations[source])
            destination.write_bytes(data)
            destination.chmod(0o755 if source.endswith(".so") else 0o644)
    return {
        "version": VERSION,
        "revision": REVISION,
        "source": f"https://github.com/jp7677/dxvk-nvapi/tree/{REVISION}",
        "release_url": URL,
        "release_archive_sha256": ARCHIVE_SHA256,
        "inputs": inputs,
    }
