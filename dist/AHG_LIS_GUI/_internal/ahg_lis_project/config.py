"""Configuration helpers for the AHG LIS Project."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict


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


@dataclass
class AHGLISConfig:
    """Data structure describing the listener configuration."""

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


def load_config(path: Path | None = None) -> AHGLISConfig:
    """Load configuration from disk or return defaults when missing."""
    config_path = path or default_config_path()
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        config = AHGLISConfig.from_dict(data)
    else:
        config = AHGLISConfig()
    config.ensure_directories()
    return config


def save_config(config: AHGLISConfig, path: Path | None = None) -> Path:
    """Persist the configuration on disk and return the file path."""
    config.ensure_directories()
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2)
    return config_path
