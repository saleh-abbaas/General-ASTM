"""Runtime dependency management for the AHG LIS Project."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from dataclasses import dataclass
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
    return deps


def _missing_dependencies(dependencies: Iterable[Dependency]) -> List[Dependency]:
    missing: list[Dependency] = []
    for dependency in dependencies:
        try:
            importlib.import_module(dependency.module)
        except ModuleNotFoundError:
            missing.append(dependency)
    return missing


def _install_packages(packages: Iterable[str]) -> Tuple[str, str]:
    command = [sys.executable, "-m", "pip", "install", *packages]
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
