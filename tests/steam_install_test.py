import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()
spec = importlib.util.spec_from_file_location("install_steam", ROOT / "tools/install-steam.py")
steam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(steam)


class SteamInstallTest(unittest.TestCase):
    def assembled_fixture(self, runner):
        required = {str(steam.builder.WINE_DLLS / name) for name in steam.builder.BASE_HASHES}
        required.update(str(steam.builder.RENDERER_DLLS / name) for name in ("d3d12.dll", "d3d12core.dll"))
        required.update(steam.builder.nvapi.FILES.values())
        required.update(("proton", "proton-base", "version", "compatibilitytool.vdf", "files/share/mw4/controller.exe", "files/share/mw4/randgrid.sys"))
        hashes = {}
        for relative in required:
            path = runner / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode())
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in ("wine", "wineserver"):
            path = runner / "files/bin" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        toolmanifest = runner / "toolmanifest.vdf"
        toolmanifest.write_text('"manifest" { "require_tool_appid" "4183110" }\n')
        manifest = {"version": VERSION, "dxvk_nvapi": {"version": steam.builder.nvapi.VERSION, "revision": steam.builder.nvapi.REVISION, "release_archive_sha256": steam.builder.nvapi.ARCHIVE_SHA256}, "files": hashes,
                    "toolmanifest_sha256": hashlib.sha256(toolmanifest.read_bytes()).hexdigest()}
        record = runner / "files/share/mw4/manifest.json"
        record.write_text(json.dumps(manifest))
        return manifest, record

    def test_detects_native_and_flatpak_roots_and_deduplicates_links(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            data = home / ".local/share"
            native = data / "Steam"
            (native / "steamapps").mkdir(parents=True)
            (home / ".steam").mkdir()
            (home / ".steam/root").symlink_to(native)
            flatpak = home / ".var/app/com.valvesoftware.Steam/data/Steam"
            (flatpak / "config").mkdir(parents=True)
            self.assertEqual(steam.steam_roots(home, data), [("native", native), ("flatpak", flatpak)])
            with patch.object(steam.Path, "home", return_value=home), patch.dict(steam.os.environ, {"XDG_DATA_HOME": str(data)}):
                with self.assertRaisesRegex(ValueError, "Multiple Steam"):
                    steam.steam_root("auto")
                self.assertEqual(steam.steam_root("flatpak"), flatpak)
                self.assertEqual(steam.steam_root("native"), native)

    def test_missing_installation_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.object(steam.Path, "home", return_value=home), patch.dict(steam.os.environ, {"XDG_DATA_HOME": str(home / "data")}):
                with self.assertRaisesRegex(ValueError, "start Steam once"):
                    steam.steam_root("auto")

    def test_installer_forwards_spaced_paths_without_a_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "Steam Data"
            data.mkdir()
            args = ["install-steam.py", "--steam-root", str(data), "--base-runner", str(root / "GE Base"), "--cache", str(root / "Download Cache")]
            with patch.object(steam.sys, "argv", args), patch.object(steam.subprocess, "run") as run:
                self.assertEqual(steam.main(), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[-4:], ["--base-runner", str(root / "GE Base"), "--cache", str(root / "Download Cache")])
            self.assertNotIn("shell", run.call_args.kwargs)
            self.assertIn(str(data / "compatibilitytools.d" / f"MW4-Proton-{VERSION}"), command)

    def test_registration_links_without_copying_and_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "Steam"
            data.mkdir()
            runner = root / "Existing Runner"
            runner.mkdir()
            args = ["install-steam.py", "--steam-root", str(data), "--runner", str(runner)]
            with patch.object(steam.sys, "argv", args), patch.object(steam.builder, "check_installed_runner", return_value=runner), patch.object(steam.subprocess, "run") as run:
                self.assertEqual(steam.main(), 0)
                run.assert_not_called()
                link = data / "compatibilitytools.d" / f"MW4-Proton-{VERSION}"
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), runner)
                with self.assertRaises(SystemExit) as error:
                    steam.main()
                self.assertEqual(error.exception.code, 1)

    def test_dry_run_creates_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            with patch.object(steam.sys, "argv", ["install-steam.py", "--steam-root", str(data), "--dry-run"]), patch.object(steam.subprocess, "run") as run:
                self.assertEqual(steam.main(), 0)
                run.assert_not_called()
            self.assertEqual(list(data.iterdir()), [])

    def test_flatpak_registration_requires_sandbox_read_access(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            args = ["install-steam.py", "--steam", "flatpak", "--steam-root", str(data), "--runner", str(data / "runner")]
            with patch.object(steam.sys, "argv", args), patch.object(steam.builder, "check_installed_runner", return_value=data / "runner"), patch.object(steam.subprocess, "run") as run:
                run.return_value.returncode = 1
                with self.assertRaises(SystemExit) as error:
                    steam.main()
                self.assertEqual(error.exception.code, 1)
                self.assertEqual(run.call_args.args[0][:5], ["flatpak", "run", "--command=test", "com.valvesoftware.Steam", "-r"])
            self.assertEqual(list(data.iterdir()), [])

    def test_registration_rejects_changed_or_missing_components(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Path(directory)
            manifest, record = self.assembled_fixture(runner)
            self.assertEqual(steam.builder.check_installed_runner(runner), runner)
            (runner / "proton").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                steam.builder.check_installed_runner(runner)
            del manifest["files"]["proton"]
            record.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "missing installed components"):
                steam.builder.check_installed_runner(runner)

    def test_registration_requires_executable_wine_and_wineserver(self):
        for name in ("wine", "wineserver"):
            for damage in ("missing", "not-executable"):
                with self.subTest(name=name, damage=damage), tempfile.TemporaryDirectory() as directory:
                    runner = Path(directory)
                    self.assembled_fixture(runner)
                    executable = runner / "files/bin" / name
                    if damage == "missing":
                        executable.unlink()
                    else:
                        executable.chmod(0o644)
                    with self.assertRaisesRegex(ValueError, "missing or not executable"):
                        steam.builder.check_installed_runner(runner)

    def test_registration_requires_recorded_runtime_manifest_and_expected_appid(self):
        for damage in ("changed", "missing-file", "missing-record", "wrong-appid", "malformed"):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as directory:
                runner = Path(directory)
                manifest, record = self.assembled_fixture(runner)
                toolmanifest = runner / "toolmanifest.vdf"
                if damage == "missing-record":
                    del manifest["toolmanifest_sha256"]
                elif damage == "missing-file":
                    toolmanifest.unlink()
                elif damage == "changed":
                    toolmanifest.write_text(toolmanifest.read_text() + "\n")
                else:
                    text = '"manifest" { "require_tool_appid" "123" }\n' if damage == "wrong-appid" else 'broken\n'
                    toolmanifest.write_text(text)
                    manifest["toolmanifest_sha256"] = hashlib.sha256(toolmanifest.read_bytes()).hexdigest()
                record.write_text(json.dumps(manifest))
                with self.assertRaisesRegex((OSError, ValueError), "toolmanifest"):
                    steam.builder.check_installed_runner(runner)


if __name__ == "__main__":
    unittest.main()
