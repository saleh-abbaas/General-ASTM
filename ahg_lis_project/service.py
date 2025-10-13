"""Windows service wrapper for the AHG LIS Project."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import win32event  # type: ignore[import-not-found]
import win32service  # type: ignore[import-not-found]
import win32serviceutil  # type: ignore[import-not-found]

if __package__ in (None, ""):
    import sys

    package_root = str(Path(__file__).resolve().parent.parent)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)

from ahg_lis_project.config import AHGLISConfig, load_config
from ahg_lis_project.listener import ASTMListener, LOGGER


class AHGLISWindowsService(win32serviceutil.ServiceFramework):
    """Windows service entry point that runs the ASTM listener."""

    _svc_name_ = "AHGLISProjectService"
    _svc_display_name_ = "AHG LIS Project Service"
    _svc_description_ = "Captures ASTM frames from medical devices and stores them as text files."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def SvcStop(self) -> None:  # noqa: N802 - signature required by pywin32
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self) -> None:  # noqa: N802 - signature required by pywin32
        config = load_config()
        configure_logging(config)
        listener = ASTMListener(config)

        self._thread = threading.Thread(target=listener.run, args=(self._stop_event,), daemon=True)
        self._thread.start()
        LOGGER.info("AHG LIS Project service started")

        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        LOGGER.info("AHG LIS Project service stopped")


def configure_logging(config: AHGLISConfig) -> None:
    """Configure logging for the Windows service context."""
    config.ensure_directories()
    log_path = Path(config.log_file).expanduser()
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    LOGGER.info("Logging initialised. Writing to %s", log_path)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(AHGLISWindowsService)
