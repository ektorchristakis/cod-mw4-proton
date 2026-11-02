#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir=
work_dir="$repo_dir/build/vkd3d"
while (($#)); do
    case "$1" in
        --output) output_dir="${2:?--output requires a directory}"; shift 2 ;;
        --work-dir) work_dir="${2:?--work-dir requires a directory}"; shift 2 ;;
        --help)
            echo "Usage: tools/build-vkd3d.sh --output DIRECTORY [--work-dir DIRECTORY]"
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
if [[ -z "$output_dir" ]]; then
    echo "--output is required" >&2
    exit 2
fi
output_dir="$(realpath -m -- "$output_dir")"
work_dir="$(realpath -m -- "$work_dir")"
if [[ -e "$output_dir" || -L "$output_dir" ]]; then
    echo "Output already exists: $output_dir" >&2
    exit 1
fi

vkd3d_revision=4522cc1a8b1347f1ab1b0f7b14a23ed9444d95d1
dxil_revision=4e4c4be90b7e8008194ae70243d54c762aba021f
source_dir="$work_dir/source"
build_dir="$work_dir/x64"
case "$work_dir/" in
    "$output_dir/"*) echo "Output must not contain the work directory" >&2; exit 1 ;;
esac
case "$output_dir/" in
    "$source_dir/"*|"$build_dir/"*) echo "Output must be separate from source and build files" >&2; exit 1 ;;
esac
mkdir -p -- "$work_dir"
if [[ ! -d "$source_dir" ]]; then
    git clone --depth 1 --branch v3.1 \
        https://github.com/HansKristian-Work/vkd3d-proton.git "$source_dir"
fi
if [[ "$(git -C "$source_dir" rev-parse HEAD)" != "$vkd3d_revision" ]]; then
    echo "Work directory contains a different VKD3D revision; choose another --work-dir" >&2
    exit 1
fi
if [[ -n "$(git -C "$source_dir" status --porcelain --untracked-files=no --ignore-submodules=all)" ]]; then
    echo "Work directory contains local source edits" >&2
    exit 1
fi

git -C "$source_dir" submodule foreach --recursive 'git diff --quiet && git diff --cached --quiet'
git -C "$source_dir" submodule update --init --recursive --depth 1
dxil_dir="$source_dir/subprojects/dxil-spirv"
git -C "$dxil_dir" fetch --depth 1 origin "$dxil_revision"
git -C "$dxil_dir" checkout --detach "$dxil_revision"
git -C "$dxil_dir" submodule update --init --recursive --depth 1

sysroot="$(realpath -m -- "$(x86_64-w64-mingw32-g++ -print-sysroot)")"
prefix_args="$(python3 - "$work_dir" "$sysroot" <<'PY'
import json
import sys
print(json.dumps([
    f"-ffile-prefix-map={sys.argv[1]}=/usr/src/mw4-proton",
    f"-ffile-prefix-map={sys.argv[2]}=/usr/x86_64-w64-mingw32/sys-root",
]))
PY
)"
setup_args=()
if [[ -f "$build_dir/meson-private/coredata.dat" ]]; then
    setup_args+=(--reconfigure)
fi
meson setup "${setup_args[@]}" "$build_dir" "$source_dir" \
    --cross-file "$source_dir/build-win64.txt" \
    --buildtype debugoptimized --prefix "$output_dir" --bindir x64 --libdir x64 \
    -Denable_tests=false -Denable_extras=false -Denable_trace=false \
    "-Dc_args=$prefix_args" "-Dcpp_args=$prefix_args" \
    -Dc_link_args=-Wl,--no-insert-timestamp -Dcpp_link_args=-Wl,--no-insert-timestamp
meson compile -C "$build_dir" -j 6

mkdir -p -- "$(dirname -- "$output_dir")"
mkdir -- "$output_dir"
install -Dm644 "$build_dir/libs/d3d12/d3d12.dll" "$output_dir/x64/d3d12.dll"
install -Dm644 "$build_dir/libs/d3d12core/d3d12core.dll" "$output_dir/x64/d3d12core.dll"
x86_64-w64-mingw32-strip --strip-debug --preserve-dates "$output_dir/x64/d3d12.dll" "$output_dir/x64/d3d12core.dll"
install -Dm644 "$source_dir/LICENSE" "$output_dir/licenses/vkd3d-LICENSE"
install -Dm644 "$source_dir/COPYING" "$output_dir/licenses/vkd3d-COPYING"
install -Dm644 "$dxil_dir/LICENSE.MIT" "$output_dir/licenses/dxil-spirv-LICENSE.MIT"
install -Dm644 "$dxil_dir/subprojects/dxbc-spirv/LICENSE" "$output_dir/licenses/dxbc-spirv-LICENSE"
install -Dm644 "$source_dir/khronos/Vulkan-Headers/LICENSE.md" "$output_dir/licenses/Vulkan-Headers-LICENSE.md"
install -Dm644 "$source_dir/khronos/SPIRV-Headers/LICENSE" "$output_dir/licenses/SPIRV-Headers-LICENSE"

python3 - "$output_dir" "$source_dir" "$vkd3d_revision" "$dxil_revision" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

output, source = map(Path, sys.argv[1:3])
submodules = subprocess.check_output(
    ["git", "-C", str(source), "submodule", "status", "--recursive"], text=True)
metadata = {
    "vkd3d_proton": sys.argv[3],
    "dxil_spirv": sys.argv[4],
    "buildtype": "debugoptimized",
    "enable_trace": False,
    "strip_debug": True,
    "normalized_build_paths": True,
    "insert_pe_timestamp": False,
    "local_source_patches": [],
    "submodules": {line.split()[1]: line.split()[0].lstrip(" +-")
                   for line in submodules.splitlines()},
    "files": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted((output / "x64").glob("*.dll"))},
}
(output / "build-info.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata, indent=2))
PY
