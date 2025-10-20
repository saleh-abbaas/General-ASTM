"""Runtime dependency management for the AHG LIS Project."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, List, Sequence


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


def _install_packages(packages: Iterable[str]) -> None:
    command = [sys.executable, "-m", "pip", "install", *packages]
    subprocess.check_call(command)


def ensure_runtime_dependencies() -> List[str]:
    """Install missing dependencies using pip if they are not available.

    Returns a list with the names of packages that were installed.
    """

    dependencies = _required_dependencies()
    missing = _missing_dependencies(dependencies)
    if not missing:
        return []

    try:
        _install_packages([dependency.package for dependency in missing])
    except subprocess.CalledProcessError as exc:  # pragma: no cover - pip failure handled at runtime
        raise DependencyError(
            "Unable to install required Python packages automatically. "
            "Please run 'pip install pyserial pywin32' manually and try again."
        ) from exc

    remaining = _missing_dependencies(dependencies)
    if remaining:
        raise DependencyError(
            "Some dependencies are still missing after installation. "
            "Please install them manually and restart the application."
        )

    return [dependency.package for dependency in missing]
