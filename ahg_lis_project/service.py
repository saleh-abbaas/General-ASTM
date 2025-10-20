"""Windows service wrapper for the AHG LIS Project."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import win32event  # type: ignore[import-not-found]
import win32service  # type: ignore[import-not-found]
import win32serviceutil  # type: ignore[import-not-found]

if __package__ in (None, ""):
    package_root = str(Path(__file__).resolve().parent.parent)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)

from ahg_lis_project.config import (  # noqa: E402 - ensure import after sys.path tweak
    AHGLISConfig,
    config_path_for_device,
    display_name_for_device,
    load_config,
    save_config,
    service_name_for_device,
)
from ahg_lis_project.listener import ASTMListener, LOGGER

CONFIG_OPTION = "config_path"
DEVICE_OPTION = "device_name"


@dataclass
class RuntimeOverrides:
    """Values provided on the command line when the service starts."""

    service_name: Optional[str] = None
    device_name: Optional[str] = None
    config_path: Optional[str] = None


class AHGLISWindowsService(win32serviceutil.ServiceFramework):
    """Windows service entry point that runs one ASTM listener."""

    _svc_name_ = "AHGLISProjectService"
    _svc_display_name_ = "AHG LIS Project Service"
    _svc_description_ = "Captures ASTM frames from medical devices and stores them as text files."

    CONFIG_PATH: Optional[str] = None
    DEVICE_NAME: Optional[str] = None

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._listener: Optional[ASTMListener] = None

    # ------------------------------------------------------------------
    # Service lifecycle
    # ------------------------------------------------------------------
    def SvcStop(self) -> None:  # noqa: N802 - signature required by pywin32
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self._stop_event.set()
        if self._listener:
            self._listener.stop()
        if self._thread:
            self._thread.join(timeout=10)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self) -> None:  # noqa: N802 - signature required by pywin32
        try:
            config = self._load_runtime_config()
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Unable to load AHG LIS configuration: %s", exc)
            raise

        configure_logging(config)
        LOGGER.info("AHG LIS Project service for %s initialising", config.device_name)

        self._listener = ASTMListener(config)
        self._thread = threading.Thread(target=self._listener.run, args=(self._stop_event,), daemon=True)
        self._thread.start()

        LOGGER.info("AHG LIS Project service for %s started", config.device_name)
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        LOGGER.info("AHG LIS Project service for %s stopped", config.device_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_runtime_config(self) -> AHGLISConfig:
        """Load configuration using runtime overrides or persisted metadata."""

        device_name = self.DEVICE_NAME
        config_path: Optional[Path] = None

        if self.CONFIG_PATH:
            config_path = Path(self.CONFIG_PATH).expanduser()
        else:
            # Fallback to registry stored values.
            try:
                option = win32serviceutil.GetServiceCustomOption(self._svc_name_, CONFIG_OPTION)
            except Exception:  # pragma: no cover - pywin32 specific exceptions on Windows
                option = None
            if option:
                config_path = Path(option).expanduser()

        if not device_name:
            try:
                option = win32serviceutil.GetServiceCustomOption(self._svc_name_, DEVICE_OPTION)
            except Exception:  # pragma: no cover - pywin32 specific exceptions on Windows
                option = None
            if option:
                device_name = option

        if device_name and not config_path:
            config_path = config_path_for_device(device_name)

        config = load_config(path=config_path, device_name=device_name)
        if device_name:
            config.device_name = device_name
        save_config(config, path=config_path)
        return config


# ----------------------------------------------------------------------
# Logging utilities
# ----------------------------------------------------------------------

def configure_logging(config: AHGLISConfig) -> None:
    """Configure logging for the Windows service context."""

    config.ensure_directories()
    log_path = Path(config.log_file).expanduser()
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    LOGGER.info("Logging initialised for %s. Writing to %s", config.device_name, log_path)


# ----------------------------------------------------------------------
# CLI helpers
# ----------------------------------------------------------------------

def _extract_runtime_overrides(argv: Iterable[str]) -> tuple[RuntimeOverrides, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--service-name")
    parser.add_argument("--device-name")
    parser.add_argument("--config")
    known, remaining = parser.parse_known_args(list(argv))
    overrides = RuntimeOverrides(
        service_name=known.service_name,
        device_name=known.device_name,
        config_path=known.config,
    )
    return overrides, remaining


def _apply_runtime_overrides(overrides: RuntimeOverrides) -> None:
    if overrides.service_name:
        AHGLISWindowsService._svc_name_ = overrides.service_name
        AHGLISWindowsService._svc_display_name_ = overrides.service_name
    if overrides.device_name:
        AHGLISWindowsService.DEVICE_NAME = overrides.device_name
    if overrides.config_path:
        AHGLISWindowsService.CONFIG_PATH = overrides.config_path


def _install_service(args: argparse.Namespace) -> None:
    device_name = args.device_name.strip()
    if not device_name:
        raise ValueError("Device name is required to install the service.")

    service_name = args.service_name or service_name_for_device(device_name)
    display_name = args.display_name or display_name_for_device(device_name)
    config_path = Path(args.config).expanduser()
    config = load_config(path=config_path if config_path.exists() else None, device_name=device_name)
    config.device_name = device_name
    save_config(config, path=config_path)

    exe_name = sys.executable
    script_path = Path(__file__).resolve()
    exe_args = (
        f'"{script_path}" --service-name "{service_name}" '
        f'--device-name "{device_name}" --config "{config_path}"'
    )

    start_type = win32service.SERVICE_AUTO_START if args.startup == "auto" else win32service.SERVICE_DEMAND_START

    win32serviceutil.InstallService(
        pythonClassString="ahg_lis_project.service.AHGLISWindowsService",
        serviceName=service_name,
        displayName=display_name,
        description=AHGLISWindowsService._svc_description_,
        exeName=exe_name,
        exeArgs=exe_args,
        startType=start_type,
    )
    win32serviceutil.SetServiceCustomOption(service_name, CONFIG_OPTION, str(config_path))
    win32serviceutil.SetServiceCustomOption(service_name, DEVICE_OPTION, device_name)

    if args.startup == "auto" and args.start_now:
        win32serviceutil.StartService(service_name)


def _start_service(args: argparse.Namespace) -> None:
    win32serviceutil.StartService(args.service_name)


def _stop_service(args: argparse.Namespace) -> None:
    try:
        win32serviceutil.StopService(args.service_name)
    except win32service.error as exc:  # type: ignore[attr-defined]
        if exc.winerror != win32service.ERROR_SERVICE_NOT_ACTIVE:  # type: ignore[attr-defined]
            raise


def _remove_service(args: argparse.Namespace) -> None:
    service_name = args.service_name
    try:
        win32serviceutil.StopService(service_name)
    except Exception:
        pass
    try:
        win32serviceutil.RemoveService(service_name)
    finally:
        try:
            win32serviceutil.SetServiceCustomOption(service_name, CONFIG_OPTION, "")
            win32serviceutil.SetServiceCustomOption(service_name, DEVICE_OPTION, "")
        except Exception:
            pass


def _status_service(args: argparse.Namespace) -> None:
    status = win32serviceutil.QueryServiceStatus(args.service_name)
    state = status[1]
    if state == win32service.SERVICE_RUNNING:
        print(f"{args.service_name}: running")
    elif state == win32service.SERVICE_STOPPED:
        print(f"{args.service_name}: stopped")
    else:
        print(f"{args.service_name}: state={state}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage AHG LIS Project Windows services.")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", help="Install a new service instance")
    install.add_argument("--device-name", required=True)
    install.add_argument("--config", required=True)
    install.add_argument("--service-name")
    install.add_argument("--display-name")
    install.add_argument("--startup", choices=["auto", "manual"], default="auto")
    install.add_argument("--start-now", action="store_true", help="Start the service immediately after installation")
    install.set_defaults(func=_install_service)

    start = sub.add_parser("start", help="Start an installed service")
    start.add_argument("--service-name", required=True)
    start.set_defaults(func=_start_service)

    stop = sub.add_parser("stop", help="Stop a running service")
    stop.add_argument("--service-name", required=True)
    stop.set_defaults(func=_stop_service)

    remove = sub.add_parser("remove", help="Remove an installed service")
    remove.add_argument("--service-name", required=True)
    remove.set_defaults(func=_remove_service)

    status = sub.add_parser("status", help="Show the Windows service status")
    status.add_argument("--service-name", required=True)
    status.set_defaults(func=_status_service)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    # When invoked by the Windows Service Control Manager the command line only
    # contains overrides. In that case we configure the service class and
    # hand over to ``HandleCommandLine`` to enter the service loop.
    if not argv or argv[0].startswith("--"):
        overrides, remaining = _extract_runtime_overrides(argv)
        _apply_runtime_overrides(overrides)
        sys.argv = [sys.argv[0], *remaining]
        win32serviceutil.HandleCommandLine(AHGLISWindowsService)
        return

    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
