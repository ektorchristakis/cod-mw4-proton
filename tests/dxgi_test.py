import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dxgi", ROOT / "tools/build-dxgi.py")
dxgi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dxgi)


class DxgiTest(unittest.TestCase):
    @contextlib.contextmanager
    def build_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in dxgi.BUILD_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            data = bytearray(128)
            data[:2] = b"MZ"
            struct.pack_into("<I", data, 0x3c, 64)
            data[64:68] = b"PE\0\0"
            struct.pack_into("<H", data, 68, 0x8664)
            struct.pack_into("<H", data, 88, 0x20b)
            (root / "x64/dxgi.dll").write_bytes(data)
            (root / "source-inputs/dxgi-memory-budget.patch").write_bytes(
                (ROOT / "patches/dxgi-memory-budget.patch").read_bytes())
            metadata = {
                "dxvk": dxgi.REVISION, "ge_proton": dxgi.GE_REVISION,
                "source_patch_sha256": dxgi.PREPARED_PATCH_SHA256,
                "budget_patch_sha256": dxgi.BUDGET_PATCH_SHA256,
                "normalized_build_paths": True, "insert_pe_timestamp": False,
                "buildtype": "release",
                "files": {name: dxgi.sha256(root / name) for name in dxgi.BUILD_FILES},
            }
            (root / "build-info.json").write_text(json.dumps(metadata))
            inputs = {name: dxgi.sha256(root / "source-inputs" / name) for name in dxgi.GE_PATCHES}
            with patch.object(dxgi, "GE_PATCHES", inputs), patch.object(
                    dxgi, "GE_PREP_SHA256", dxgi.sha256(root / "source-inputs/protonprep-valve-staging.sh")):
                yield root, metadata

    def test_complete_build_and_changed_dll(self):
        with self.build_fixture() as (root, metadata):
            self.assertEqual(dxgi.check_build(root), metadata)
            with (root / "x64/dxgi.dll").open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch: x64/dxgi.dll"):
                dxgi.check_build(root)

    def test_source_inputs_are_pinned_even_if_manifest_is_rehashed(self):
        with self.build_fixture() as (root, metadata):
            name = next(iter(dxgi.GE_PATCHES))
            relative = "source-inputs/" + name
            (root / relative).write_bytes(b"different GE patch")
            metadata["files"][relative] = dxgi.sha256(root / relative)
            (root / "build-info.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "source input differs"):
                dxgi.check_build(root)

    def test_rejects_wrong_architecture_with_matching_file_hash(self):
        with self.build_fixture() as (root, metadata):
            image = root / "x64/dxgi.dll"
            data = bytearray(image.read_bytes())
            struct.pack_into("<H", data, 68, 0x14c)
            image.write_bytes(data)
            metadata["files"]["x64/dxgi.dll"] = dxgi.sha256(image)
            (root / "build-info.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "x86_64 PE32"):
                dxgi.check_build(root)

    def test_rejects_instrumented_recipe_and_extra_payload_files(self):
        with self.build_fixture() as (root, metadata):
            metadata["source_patch_sha256"] = hashlib.sha256(b"extra diagnostics").hexdigest()
            with self.assertRaisesRegex(ValueError, "pinned portable budget variant"):
                dxgi.check_metadata(metadata)
            metadata["source_patch_sha256"] = dxgi.PREPARED_PATCH_SHA256
            metadata["files"]["x64/diagnostics.dll"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "unexpected files"):
                dxgi.check_metadata(metadata)


if __name__ == "__main__":
    unittest.main()
