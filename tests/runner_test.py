import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("mw4_runner", str(ROOT / "runtime/proton"))
spec = importlib.util.spec_from_loader(loader.name, loader)
runner = importlib.util.module_from_spec(spec)
loader.exec_module(runner)


class RunnerTest(unittest.TestCase):
    def test_sparse_cpu_mapping_respects_affinity_and_smt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "online").write_text("0-1,4-15\n")
            for cpu in range(16):
                topology = root / f"cpu{cpu}/topology"
                topology.mkdir(parents=True)
                topology.joinpath("thread_siblings_list").write_text(f"{cpu & ~1}-{cpu | 1}\n")
            env = {}
            with patch.object(runner.os, "sched_getaffinity", return_value={0, 1, 4, 5, 12, 13, 14, 15}):
                affinity = runner.campaign_topology(env, root)
            self.assertEqual(affinity, {0, 1, 4, 5, 12, 13})
            self.assertEqual(env["WINE_CPU_TOPOLOGY"], "3s:0,1,4,5,12,13")
            with patch.object(runner.os, "sched_getaffinity", return_value={1, 4, 5}):
                env = {}
                self.assertEqual(runner.campaign_topology(env, root), {1, 4, 5})
                self.assertEqual(env["WINE_CPU_TOPOLOGY"], "3:1,4,5")
            with patch.object(runner.os, "sched_getaffinity", return_value={14, 15}):
                with self.assertRaisesRegex(ValueError, "No allowed online CPU"):
                    runner.campaign_topology({}, root)

    def test_dense_cpu_host_and_explicit_topology_are_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "online").write_text("0-15\n")
            env = {}
            self.assertIsNone(runner.campaign_topology(env, root))
            self.assertEqual(env, {})
        for topology in ("6s:0,1,4,5,6,7,8,9,10,11,12,13", ""):
            env = {"WINE_CPU_TOPOLOGY": topology}
            self.assertIsNone(runner.campaign_topology(env, Path("/nonexistent")))
            self.assertEqual(env["WINE_CPU_TOPOLOGY"], topology)

    def test_campaign_child_inherits_only_selected_affinity(self):
        original = os.sched_getaffinity(0)
        selected = {min(original)}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / "files/bin/wineserver"
            server.parent.mkdir(parents=True)
            server.symlink_to("/usr/bin/true")
            output = root / "affinity"
            command = [sys.executable, "-c",
                       "import os,pathlib,sys; pathlib.Path(sys.argv[1]).write_text(','.join(map(str,sorted(os.sched_getaffinity(0)))))",
                       str(output)]
            with (root / "lock").open("w") as lock:
                result = runner.run_campaign(command, os.environ.copy(), lock,
                                             root / "prefix", root, selected)
            self.assertEqual(result, 0)
            self.assertEqual(output.read_text(), str(min(original)))
            self.assertEqual(os.sched_getaffinity(0), original)

    def test_stop_waits_for_prefix_processes_before_unlocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / "runtime/proton", root / "proton")
            base = root / "proton-base"
            base.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, signal, time\n"
                "signal.signal(signal.SIGTERM, lambda *args: exit(0))\n"
                "pathlib.Path(__file__).with_name('started').touch()\n"
                "while True: time.sleep(.01)\n")
            base.chmod(0o755)
            server = root / "files/bin/wineserver"
            server.parent.mkdir(parents=True)
            server.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, time\n"
                "prefix = pathlib.Path(os.environ['WINEPREFIX'])\n"
                "prefix.with_name('waiting').touch()\n"
                "while not prefix.with_name('finished').exists(): time.sleep(.01)\n")
            server.chmod(0o755)
            env = dict(os.environ, WINEPREFIX=str(root / "prefix"))
            command = [sys.executable, str(root / "proton"), "run", "/tmp/sp26/sp26-cod.exe"]

            def wait_for(name):
                deadline = time.monotonic() + 5
                while not (root / name).exists():
                    if time.monotonic() > deadline:
                        self.fail(f"Timed out waiting for {name}")
                    time.sleep(.01)

            first = subprocess.Popen(command, env=env)
            try:
                wait_for("started")
                first.send_signal(signal.SIGTERM)
                wait_for("waiting")
                self.assertIsNone(first.poll())
                second = subprocess.run(command, env=env, capture_output=True, timeout=5)
                self.assertEqual(second.returncode, 2)
                self.assertIn(b"already running", second.stderr)
                (root / "finished").touch()
                self.assertEqual(first.wait(timeout=5), 128 + signal.SIGTERM)
                # The completed launch releases the lock for a later launch.
                base.write_text("#!/usr/bin/env python3\n")
                self.assertEqual(subprocess.run(command, env=env, timeout=5).returncode, 0)
            finally:
                (root / "finished").touch()
                if first.poll() is None:
                    first.terminate()
                    first.wait(timeout=5)

    def test_paths_with_spaces_and_windows_drive(self):
        root = Path("/tmp/Custom Runner")
        for path, expected in ((r"D:\Games\Modern Warfare 4\sp26\sp26-cod.exe",
                                r"D:\Games\Modern Warfare 4\sp26\sp26-cod.exe"),
                               ("/mnt/Windows Games/MW4/sp26/sp26-cod.exe",
                                r"Z:\mnt\Windows Games\MW4\sp26\sp26-cod.exe")):
            with self.subTest(path=path):
                command = runner.campaign_command(root, ["waitforexitandrun", path])
                self.assertEqual(command[-1], expected)
                self.assertEqual(command[2], "/tmp/Custom Runner/files/share/mw4/controller.exe")
                self.assertEqual(command[4], r"Z:\tmp\Custom Runner\files\share\mw4\randgrid.sys")

    def test_other_games_and_proton_verbs_are_unchanged(self):
        for arguments in ([], ["getcompatpath", "sp26-cod.exe"],
                          ["run", "other.exe"], ["runinprefix", "wineboot.exe"]):
            with self.subTest(arguments=arguments):
                self.assertIsNone(runner.campaign_command(ROOT, arguments))

    def test_standard_argument_and_unexpected_arguments(self):
        plain = runner.campaign_command(ROOT, ["run", r"D:\sp26\sp26-cod.exe"])
        explicit = runner.campaign_command(ROOT,
            ["run", r"D:\sp26\sp26-cod.exe", runner.GAME_ARGUMENT])
        self.assertEqual(plain, explicit)
        with self.assertRaises(ValueError):
            runner.campaign_command(ROOT, ["run", "sp26-cod.exe", "--unexpected"])


if __name__ == "__main__":
    unittest.main()
