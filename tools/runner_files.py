"""Replace runner files without writing through copied aliases."""

import os
from pathlib import Path
import shutil


def checked_destination(root, destination):
    root = root.resolve()
    destination = Path(os.path.abspath(destination))
    if (not destination.is_relative_to(root) or destination == root or
            not destination.parent.resolve().is_relative_to(root)):
        raise ValueError(f"Runner destination escapes the assembly directory: {destination}")
    return destination


def prepare_destination(root, destination):
    destination = checked_destination(root, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    return destination


def replace_file(source, destination, root):
    destination = prepare_destination(root, destination)
    shutil.copy2(source, destination)
