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

### AHG LIS Project (Windows, C#)
The Python utilities remain available for reference, but the recommended Windows
deployment is now a C# solution located under [`csharp/`](csharp/). The
reimplementation introduces a strongly typed core library, a Windows service
host, and a graphical administration tool that always runs with elevated
privileges.

#### Solution layout
* **AHGLIS.Core** – shared domain models, configuration persistence, logging, and
  the serial listener implementation that translates ASTM payloads into text
  files for each analyser.
* **AHGLIS.Service** – a Windows Service (Worker Service) that watches the
  configuration file, starts a listener per device profile, and exposes command
  line helpers for installing, removing, starting, stopping, or checking the
  service status.
* **AHGLIS.Gui** – a Windows Forms application with a tray icon. It lets
  administrators pick COM ports, baud rates, output folders, log directories,
  and service actions while persisting device profiles.

All executables request administrator privileges through their application
manifest. Run every command below from an elevated PowerShell or Command Prompt.

#### Building (Visual Studio or .NET SDK)
1. Install the .NET 8.0 SDK and the “.NET desktop development” workload for
   Visual Studio 2022 (or newer). The service targets `net8.0-windows` so build
   machines must run Windows 10 or later.
2. Open `csharp/AHGLISProject.sln` in Visual Studio **as Administrator**, or run
   the following commands from an elevated terminal:
   ```powershell
   cd csharp
   dotnet restore
   dotnet build -c Release
   ```
3. Publish the GUI and service (still elevated) so you can deploy them to the
   analyser workstation:
   ```powershell
   dotnet publish src/AHGLIS.Gui/AHGLIS.Gui.csproj -c Release -r win-x64 -p:PublishSingleFile=false -o publish/gui
   dotnet publish src/AHGLIS.Service/AHGLIS.Service.csproj -c Release -r win-x64 -p:PublishSingleFile=false -o publish/service
   ```
4. Copy the contents of `publish/gui` and `publish/service` to the target
   machine, ensuring that `AHGLIS.Gui.exe` and `AHGLIS.Service.exe` live in the
   same folder (the GUI launches the service executable when you ask it to
   install, start, or stop the Windows service).

#### Configuring analysers with the GUI
1. Run `AHGLIS.Gui.exe` **as Administrator**. The manifest enforces elevation,
   but starting the process from an elevated shell ensures the tray icon can
   control the service.
2. Use **Device name**, **Serial port**, **Baud rate**, **Output folder**, and
   **Log folder** to describe the analyser. ASTM messages are persisted as
   timestamped `.txt` files inside the output folder, prefixed with the device
   name so multiple analysers can share a destination directory.
3. Press **Save device**. Settings are written to
   `%PROGRAMDATA%\AHG LIS Project\ahg-lis.settings.json`. Each device receives its
   own log file as well as service-level diagnostics inside the configured log
   directory.
4. Use **Install** to register the Windows service. The GUI executes
   `AHGLIS.Service.exe install`, which creates a service named
   “AHG LIS Device Listener” configured for automatic start when Windows boots.
5. Use **Start**, **Stop**, **Uninstall**, and **Refresh status** to control the
   service. A tray icon remains in the notification area so you can minimise the
   window without losing visibility into the service state.

#### Service command-line reference
`AHGLIS.Service.exe` exposes the following administrative verbs (run them from an
elevated shell next to the executable):

```powershell
AHGLIS.Service.exe install    # register the Windows service and set it to start automatically
AHGLIS.Service.exe uninstall  # remove the service after stopping it
AHGLIS.Service.exe start      # start the service immediately
AHGLIS.Service.exe stop       # stop the service gracefully
AHGLIS.Service.exe status     # print the current ServiceControllerStatus
```

When launched without arguments, the executable enters service mode (the GUI
registers it with the `run` verb). Configuration changes are detected at runtime
so listeners restart automatically when you edit device profiles in the GUI.

### Legacy scripts
The original `astm_general.py` script is still included for reference. It provides the barebones ASTM listener used on
Linux systems. The new AHG LIS Project tooling offers the same serial capture flow with a modernised configuration
experience on Windows.

### Contact
  * Dr Shaileshkumar Manubhai Patel
  * biochemistrygmcs@gmail.com
  * WhatsApp: 9664555812 (India)
	
