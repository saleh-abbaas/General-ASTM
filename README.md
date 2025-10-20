### About
If you wish **unidirectional communication** with medical equipment using **ASTM protocol** this might be useful

It handles both RS232 (COM Port, ttyS0 etc ) and TCP connections via LAN/wifi

It is tested with

        Erba biochemistry analysers (XL-640)
        Note: Erba XL-640 with Windows-XP have problem with resources. Use Windows 7 or above
        ElitePro Coagulation analyser
        It must work with any analyser following ASTM protocol

### prerequisites
  * Linux ( Tested in debian, but must work with any)
  * Python3 +
  * Some python 3 libraries like sys,logging, signal time,datetime,socket,serial
  * Most libraries are deault installation with python in Linux
  * See log file for missing libraries

### AHG LIS Project (Windows)
The repository now includes a Windows-focused workflow named **AHG LIS Project**. A graphical interface helps with
configuring serial communication, selecting the destination folder for ASTM text files, choosing the log file location
and installing the service that runs the listener in the background.

#### Requirements
* Windows 10 or later
* Python 3.9+
* [pyserial](https://pypi.org/project/pyserial/) for serial communication
* [pywin32](https://pypi.org/project/pywin32/) to manage the Windows service
* [pystray](https://pypi.org/project/pystray/) and [Pillow](https://pypi.org/project/Pillow/) to display the optional
  system tray status icon

> **Tip:** When the GUI starts it will automatically install these packages if they
> are missing. It now searches for a working Python interpreter on the machine and
> falls back to the `pip` command if necessary, so environments where `python` is
> not on `PATH` are still handled. Full pip output is shown when an installation
> fails so you can diagnose configuration issues quickly. You can still install
> them manually with `pip install pyserial pywin32 pystray Pillow` if you prefer
> to control the process yourself.

#### Using the GUI
1. Launch the configuration tool:
   ```
   python -m ahg_lis_project
   ```
2. Give the configuration a **Device Name**. Every device uses its own profile and Windows service instance so multiple
   analysers can be captured concurrently.
3. Select the COM port connected to the analyser. Use **Refresh** to rescan ports.
4. Pick the baud rate reported by the medical device (use **Custom** for uncommon values).
5. Choose the folder where ASTM payloads should be saved. Each transaction will be persisted as a timestamped `.txt`
   file that includes the device identifier (for example `2024-06-30-10-55-20-000000_device-a.txt`).
6. Choose the log file path. The GUI will create the folder if it does not exist.
7. Click **Install Service** to store the configuration and register the Windows service (run the tool as Administrator).
   The service is configured to start automatically when Windows boots and a tray icon (green when running, red when
   stopped) reflects its status when the required packages are available.
8. Use **Start Service**, **Stop Service**, or **Uninstall Service** to control the background service. Existing device
   profiles can be reloaded from the **Device Name** drop-down.

#### Building a distributable GUI + service
If you want to ship the AHG LIS Project as a standalone executable for your lab
computers you can bundle the GUI together with the service helper using the
packaged builder. Install the runtime dependencies in the build environment
first (`pip install pyserial pywin32 pystray Pillow`) so PyInstaller can embed
them. The helper automatically installs PyInstaller if necessary, invokes it
with the correct options (including the serial and tray-icon backends required
at runtime), and copies the CPython runtime DLL into the output so the executable
can start without additional manual steps:

```
python -m ahg_lis_project build
```

By default the distributable is written to `dist/AHG_LIS_GUI`. The folder
contains the `AHG_LIS_GUI.exe` launcher together with every file required to run
on a clean Windows machine (all Python dependencies are bundled, so no pip
installation is necessary on the target PC). Copy the **entire** folder to the destination
computer (do not run the executables from the temporary `build/` directory),
then execute `AHG_LIS_GUI.exe` as an administrator to configure and install the
Windows service. The installed service uses the same configuration folder as
when running the GUI with the standard Python interpreter.

Use `python -m ahg_lis_project build --dist-dir C:\\AHG\\Bundles` to change the
output location or `python -m ahg_lis_project build --no-clean` to reuse existing
build artefacts between invocations.

#### Running the service manually
The Windows service entry point lives in `ahg_lis_project/service.py`. It can be controlled from the command line as well:

```
python ahg_lis_project/service.py install --device-name "Device A" --config "C:\\AHG\\device-a.json"
python ahg_lis_project/service.py start --service-name AHGLISProject_device-a
python ahg_lis_project/service.py status --service-name AHGLISProject_device-a
python ahg_lis_project/service.py stop --service-name AHGLISProject_device-a
python ahg_lis_project/service.py remove --service-name AHGLISProject_device-a
```

Configuration files are stored per device under `%PROGRAMDATA%\AHG_LIS_Project\devices\`. Installing a service for the
same device name again updates the configuration and leaves other devices untouched.

### Legacy scripts
The original `astm_general.py` script is still included for reference. It provides the barebones ASTM listener used on
Linux systems. The new AHG LIS Project tooling offers the same serial capture flow with a modernised configuration
experience on Windows.

### Contact
  * Dr Shaileshkumar Manubhai Patel
  * biochemistrygmcs@gmail.com
  * WhatsApp: 9664555812 (India)
	
