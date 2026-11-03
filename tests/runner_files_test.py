import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner_files", ROOT / "tools/runner_files.py")
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)


class RunnerFilesTest(unittest.TestCase):
    def test_replacement_rejects_escaping_directory_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "new.dll"
            source.write_bytes(b"new DLL")
            runner = root / "runner"
            runner.mkdir()
            base = root / "base"
            base.mkdir()
            original = base / "old.dll"
            original.write_bytes(b"original DLL")
            (runner / "libraries").symlink_to(base, target_is_directory=True)
            for destination in (runner / "libraries/old.dll", runner / "libraries/new/subdir/new.dll"):
                with self.assertRaisesRegex(ValueError, "escapes the assembly"):
                    files.replace_file(source, destination, runner)
            self.assertEqual(original.read_bytes(), b"original DLL")
            self.assertEqual(list(base.iterdir()), [original])

    def test_internal_directory_alias_and_leaf_alias_are_materialized_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "new.dll"
            source.write_bytes(b"new DLL")
            original = root / "old.dll"
            original.write_bytes(b"original DLL")
            runner = root / "runner"
            (runner / "real").mkdir(parents=True)
            (runner / "libraries").symlink_to(runner / "real", target_is_directory=True)
            destination = runner / "libraries/file.dll"
            destination.symlink_to(original)
            files.replace_file(source, destination, runner)
            self.assertFalse(destination.is_symlink())
            self.assertEqual(destination.read_bytes(), b"new DLL")
            self.assertEqual(original.read_bytes(), b"original DLL")


if __name__ == "__main__":
    unittest.main()
