"""Tkinter based configuration utility for the AHG LIS Project."""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import List, Optional

from .config import AHGLISConfig, load_config, save_config
from .dependencies import DependencyError, ensure_runtime_dependencies


def _load_serial_port_scanner():
    try:
        from serial.tools import list_ports  # type: ignore[import-not-found]

        return list_ports
    except ModuleNotFoundError:  # pragma: no cover - handled at runtime
        return None


list_ports = _load_serial_port_scanner()

WINDOW_TITLE = "AHG LIS Project"
SERVICE_SCRIPT = Path(__file__).resolve().parent / "service.py"


class AHGLISApp(tk.Tk):
    """Main application window for the AHG LIS Project GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.resizable(False, False)

        installed: Optional[List[str]] = None
        self.withdraw()
        try:
            installed = ensure_runtime_dependencies()
        except DependencyError as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))
            self.destroy()
            raise SystemExit(1) from exc
        finally:
            self.deiconify()

        if installed:
            messagebox.showinfo(
                WINDOW_TITLE,
                "The following packages were installed automatically: " + ", ".join(installed),
            )

        global list_ports
        list_ports = _load_serial_port_scanner()

        self.configuration = load_config()

        self.serial_var = tk.StringVar(value=self.configuration.serial_port)
        self.baud_var = tk.StringVar(value=str(self.configuration.baudrate))
        self.output_var = tk.StringVar(value=self.configuration.output_folder)
        self.log_var = tk.StringVar(value=self.configuration.log_file)

        self._build_ui()
        self._populate_serial_ports()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 5}
        frame = ttk.Frame(self, padding=10)
        frame.grid(column=0, row=0, sticky="nsew")

        ttk.Label(frame, text="Serial COM Port:").grid(column=0, row=0, sticky="w", **padding)
        self.serial_combo = ttk.Combobox(frame, textvariable=self.serial_var, width=30)
        self.serial_combo.grid(column=1, row=0, sticky="we", **padding)
        ttk.Button(frame, text="Refresh", command=self._populate_serial_ports).grid(column=2, row=0, **padding)

        ttk.Label(frame, text="Baud Rate:").grid(column=0, row=1, sticky="w", **padding)
        self.baud_combo = ttk.Combobox(frame, textvariable=self.baud_var, width=30, values=_default_baud_rates())
        self.baud_combo.grid(column=1, row=1, sticky="we", **padding)
        ttk.Button(frame, text="Custom", command=self._prompt_baud_rate).grid(column=2, row=1, **padding)

        ttk.Label(frame, text="Output Folder:").grid(column=0, row=2, sticky="w", **padding)
        ttk.Entry(frame, textvariable=self.output_var, width=32).grid(column=1, row=2, sticky="we", **padding)
        ttk.Button(frame, text="Browse", command=self._select_output_folder).grid(column=2, row=2, **padding)

        ttk.Label(frame, text="Log File:").grid(column=0, row=3, sticky="w", **padding)
        ttk.Entry(frame, textvariable=self.log_var, width=32).grid(column=1, row=3, sticky="we", **padding)
        ttk.Button(frame, text="Choose", command=self._select_log_file).grid(column=2, row=3, **padding)

        button_frame = ttk.Frame(frame)
        button_frame.grid(column=0, row=4, columnspan=3, pady=15)

        ttk.Button(button_frame, text="Install Service", command=self._install_service).grid(column=0, row=0, padx=5)
        ttk.Button(button_frame, text="Start Service", command=lambda: self._run_service_command("start")).grid(column=1, row=0, padx=5)
        ttk.Button(button_frame, text="Stop Service", command=lambda: self._run_service_command("stop")).grid(column=2, row=0, padx=5)
        ttk.Button(button_frame, text="Uninstall Service", command=lambda: self._run_service_command("remove")).grid(column=3, row=0, padx=5)

        ttk.Label(frame, text="Run this tool with administrator privileges to manage the service.", wraplength=420, foreground="#555").grid(column=0, row=5, columnspan=3, **padding)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _select_output_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder", initialdir=self.output_var.get() or None)
        if folder:
            self.output_var.set(folder)

    def _select_log_file(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Select log file", defaultextension=".log", initialfile=Path(self.log_var.get()).name
        )
        if file_path:
            self.log_var.set(file_path)

    def _prompt_baud_rate(self) -> None:
        current = self.baud_var.get() or "9600"
        result = simpledialog.askstring(WINDOW_TITLE, "Enter custom baud rate:", initialvalue=current, parent=self)
        if result:
            self.baud_var.set(result.strip())

    def _populate_serial_ports(self) -> None:
        ports = self._detect_serial_ports()
        self.serial_combo["values"] = ports
        if ports and self.serial_var.get() not in ports:
            self.serial_var.set(ports[0])

    def _detect_serial_ports(self) -> List[str]:
        if list_ports is None:
            return [self.serial_var.get()] if self.serial_var.get() else []
        ports = [port.device for port in list_ports.comports()]
        return ports or ([self.serial_var.get()] if self.serial_var.get() else [])

    def _install_service(self) -> None:
        try:
            config = self._build_config()
        except ValueError as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))
            return
        save_config(config)
        try:
            self._run_subprocess("install", "--startup", "auto")
            messagebox.showinfo(WINDOW_TITLE, "Service installed successfully.")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(WINDOW_TITLE, f"Unable to install service.\n{exc}")
        except FileNotFoundError:
            messagebox.showerror(WINDOW_TITLE, "Python executable not found. Ensure Python is correctly installed.")

    def _run_service_command(self, command: str) -> None:
        try:
            self._run_subprocess(command)
            messagebox.showinfo(WINDOW_TITLE, f"Service command '{command}' executed successfully.")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(WINDOW_TITLE, f"Command '{command}' failed.\n{exc}")
        except FileNotFoundError:
            messagebox.showerror(WINDOW_TITLE, "Python executable not found. Ensure Python is correctly installed.")

    def _run_subprocess(self, *args: str) -> None:
        command = [sys.executable, str(SERVICE_SCRIPT)] + list(args)
        subprocess.check_call(command)

    def _build_config(self) -> AHGLISConfig:
        try:
            baudrate = int(self.baud_var.get().strip())
        except ValueError as exc:
            raise ValueError("Baud rate must be a number.") from exc
        if baudrate <= 0:
            raise ValueError("Baud rate must be greater than zero.")

        config = AHGLISConfig(
            serial_port=self.serial_var.get().strip() or "COM1",
            baudrate=baudrate,
            output_folder=self.output_var.get().strip() or str(Path.home()),
            log_file=self.log_var.get().strip() or str(Path.home() / "ahg_lis.log"),
        )
        config.ensure_directories()
        return config


def _default_baud_rates() -> tuple[str, ...]:
    """Common baud rates for serial medical devices."""

    return (
        "9600",
        "19200",
        "38400",
        "57600",
        "115200",
    )


def main() -> None:
    try:
        app = AHGLISApp()
    except SystemExit:
        return
    app.mainloop()


if __name__ == "__main__":
    main()
