"""Utilities for bundling the AHG LIS Project with PyInstaller."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


class BuildError(RuntimeError):
    """Raised when the executable cannot be created."""


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ModuleNotFoundError as exc:  # pragma: no cover - requires missing dependency
        command = [sys.executable, "-m", "pip", "install", "pyinstaller"]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        if process.returncode != 0:
            raise BuildError(
                "Unable to install PyInstaller automatically.\n"
                f"Command: {' '.join(command)}\n"
                f"Exit code: {process.returncode}\n\n"
                f"Standard Output:\n{process.stdout.strip() or '<empty>'}\n\n"
                f"Standard Error:\n{process.stderr.strip() or '<empty>'}"
            ) from exc


def _pyinstaller_data_argument() -> str:
    package_root = Path(__file__).resolve().parent
    separator = ";" if os.name == "nt" else ":"
    return f"{package_root}{separator}ahg_lis_project"


def _run_pyinstaller(arguments: Iterable[str]) -> None:
    command = [sys.executable, "-m", "PyInstaller", *arguments]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise BuildError(
            "PyInstaller failed to create the executable. "
            f"Exit code: {result.returncode}. Review the console output above for details."
        )


def _find_python_runtime() -> Path:
    if sys.platform != "win32":  # pragma: no cover - executed only on Windows
        raise BuildError("Python DLL injection is only required on Windows builds.")

    major, minor = sys.version_info[:2]
    expected_name = f"python{major}{minor}.dll"
    candidates = [
        Path(sys.base_prefix) / expected_name,
        Path(sys.exec_prefix) / expected_name,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    search_root = Path(sys.base_prefix)
    for dll in search_root.rglob(f"python{major}{minor}*.dll"):
        return dll

    raise BuildError(
        f"Unable to locate the {expected_name} runtime in {search_root}. "
        "Install CPython from python.org and retry the build."
    )


def _copy_python_runtime(dist_dir: Path) -> None:
    if sys.platform != "win32":  # pragma: no cover - executed only on Windows
        return

    dll_path = _find_python_runtime()
    shutil.copy2(dll_path, dist_dir / dll_path.name)


def build_executable(*, dist_dir: Path | None = None, clean: bool = True) -> Path:
    """Bundle the GUI and service helper into a redistributable package."""

    _ensure_pyinstaller()

    name = "AHG_LIS_GUI"
    dist_dir = dist_dir or Path("dist") / name
    dist_dir = Path(dist_dir)
    work_dir = Path("build") / f"{name}_internal"

    if clean:
        shutil.rmtree(dist_dir, ignore_errors=True)
        shutil.rmtree(work_dir, ignore_errors=True)

    hidden_imports = [
        "pystray._win32",
        "serial.tools.list_ports",
        "serial.tools.list_ports_windows",
        "serial.tools.list_ports_common",
        "serial.tools.list_ports_posix",
    ]

    arguments = [
        "--noconfirm",
        "--windowed",
        "--name",
        name,
        "--distpath",
        str(dist_dir.parent),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(work_dir),
        "--add-data",
        _pyinstaller_data_argument(),
        str(Path(__file__).resolve().parent / "__main__.py"),
    ]

    for module in hidden_imports:
        arguments.extend(["--hidden-import", module])
    if clean:
        arguments.insert(0, "--clean")

    _run_pyinstaller(arguments)

    final_dir = dist_dir
    if not final_dir.exists():
        final_dir = dist_dir.parent / name

    if not final_dir.exists():
        raise BuildError("PyInstaller finished without creating the expected dist directory.")

    _copy_python_runtime(final_dir)

    return final_dir

