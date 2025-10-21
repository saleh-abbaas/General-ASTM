"""Configuration helpers for the AHG LIS Project."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _default_base_dir() -> Path:
    """Return the directory used to store configuration and data."""
    if os.name == "nt":
        program_data = os.environ.get("PROGRAMDATA")
        if program_data:
            return Path(program_data) / "AHG_LIS_Project"
    return Path.home() / "AHG_LIS_Project"


def default_output_dir() -> Path:
    """Default directory where ASTM payload files are stored."""
    return _default_base_dir() / "data"


def default_log_file() -> Path:
    """Default path for the application log file."""
    return _default_base_dir() / "logs" / "ahg_lis.log"


def default_config_path() -> Path:
    """Default path of the persisted configuration file."""
    return _default_base_dir() / "config.json"


def _device_config_dir() -> Path:
    """Directory that stores device specific configuration files."""

    return _default_base_dir() / "devices"


def _slugify(value: str) -> str:
    """Create a filesystem friendly identifier from an arbitrary string."""

    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "device"


def available_devices() -> List[str]:
    """Return a sorted list with the names of configured devices."""

    directory = _device_config_dir()
    if not directory.exists():
        return []
    result = []
    for candidate in directory.glob("*.json"):
        if candidate.name == "default.json":
            continue
        with candidate.open("r", encoding="utf-8") as handle:
            try:
                payload = json.load(handle)
            except json.JSONDecodeError:
                continue
        name = payload.get("device_name")
        if isinstance(name, str) and name.strip():
            result.append(name.strip())
    return sorted({name for name in result})


def config_path_for_device(device_name: str) -> Path:
    """Return the configuration path for the specified device."""

    return _device_config_dir() / f"{_slugify(device_name)}.json"


def device_slug(device_name: str) -> str:
    """Expose the slugified identifier for reuse in other modules."""

    return _slugify(device_name)


def service_name_for_device(device_name: str) -> str:
    """Return a deterministic Windows service name for the device."""

    return f"AHGLISProject_{_slugify(device_name)}"


def display_name_for_device(device_name: str) -> str:
    """Return a user facing Windows service display name."""

    return f"AHG LIS Project ({device_name})"


@dataclass
class AHGLISConfig:
    """Data structure describing the listener configuration."""

    device_name: str = "Default Device"
    serial_port: str = "COM1"
    baudrate: int = 9600
    output_folder: str = str(default_output_dir())
    log_file: str = str(default_log_file())
    alarm_time: int = 10

    def ensure_directories(self) -> None:
        """Ensure folders for output data and log files exist."""
        output_path = Path(self.output_folder).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)
        log_path = Path(self.log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the configuration into a serialisable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AHGLISConfig":
        """Create configuration from dictionary data."""
        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {key: value for key, value in payload.items() if key in valid_keys}
        return cls(**filtered)


def load_config(path: Path | None = None, device_name: str | None = None) -> AHGLISConfig:
    """Load configuration for a specific device or return defaults."""

    config_path = path
    if device_name and not config_path:
        config_path = config_path_for_device(device_name)

    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        config = AHGLISConfig.from_dict(data)
    else:
        if not device_name:
            # Attempt to load the first available device configuration for backwards compatibility.
            devices = available_devices()
            if devices:
                return load_config(device_name=devices[0])
        config = AHGLISConfig(device_name=device_name or "Default Device")

    if device_name and not config.device_name:
        config.device_name = device_name
    config.ensure_directories()
    return config


def save_config(config: AHGLISConfig, path: Path | None = None) -> Path:
    """Persist the configuration on disk and return the file path."""

    target_path = path
    if config.device_name and not target_path:
        target_path = config_path_for_device(config.device_name)
    if not target_path:
        target_path = default_config_path()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    config.ensure_directories()
    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2)
    return target_path


def config_summary() -> List[Tuple[str, Path]]:
    """Return all known device configurations and their storage path."""

    summary: List[Tuple[str, Path]] = []
    for name in available_devices():
        summary.append((name, config_path_for_device(name)))
    default_path = default_config_path()
    if default_path.exists():
        summary.append(("Legacy configuration", default_path))
    return summary
