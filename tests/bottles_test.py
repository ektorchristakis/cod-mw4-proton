import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


wine = load("bottles_wine", ROOT / "runtime/bottles-wine")
installer = load("install_bottles", ROOT / "tools/install-bottles.py")


class BottlesTest(unittest.TestCase):
    def test_bottles_start_and_direct_launches_use_campaign_controller(self):
        game = "/external/Game Files/sp26/sp26-cod.exe"
        for arguments in ([game], [game, "hdeyguxs3zaumvlgvybm2vyc"],
                          ["start", "/wait", "/unix", game],
                          ["start.exe", "/b", "/wait", "/d", r"Z:\external\Game Files", "/unix", game],
                          ["start", "/wait", r"D:\Game\sp26\sp26-cod.exe"]):
            self.assertEqual(wine.campaign_arguments(arguments), arguments[-1] if arguments[0] == "start" or arguments[0] == "start.exe" else game)
        self.assertIsNone(wine.campaign_arguments(["wineboot", "-u"]))
        self.assertIsNone(wine.campaign_arguments(["start", "/wait", "/unix", "/external/setup.exe"]))
        with self.assertRaisesRegex(ValueError, "disable virtual desktop"):
            wine.campaign_arguments(["explorer", "/desktop=shell,1280x720", game])
        with self.assertRaisesRegex(ValueError, "standard launch arguments"):
            wine.campaign_arguments([game, "--multiplayer"])

    def fixture(self, temporary):
        root = Path(temporary)
        runner = root / "shared runner"
        binaries = runner / "files/bin"
        binaries.mkdir(parents=True)
        (runner / "version").write_text("1 MW4-Proton-test\n")
        (runner / "toolmanifest.vdf").write_text('"manifest" { "commandline" "/proton %verb%" "require_tool_appid" "4183110" }\n')
        (binaries / "wine").write_text(
            "#!/usr/bin/env python3\n"
            "import json,os,pathlib,sys\n"
            "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps({'arguments':sys.argv[1:],'environment':dict(os.environ)}))\n")
        (binaries / "wine").chmod(0o755)
        (binaries / "wineserver").symlink_to("/usr/bin/true")
        share = runner / "files/share/mw4"
        share.mkdir(parents=True)
        for name in ("controller.exe", "randgrid.sys"):
            (share / name).write_bytes(b"fixture")
        dlls = {
            "x86_64-windows": ("msvcrt.dll", "winhttp.dll"),
            "vkd3d-proton/x86_64-windows": ("d3d12.dll", "d3d12core.dll"),
            "dxvk/x86_64-windows": ("dxgi.dll", "d3d11.dll", "d3d10core.dll"),
            "nvapi/x86_64-windows": ("nvapi64.dll", "nvofapi64.dll"),
            "nvapi/i386-windows": ("nvapi.dll",),
        }
        for directory, names in dlls.items():
            path = runner / "files/lib/wine" / directory
            path.mkdir(parents=True)
            for name in names:
                (path / name).write_text(directory + "/" + name)
        adapter = root / "bottles/runners/MW4-Bottles-test"
        installer.install_adapter(runner, adapter)
        prefix = root / "bottle"
        (prefix / "drive_c/windows/system32").mkdir(parents=True)
        (prefix / "drive_c/windows/syswow64").mkdir()
        capture = root / "capture.json"
        env = dict(os.environ, WINEPREFIX=str(prefix), CAPTURE=str(capture),
                   WINE_CPU_TOPOLOGY="1:0", WINEDLLOVERRIDES="winemenubuilder=d;MSVCRT,unrelated=b;nvapi64=b")
        return runner, adapter, prefix, capture, env

    def test_installed_layout_intercepts_bottles_and_preserves_source_dlls(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner, adapter, prefix, capture, env = self.fixture(temporary)
            foreign = Path(temporary) / "old-renderer.dll"
            foreign.write_text("old renderer must remain unchanged")
            (prefix / "drive_c/windows/system32/d3d12.dll").symlink_to(foreign)
            game = "/external/Game Files/sp26/sp26-cod.exe"
            result = subprocess.run([str(adapter / "files/bin/wine64"), "start", "/wait", "/unix", game],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(capture.read_text())
            self.assertEqual(record["arguments"], [str(runner / "files/share/mw4/controller.exe"), "game",
                                                    wine.load_proton(adapter).windows_path(runner / "files/share/mw4/randgrid.sys"),
                                                    r"C:\mw4-launch.log", r"Z:\external\Game Files\sp26\sp26-cod.exe"])
            overrides = record["environment"]["WINEDLLOVERRIDES"]
            self.assertIn("winemenubuilder=d", overrides)
            self.assertIn("msvcrt=n,b", overrides)
            self.assertNotIn("MSVCRT", overrides)
            self.assertIn("unrelated=b", overrides)
            self.assertIn("nvapi64=n", overrides)
            self.assertEqual(record["environment"]["WINE_DISABLE_EXE_ASLR"], "1")
            self.assertEqual(record["environment"]["WINELOADER"], str(runner / "files/bin/wine"))
            self.assertEqual((prefix / "drive_c/windows/system32/d3d12.dll").read_text(), "vkd3d-proton/x86_64-windows/d3d12.dll")
            self.assertEqual(foreign.read_text(), "old renderer must remain unchanged")
            self.assertEqual((adapter / "files/lib").resolve(), runner / "files/lib")
            self.assertEqual((adapter / "bin/wine").resolve(), adapter / "files/bin/wine")
            self.assertIn('"4183110"', (adapter / "toolmanifest.vdf").read_text())

    def test_version_and_prefix_tools_delegate_without_campaign_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner, adapter, prefix, capture, env = self.fixture(temporary)
            del env["WINEPREFIX"]
            result = subprocess.run([str(adapter / "bin/wine"), "--version"], env=env)
            self.assertEqual(result.returncode, 0)
            record = json.loads(capture.read_text())
            self.assertEqual(record["arguments"], ["--version"])
            self.assertIn("msvcrt=n,b", record["environment"]["WINEDLLOVERRIDES"])
            self.assertIn("winhttp=n,b", record["environment"]["WINEDLLOVERRIDES"])
            self.assertEqual(list((prefix / "drive_c/windows/system32").iterdir()), [])

    def test_first_wineboot_seeds_native_dlls_before_delegating(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner, adapter, prefix, capture, env = self.fixture(temporary)
            fresh = Path(temporary) / "fresh bottle"
            env["WINEPREFIX"] = str(fresh)
            result = subprocess.run([str(adapter / "bin/wine"), "wineboot", "-i"], env=env)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(capture.read_text())["arguments"], ["wineboot", "-i"])
            for dll in ("msvcrt.dll", "winhttp.dll"):
                self.assertEqual((fresh / "drive_c/windows/system32" / dll).read_text(),
                                 "x86_64-windows/" + dll)

    def test_campaign_cannot_write_through_external_windows_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner, adapter, prefix, capture, env = self.fixture(temporary)
            system32 = prefix / "drive_c/windows/system32"
            system32.rmdir()
            outside = Path(temporary) / "original Windows system32"
            outside.mkdir()
            system32.symlink_to(outside, target_is_directory=True)
            result = subprocess.run([str(adapter / "bin/wine"), "/game/sp26/sp26-cod.exe"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("outside its prefix", result.stderr)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse(capture.exists())

    def test_runner_discovery_respects_xdg_and_flatpak_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            data = home / "custom-data"
            native = data / "bottles"
            flatpak = home / ".var/app/com.usebottles.bottles/data/bottles"
            native.mkdir(parents=True)
            flatpak.mkdir(parents=True)
            self.assertEqual(installer.bottles_roots(home, data), [("native", native), ("flatpak", flatpak)])


if __name__ == "__main__":
    unittest.main()
