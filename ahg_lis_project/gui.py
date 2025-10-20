from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import List, Optional

if __package__ in (None, ""):
    package_root = str(Path(__file__).resolve().parent.parent)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)

from ahg_lis_project.config import (  # noqa: E402 - ensure import after sys.path tweak
    AHGLISConfig,
    available_devices,
    config_path_for_device,
    display_name_for_device,
    load_config,
    save_config,
    service_name_for_device,
)
from ahg_lis_project.dependencies import DependencyError, ensure_runtime_dependencies

try:  # pragma: no cover - optional dependency used on Windows only
    import pystray
    from PIL import Image, ImageDraw
except ModuleNotFoundError:  # pragma: no cover - not available during tests
    pystray = None  # type: ignore[assignment]
    Image = ImageDraw = None  # type: ignore[assignment]


def _load_serial_port_scanner():
    try:
        from serial.tools import list_ports  # type: ignore[import-not-found]

        return list_ports
    except ModuleNotFoundError:  # pragma: no cover - handled at runtime
        return None


def _default_baud_rates() -> tuple[str, ...]:
    """Common baud rates for serial medical devices."""

    return (
        "9600",
        "19200",
        "38400",
        "57600",
        "115200",
    )


list_ports = _load_serial_port_scanner()

WINDOW_TITLE = "AHG LIS Project"
SERVICE_SCRIPT = Path(__file__).resolve().parent / "service.py"
STATUS_POLL_INTERVAL_MS = 5000


class ServiceTrayIcon:
    """Optional Windows system tray icon reflecting the service status."""

    def __init__(self, app: "AHGLISApp") -> None:
        self.app = app
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._state: Optional[bool] = None

    def start(self) -> None:
        if os.name != "nt" or pystray is None or Image is None or ImageDraw is None:
            return
        if self._icon:
            return
        image = self._create_image(False)
        self._icon = pystray.Icon("ahg_lis_project", image, WINDOW_TITLE)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def update(self, running: Optional[bool]) -> None:
        if not self._icon:
            return
        state = bool(running)
        if self._state == state:
            return
        self._state = state
        self._icon.icon = self._create_image(state)

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            finally:
                self._icon = None
                self._thread = None
                self._state = None

    def _create_image(self, running: bool):
        if Image is None or ImageDraw is None:  # pragma: no cover - defensive
            raise RuntimeError("Pillow is required to create tray icons")
        size = (64, 64)
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        colour = (76, 175, 80) if running else (244, 67, 54)
        draw.ellipse((16, 16, 48, 48), fill=colour)
        return image


class AHGLISApp(tk.Tk):
    """Main application window for the AHG LIS Project GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

        device_names = available_devices()
        initial_device = device_names[0] if device_names else None
        self.configuration = load_config(device_name=initial_device)

        self.tray_icon = ServiceTrayIcon(self)
        self.device_var = tk.StringVar(value=self.configuration.device_name)
        self.serial_var = tk.StringVar(value=self.configuration.serial_port)
        self.baud_var = tk.StringVar(value=str(self.configuration.baudrate))
        self.output_var = tk.StringVar(value=self.configuration.output_folder)
        self.log_var = tk.StringVar(value=self.configuration.log_file)

        self._build_ui(device_names)
        self._populate_serial_ports()
        self.tray_icon.start()
        self.after(1000, self._schedule_tray_refresh)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self, known_devices: List[str]) -> None:
        padding = {"padx": 10, "pady": 5}
        frame = ttk.Frame(self, padding=10)
        frame.grid(column=0, row=0, sticky="nsew")

        ttk.Label(frame, text="Device Name:").grid(column=0, row=0, sticky="w", **padding)
        self.device_combo = ttk.Combobox(frame, textvariable=self.device_var, width=30, values=known_devices)
        self.device_combo.grid(column=1, row=0, sticky="we", **padding)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_selected)
        ttk.Button(frame, text="Load", command=self._load_device_profile).grid(column=2, row=0, **padding)

        ttk.Label(frame, text="Serial COM Port:").grid(column=0, row=1, sticky="w", **padding)
        self.serial_combo = ttk.Combobox(frame, textvariable=self.serial_var, width=30)
        self.serial_combo.grid(column=1, row=1, sticky="we", **padding)
        ttk.Button(frame, text="Refresh", command=self._populate_serial_ports).grid(column=2, row=1, **padding)

        ttk.Label(frame, text="Baud Rate:").grid(column=0, row=2, sticky="w", **padding)
        self.baud_combo = ttk.Combobox(frame, textvariable=self.baud_var, width=30, values=_default_baud_rates())
        self.baud_combo.grid(column=1, row=2, sticky="we", **padding)
        ttk.Button(frame, text="Custom", command=self._prompt_baud_rate).grid(column=2, row=2, **padding)

        ttk.Label(frame, text="Output Folder:").grid(column=0, row=3, sticky="w", **padding)
        ttk.Entry(frame, textvariable=self.output_var, width=32).grid(column=1, row=3, sticky="we", **padding)
        ttk.Button(frame, text="Browse", command=self._select_output_folder).grid(column=2, row=3, **padding)

        ttk.Label(frame, text="Log File:").grid(column=0, row=4, sticky="w", **padding)
        ttk.Entry(frame, textvariable=self.log_var, width=32).grid(column=1, row=4, sticky="we", **padding)
        ttk.Button(frame, text="Choose", command=self._select_log_file).grid(column=2, row=4, **padding)

        button_frame = ttk.Frame(frame)
        button_frame.grid(column=0, row=5, columnspan=3, pady=15)

        ttk.Button(button_frame, text="Install Service", command=self._install_service).grid(column=0, row=0, padx=5)
        ttk.Button(button_frame, text="Start Service", command=lambda: self._run_service_command("start")).grid(
            column=1, row=0, padx=5
        )
        ttk.Button(button_frame, text="Stop Service", command=lambda: self._run_service_command("stop")).grid(
            column=2, row=0, padx=5
        )
        ttk.Button(button_frame, text="Uninstall Service", command=lambda: self._run_service_command("remove")).grid(
            column=3, row=0, padx=5
        )

        ttk.Label(
            frame,
            text="Run this tool with administrator privileges to manage the service.",
            wraplength=420,
            foreground="#555",
        ).grid(column=0, row=6, columnspan=3, **padding)

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

    def _on_device_selected(self, _event: object) -> None:
        self._load_device_profile()

    def _install_service(self) -> None:
        try:
            config = self._build_config()
        except ValueError as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))
            return
        service_name, display_name, config_path = self._service_identifiers(config.device_name)
        save_config(config, path=config_path)
        try:
            self._run_subprocess(
                "install",
                "--device-name",
                config.device_name,
                "--config",
                str(config_path),
                "--service-name",
                service_name,
                "--display-name",
                display_name,
                "--startup",
                "auto",
            )
            self.configuration = config
            self._update_device_list()
            self._refresh_tray_icon()
            messagebox.showinfo(WINDOW_TITLE, "Service installed successfully.")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(WINDOW_TITLE, f"Unable to install service.\n{exc}")
        except FileNotFoundError:
            messagebox.showerror(WINDOW_TITLE, "Python executable not found. Ensure Python is correctly installed.")

    def _run_service_command(self, command: str) -> None:
        try:
            service_name, _, _ = self._service_identifiers()
            self._run_subprocess(command, "--service-name", service_name)
            self._refresh_tray_icon()
            messagebox.showinfo(WINDOW_TITLE, f"Service command '{command}' executed successfully.")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(WINDOW_TITLE, f"Command '{command}' failed.\n{exc}")
        except FileNotFoundError:
            messagebox.showerror(WINDOW_TITLE, "Python executable not found. Ensure Python is correctly installed.")

    def _run_subprocess(self, *args: str) -> None:
        command = [sys.executable, str(SERVICE_SCRIPT)] + [arg for arg in args if arg]
        subprocess.check_call(command)

    def _build_config(self) -> AHGLISConfig:
        try:
            baudrate = int(self.baud_var.get().strip())
        except ValueError as exc:
            raise ValueError("Baud rate must be a number.") from exc
        if baudrate <= 0:
            raise ValueError("Baud rate must be greater than zero.")

        device_name = self.device_var.get().strip() or "Default Device"
        config = AHGLISConfig(
            device_name=device_name,
            serial_port=self.serial_var.get().strip() or "COM1",
            baudrate=baudrate,
            output_folder=self.output_var.get().strip() or str(Path.home()),
            log_file=self.log_var.get().strip() or str(Path.home() / "ahg_lis.log"),
        )
        config.ensure_directories()
        return config

    def _load_device_profile(self) -> None:
        name = self.device_var.get().strip()
        if not name:
            messagebox.showerror(WINDOW_TITLE, "Enter a device name before loading its configuration.")
            return
        self.configuration = load_config(device_name=name)
        self.device_var.set(self.configuration.device_name)
        self.serial_var.set(self.configuration.serial_port)
        self.baud_var.set(str(self.configuration.baudrate))
        self.output_var.set(self.configuration.output_folder)
        self.log_var.set(self.configuration.log_file)
        self._populate_serial_ports()
        self._refresh_tray_icon()

    def _service_identifiers(self, device_name: Optional[str] = None):
        target = (device_name or self.device_var.get()).strip() or "Default Device"
        return (
            service_name_for_device(target),
            display_name_for_device(target),
            config_path_for_device(target),
        )

    def _update_device_list(self) -> None:
        names = {name for name in available_devices() if name}
        current = self.device_var.get().strip()
        if current:
            names.add(current)
        self.device_combo["values"] = sorted(names)

    def _query_service_running(self) -> Optional[bool]:
        if os.name != "nt":  # pragma: no cover - Windows only
            return None
        try:
            import win32service  # type: ignore[import-not-found]
            import win32serviceutil  # type: ignore[import-not-found]
        except ModuleNotFoundError:  # pragma: no cover - optional dependency
            return None

        service_name, _, _ = self._service_identifiers()
        try:
            status = win32serviceutil.QueryServiceStatus(service_name)
        except Exception:
            return None
        return status[1] == win32service.SERVICE_RUNNING

    def _refresh_tray_icon(self) -> None:
        status = self._query_service_running()
        self.tray_icon.update(status)

    def _schedule_tray_refresh(self) -> None:
        self._refresh_tray_icon()
        self.after(STATUS_POLL_INTERVAL_MS, self._schedule_tray_refresh)

    def _on_close(self) -> None:
        self.tray_icon.stop()
        self.destroy()


def main() -> None:
    try:
        app = AHGLISApp()
    except SystemExit:
        return
    app.mainloop()


if __name__ == "__main__":
    main()
