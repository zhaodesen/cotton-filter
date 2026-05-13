"""Build the Windows executable with explicit runtime DLLs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


RUNTIME_DLLS = (
    f"python{sys.version_info.major}{sys.version_info.minor}.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
)


def candidate_dirs() -> list[Path]:
    dirs = [
        Path(sys.executable).resolve().parent,
        Path(sys.base_prefix).resolve(),
        Path(sys.exec_prefix).resolve(),
        Path(sys.base_prefix).resolve() / "DLLs",
        Path(sys.exec_prefix).resolve() / "DLLs",
    ]
    unique_dirs: list[Path] = []
    for folder in dirs:
        if folder not in unique_dirs:
            unique_dirs.append(folder)
    return unique_dirs


def find_runtime_dlls() -> list[Path]:
    found: list[Path] = []
    for name in RUNTIME_DLLS:
        for folder in candidate_dirs():
            path = folder / name
            if path.is_file():
                found.append(path)
                break
        else:
            print(f"Runtime DLL not found, skipping: {name}")
    return found


def main() -> int:
    command = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name",
        "cotton-filter",
        "--clean",
    ]
    for dll_path in find_runtime_dlls():
        command.extend(["--add-binary", f"{dll_path}{os.pathsep}."])
        print(f"Bundling runtime DLL: {dll_path}")
    command.append("main.py")

    subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
