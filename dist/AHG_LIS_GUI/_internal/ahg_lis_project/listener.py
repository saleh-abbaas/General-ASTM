"""Core ASTM listener used by both the GUI and the Windows service."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import AHGLISConfig

try:
    import serial  # type: ignore[import-not-found]
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime on Windows
    raise RuntimeError(
        "pyserial is required to communicate with the medical device. "
        "Install it with 'pip install pyserial'."
    ) from exc

LOGGER = logging.getLogger("ahg_lis_project")


class ASTMListener:
    """Serial ASTM listener that mirrors the legacy script behaviour."""

    ENQ = b"\x05"
    ACK = b"\x06"
    EOT = b"\x04"
    LF = b"\x0a"

    def __init__(self, config: AHGLISConfig) -> None:
        self.config = config
        self._port: Optional[serial.Serial] = None
        self._stop_event = threading.Event()
        self._current_file: Optional[Path] = None
        self._file_handle: Optional[open] = None  # type: ignore[type-arg]
        self._buffer: list[str] = []

    def stop(self) -> None:
        """Request the listener to stop."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, stop_event: Optional[threading.Event] = None) -> None:
        """Start the listening loop."""
        LOGGER.info("Starting AHG LIS listener on %s", self.config.serial_port)
        external_stop = stop_event or threading.Event()
        while not (self._stop_event.is_set() or external_stop.is_set()):
            try:
                if not self._port:
                    self._port = self._open_port()
                self._poll_once()
            except serial.SerialException as exc:
                LOGGER.error("Serial error: %s", exc)
                self._close_port()
                if self._stop_event.wait(5) or (stop_event and stop_event.wait(5)):
                    break
            except Exception as exc:  # pragma: no cover - defensive logging
                LOGGER.exception("Unexpected error while reading from analyser: %s", exc)
                time.sleep(1)
        self._shutdown()
        LOGGER.info("Listener stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _open_port(self) -> serial.Serial:
        LOGGER.debug("Opening serial port %s", self.config.serial_port)
        port = serial.Serial(self.config.serial_port, baudrate=self.config.baudrate, timeout=1)
        LOGGER.info("Connected to %s", self.config.serial_port)
        return port

    def _close_port(self) -> None:
        if self._port and self._port.is_open:
            try:
                self._port.close()
            except serial.SerialException:  # pragma: no cover - best effort
                pass
        self._port = None

    def _poll_once(self) -> None:
        if not self._port:
            return
        byte = self._port.read(1)
        if not byte:
            return
        self._handle_byte(byte)

    def _handle_byte(self, byte: bytes) -> None:
        LOGGER.debug("Received byte 0x%s", byte.hex())
        if byte == self.ENQ:
            self._ack()
            self._prepare_file()
            self._buffer = [byte.decode("latin1")]
            LOGGER.info("<ENQ> received - session started")
            return

        if byte == self.LF:
            self._ack()
            self._buffer.append("\n")
            self._write_buffer()
            LOGGER.info("<LF> received - chunk written to %s", self._current_file)
            return

        if byte == self.EOT:
            self._buffer.append(byte.decode("latin1"))
            self._write_buffer()
            self._close_file()
            LOGGER.info("<EOT> received - session finished")
            return

        self._buffer.append(byte.decode("latin1"))

    def _ack(self) -> None:
        if self._port:
            self._port.write(self.ACK)

    def _prepare_file(self) -> None:
        if self._file_handle:
            self._close_file()
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
        self._current_file = Path(self.config.output_folder) / f"{timestamp}.txt"
        self._file_handle = self._current_file.open("w", encoding="utf-8")

    def _write_buffer(self) -> None:
        if self._file_handle and self._buffer:
            self._file_handle.write("".join(self._buffer))
            self._file_handle.flush()
            self._buffer = []

    def _close_file(self) -> None:
        if self._file_handle:
            try:
                self._file_handle.close()
            except OSError:  # pragma: no cover - best effort
                pass
        self._file_handle = None
        self._current_file = None
        self._buffer = []

    def _shutdown(self) -> None:
        self._close_file()
        self._close_port()
