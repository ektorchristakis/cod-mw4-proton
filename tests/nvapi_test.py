import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nvapi", ROOT / "tools/nvapi.py")
nvapi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nvapi)


class NvapiTest(unittest.TestCase):
    def archive(self, root, linked=None):
        archive = root / "nvapi.tar.gz"
        with tarfile.open(archive, "w:gz") as package:
            for name in nvapi.FILES:
                member = tarfile.TarInfo("./" + name)
                if name == linked:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/outside"
                    package.addfile(member)
                    continue
                data = name.encode()
                if name.endswith(".json"):
                    data = json.dumps({"layer": {"library_path": "./libdxvk_nvapi_vkreflex_layer.so"}}).encode()
                member.size = len(data)
                package.addfile(member, io.BytesIO(data))
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_verified_offline_archive_never_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, digest = self.archive(Path(directory))
            with patch.object(nvapi, "ARCHIVE_SHA256", digest), patch.object(nvapi.urllib.request, "urlopen") as download:
                self.assertEqual(nvapi.release_archive(archive), archive)
                download.assert_not_called()

    def test_changed_archive_rejected_before_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, digest = self.archive(root)
            with archive.open("ab") as stream:
                stream.write(b"changed")
            with patch.object(nvapi, "ARCHIVE_SHA256", digest):
                with self.assertRaisesRegex(ValueError, "unexpected SHA-256"):
                    nvapi.release_archive(archive)
                with self.assertRaisesRegex(ValueError, "unexpected SHA-256"):
                    nvapi.install(archive, root / "runner")
            self.assertFalse((root / "runner").exists())

    def test_complete_runtime_install_preserves_alias_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, digest = self.archive(root)
            runner = root / "runner"
            original = root / "base.dll"
            original.write_bytes(b"base DLL")
            symlink = runner / nvapi.FILES["x64/nvapi64.dll"]
            symlink.parent.mkdir(parents=True)
            symlink.symlink_to(original)
            hardlink = runner / nvapi.FILES["x64/nvofapi64.dll"]
            hardlink.hardlink_to(original)
            with patch.object(nvapi, "ARCHIVE_SHA256", digest):
                metadata = nvapi.install(archive, runner)
            self.assertEqual(original.read_bytes(), b"base DLL")
            self.assertFalse(symlink.is_symlink())
            for relative in (
                    "files/lib/wine/nvapi/i386-windows/nvapi.dll",
                    "files/lib/wine/nvapi/x86_64-windows/nvapi64.dll",
                    "files/lib/wine/nvapi/x86_64-windows/nvofapi64.dll",
                    "files/lib/x86_64-linux-gnu/libdxvk_nvapi_vkreflex_layer.so",
                    "files/share/dxvk-nvapi-vkreflex-layer/implicit_layer.d/VkLayer_DXVK_NVAPI_reflex.json",
                    "files/share/mw4/licenses/DXVK-NVAPI-LICENSE",
                    "files/share/mw4/dxvk-nvapi/README.md"):
                self.assertTrue((runner / relative).is_file(), relative)
            self.assertEqual(set(metadata["inputs"]), set(nvapi.FILES))
            for source, relative in nvapi.FILES.items():
                destination = runner / relative
                self.assertTrue(destination.is_file())
                if not source.endswith(".json"):
                    self.assertEqual(destination.read_bytes(), source.encode())
            layer = runner / nvapi.FILES["layer/VkLayer_DXVK_NVAPI_reflex.json"]
            library = json.loads(layer.read_text())["layer"]["library_path"]
            self.assertEqual((layer.parent / library).resolve(),
                             (runner / nvapi.FILES["layer/libdxvk_nvapi_vkreflex_layer.so"]).resolve())

    def test_archive_links_are_not_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, digest = self.archive(root, linked="x32/nvapi.dll")
            with patch.object(nvapi, "ARCHIVE_SHA256", digest):
                with self.assertRaisesRegex(ValueError, "not a regular file"):
                    nvapi.install(archive, root / "runner")
            self.assertFalse((root / "runner").exists())

    def test_ancestor_escape_rejected_before_any_component_is_written(self):
        for relative in ("files/lib/wine/nvapi", "files/share/mw4/dxvk-nvapi"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive, digest = self.archive(root)
                runner = root / "runner"
                external = root / "external-base"
                (external / "i386-windows").mkdir(parents=True)
                original = external / "i386-windows/nvapi.dll"
                original.write_bytes(b"original DLL")
                link = runner / relative
                link.parent.mkdir(parents=True)
                link.symlink_to(external, target_is_directory=True)
                before = {str(p.relative_to(runner)) for p in runner.rglob("*")}
                with patch.object(nvapi, "ARCHIVE_SHA256", digest):
                    with self.assertRaisesRegex(ValueError, "escapes the assembly"):
                        nvapi.install(archive, runner)
                self.assertEqual(original.read_bytes(), b"original DLL")
                self.assertEqual({str(p.relative_to(runner)) for p in runner.rglob("*")}, before)
                self.assertEqual({str(p.relative_to(external)) for p in external.rglob("*")},
                                 {"i386-windows", "i386-windows/nvapi.dll"})


if __name__ == "__main__":
    unittest.main()
