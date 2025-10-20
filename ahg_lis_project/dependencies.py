"""Runtime dependency management for the AHG LIS Project."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


class DependencyError(RuntimeError):
    """Raised when runtime dependencies cannot be satisfied automatically."""


@dataclass(frozen=True)
class Dependency:
    """Description of a package that needs to be available at runtime."""

    package: str
    module: str


def _required_dependencies() -> Sequence[Dependency]:
    deps: list[Dependency] = [Dependency("pyserial", "serial")]
    if os.name == "nt":
        deps.append(Dependency("pywin32", "win32serviceutil"))
        deps.append(Dependency("pystray", "pystray"))
        deps.append(Dependency("Pillow", "PIL"))
    return deps


def _missing_dependencies(dependencies: Iterable[Dependency]) -> List[Dependency]:
    missing: list[Dependency] = []
    for dependency in dependencies:
        try:
            importlib.import_module(dependency.module)
        except ModuleNotFoundError:
            missing.append(dependency)
    return missing


def _python_candidates() -> List[Path]:
    candidates: list[Path] = []
    base_executable = getattr(sys, "_base_executable", None)
    if base_executable:
        path = Path(base_executable)
        if path.exists() and path not in candidates:
            candidates.append(path)

    executable = Path(sys.executable)
    if executable.exists() and executable not in candidates:
        candidates.append(executable)

    for name in ("python", "python3", "py"):
        resolved = shutil.which(name)
        if resolved:
            path = Path(resolved)
            if path not in candidates:
                candidates.append(path)

    return candidates


def _pip_command(packages: Iterable[str]) -> List[str]:
    """Locate a Python interpreter capable of executing pip."""

    for candidate in _python_candidates():
        if getattr(sys, "frozen", False) and candidate == Path(sys.executable):
            # A frozen executable cannot run pip modules; skip and try the next candidate.
            continue

        base_command = [str(candidate), "-m", "pip"]
        probe = subprocess.run(
            base_command + ["--version"], capture_output=True, text=True, check=False
        )
        if probe.returncode == 0:
            return base_command + ["install", *packages]

    pip_exe = shutil.which("pip")
    if pip_exe:
        return [pip_exe, "install", *packages]

    raise DependencyError(
        "Unable to locate a Python interpreter with pip support. "
        "Install Python 3 with pip enabled and retry."
    )


def _install_packages(packages: Iterable[str]) -> Tuple[str, str]:
    if getattr(sys, "frozen", False):
        raise DependencyError(
            "This packaged build is missing required libraries ("
            + ", ".join(packages)
            + "). Rebuild the executable after installing them in the source environment."
        )

    command = _pip_command(list(packages))
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise DependencyError(
            "Unable to install required Python packages automatically.\n"
            f"Command: {' '.join(command)}\n"
            f"Exit code: {process.returncode}\n\n"
            f"Standard Output:\n{process.stdout.strip() or '<empty>'}\n\n"
            f"Standard Error:\n{process.stderr.strip() or '<empty>'}"
        )
    return process.stdout, process.stderr


def ensure_runtime_dependencies() -> List[str]:
    """Install missing dependencies using pip if they are not available.

    Returns a list with the names of packages that were installed.
    """

    dependencies = _required_dependencies()
    missing = _missing_dependencies(dependencies)
    if not missing:
        return []

    _install_packages([dependency.package for dependency in missing])

    remaining = _missing_dependencies(dependencies)
    if remaining:
        raise DependencyError(
            "Some dependencies are still missing after installation. "
            "Please install them manually and restart the application."
        )

    return [dependency.package for dependency in missing]
