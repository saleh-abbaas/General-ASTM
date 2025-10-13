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

> **Tip:** When the GUI starts it will automatically install these packages if they
> are missing by calling `python -m pip install ...`. Any installation errors are
> displayed in full so you can see the exact pip output without digging through
> log files. You can still install them manually with `pip install pyserial pywin32`
> if you prefer to control the process yourself.

#### Using the GUI
1. Launch the configuration tool:
   ```
   python -m ahg_lis_project
   ```
2. Select the COM port connected to the analyser. Use **Refresh** to rescan ports.
3. Pick the baud rate reported by the medical device (use **Custom** for uncommon values).
4. Choose the folder where ASTM payloads should be saved. Each transaction will be persisted as a timestamped `.txt` file.
5. Choose the log file path. The GUI will create the folder if it does not exist.
6. Click **Install Service** to store the configuration and register the Windows service (run the tool as Administrator).
7. Use **Start Service**, **Stop Service**, or **Uninstall Service** to control the background service.

#### Building a distributable GUI + service
If you want to ship the AHG LIS Project as a standalone executable for your lab
computers you can bundle the GUI together with the service helper by using
[PyInstaller](https://pyinstaller.org/). Install PyInstaller and build the
executable from the repository root:

```
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "AHG_LIS_GUI" --add-data "ahg_lis_project;ahg_lis_project" ahg_lis_project/__main__.py
```

The generated files will be located under `dist/AHG_LIS_GUI`. The folder
contains the `AHG_LIS_GUI.exe` launcher plus all Python runtime files. Distribute
the whole folder to the destination machine, then run `AHG_LIS_GUI.exe` as an
administrator to configure and install the Windows service. The installed
service uses the same configuration folder as when running the GUI with the
standard Python interpreter.

> **Note:** If you build the bundle from Linux or macOS replace the semicolon in
> the `--add-data` flag with a colon: `--add-data "ahg_lis_project:ahg_lis_project"`.

#### Running the service manually
The Windows service entry point lives in `ahg_lis_project/service.py`. It can be controlled from the command line as well:

```
python ahg_lis_project/service.py install --startup auto
python ahg_lis_project/service.py start
python ahg_lis_project/service.py stop
python ahg_lis_project/service.py remove
```

The service uses the configuration stored under `%PROGRAMDATA%\AHG_LIS_Project\config.json`.

### Legacy scripts
The original `astm_general.py` script is still included for reference. It provides the barebones ASTM listener used on
Linux systems. The new AHG LIS Project tooling offers the same serial capture flow with a modernised configuration
experience on Windows.

### Contact
  * Dr Shaileshkumar Manubhai Patel
  * biochemistrygmcs@gmail.com
  * WhatsApp: 9664555812 (India)
	
