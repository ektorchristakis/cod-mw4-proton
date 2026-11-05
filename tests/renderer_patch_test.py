import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_runner", ROOT / "tools/build-runner.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class RendererPatchTest(unittest.TestCase):
    def metadata(self):
        patch = ROOT / "patches/vkd3d-aligned-heaps.patch"
        return {
            "vkd3d_proton": builder.VKD3D_REVISION,
            "dxil_spirv": builder.DXIL_REVISION,
            "local_source_patches": [{"name": patch.name, "sha256": builder.sha256(patch)}],
        }

    def test_accepts_pinned_renderer_with_patch(self):
        builder.check_renderer_metadata(self.metadata())

    def test_rejects_missing_or_changed_patch(self):
        for patches in ([], [{"name": "vkd3d-aligned-heaps.patch", "sha256": "0" * 64}]):
            metadata = self.metadata()
            metadata["local_source_patches"] = patches
            with self.subTest(patches=patches), self.assertRaisesRegex(ValueError, "aligned-heap"):
                builder.check_renderer_metadata(metadata)


if __name__ == "__main__":
    unittest.main()
