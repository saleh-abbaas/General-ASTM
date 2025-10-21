using System.ComponentModel;
using System.IO.Ports;
using System.ServiceProcess;
using System.Text;
using System.Windows.Forms;
using AHGLIS.Core.Configuration;
using AHGLIS.Core.Logging;
using AHGLIS.Core.Models;

namespace AHGLIS.Gui;

/// <summary>
/// Provides the administrative console for configuring analyser connections and managing the service lifecycle.
/// </summary>
internal sealed class MainForm : Form
{
    private readonly ConfigurationStore _configurationStore;
    private readonly ServiceLogWriter _serviceLogWriter;
    private readonly ServiceManager _serviceManager = new();

    private AppConfiguration _configuration = new();
    private readonly BindingList<DeviceProfile> _devices = new();

    private readonly NotifyIcon _notifyIcon;
    private readonly ContextMenuStrip _trayMenu;

    private readonly ListBox _deviceList = new();
    private readonly TextBox _deviceName = new();
    private readonly ComboBox _ports = new();
    private readonly ComboBox _baudRates = new();
    private readonly TextBox _outputDirectory = new();
    private readonly TextBox _logDirectory = new();
    private readonly Label _serviceStatusLabel = new();
    private readonly Button _saveButton = new();
    private readonly Button _deleteButton = new();
    private readonly Button _installButton = new();
    private readonly Button _startButton = new();
    private readonly Button _stopButton = new();
    private readonly Button _uninstallButton = new();
    private readonly Button _refreshPortsButton = new();

    public MainForm(ConfigurationStore configurationStore, ServiceLogWriter serviceLogWriter)
    {
        _configurationStore = configurationStore;
        _serviceLogWriter = serviceLogWriter;

        Text = "AHG LIS Project";
        Width = 960;
        Height = 600;
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(920, 540);

        _trayMenu = BuildTrayMenu();
        _notifyIcon = new NotifyIcon
        {
            Icon = SystemIcons.Shield,
            Visible = true,
            Text = "AHG LIS Project",
            ContextMenuStrip = _trayMenu,
        };
        _notifyIcon.MouseDoubleClick += (_, _) => RestoreFromTray();

        InitializeComponent();
        LoadConfiguration();
        RefreshServiceStatus();

        Resize += HandleResize;
        FormClosing += HandleClosing;
    }

    private void InitializeComponent()
    {
        _deviceList.Dock = DockStyle.Fill;
        _deviceList.DataSource = _devices;
        _deviceList.DisplayMember = nameof(DeviceProfile.DeviceName);
        _deviceList.SelectedIndexChanged += (_, _) => DisplaySelectedDevice();

        var leftPanel = new Panel
        {
            Dock = DockStyle.Left,
            Width = 260,
            Padding = new Padding(10),
        };
        var leftLayout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 2,
        };
        var deviceListLabel = new Label
        {
            Text = "Configured devices",
            Dock = DockStyle.Fill,
            Font = new Font(Font, FontStyle.Bold),
            Height = 24,
        };
        leftLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        leftLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        leftLayout.Controls.Add(deviceListLabel, 0, 0);
        leftLayout.Controls.Add(_deviceList, 0, 1);
        leftPanel.Controls.Add(leftLayout);
        Controls.Add(leftPanel);

        var mainLayout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 0,
            Padding = new Padding(10),
        };
        mainLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 160));
        mainLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        mainLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 40));

        void AddRow(string labelText, Control field, Control? auxButton = null)
        {
            var rowIndex = mainLayout.RowCount;
            mainLayout.RowCount++;
            mainLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));

            var label = new Label
            {
                Text = labelText,
                Dock = DockStyle.Fill,
                TextAlign = ContentAlignment.MiddleLeft,
            };

            field.Dock = DockStyle.Fill;
            mainLayout.Controls.Add(label, 0, rowIndex);
            mainLayout.Controls.Add(field, 1, rowIndex);

            if (auxButton is not null)
            {
                auxButton.Dock = DockStyle.Fill;
                mainLayout.Controls.Add(auxButton, 2, rowIndex);
            }
        }

        _deviceName.PlaceholderText = "Device name";
        AddRow("Device name", _deviceName);

        _ports.DropDownStyle = ComboBoxStyle.DropDownList;
        _refreshPortsButton.Text = "↻";
        _refreshPortsButton.Click += (_, _) => PopulateSerialPorts();
        AddRow("Serial port", _ports, _refreshPortsButton);

        _baudRates.DropDownStyle = ComboBoxStyle.DropDown;
        _baudRates.Items.AddRange(new object[] { "9600", "19200", "38400", "57600", "115200" });
        _baudRates.Text = "9600";
        AddRow("Baud rate", _baudRates);

        _outputDirectory.ReadOnly = true;
        var browseOutput = new Button { Text = "..." };
        browseOutput.Click += (_, _) => SelectFolder(_outputDirectory);
        AddRow("Output folder", _outputDirectory, browseOutput);

        _logDirectory.ReadOnly = true;
        var browseLog = new Button { Text = "..." };
        browseLog.Click += (_, _) => SelectFolder(_logDirectory);
        AddRow("Log folder", _logDirectory, browseLog);

        var actionRow = mainLayout.RowCount;
        mainLayout.RowCount++;
        mainLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));
        var actions = BuildActionPanel();
        mainLayout.Controls.Add(actions, 0, actionRow);
        mainLayout.SetColumnSpan(actions, 3);

        var serviceRow = mainLayout.RowCount;
        mainLayout.RowCount++;
        mainLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var servicePanel = BuildServicePanel();
        mainLayout.Controls.Add(servicePanel, 0, serviceRow);
        mainLayout.SetColumnSpan(servicePanel, 3);

        Controls.Add(mainLayout);
    }

    private Control BuildActionPanel()
    {
        var panel = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.RightToLeft,
            AutoSize = true,
        };

        _saveButton.Text = "Save device";
        _saveButton.Click += async (_, _) => await SaveDeviceAsync();
        _deleteButton.Text = "Delete device";
        _deleteButton.Click += async (_, _) => await DeleteDeviceAsync();

        panel.Controls.Add(_saveButton);
        panel.Controls.Add(_deleteButton);
        return panel;
    }

    private Control BuildServicePanel()
    {
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 5,
            RowCount = 3,
            AutoSize = true,
        };
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));
        panel.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        var title = new Label
        {
            Text = "Service control",
            Font = new Font(Font, FontStyle.Bold),
            Dock = DockStyle.Fill,
        };
        panel.Controls.Add(title, 0, 0);
        panel.SetColumnSpan(title, 5);

        _installButton.Text = "Install";
        _installButton.Click += async (_, _) => await InstallServiceAsync();
        _startButton.Text = "Start";
        _startButton.Click += async (_, _) => await StartServiceAsync();
        _stopButton.Text = "Stop";
        _stopButton.Click += async (_, _) => await StopServiceAsync();
        _uninstallButton.Text = "Uninstall";
        _uninstallButton.Click += async (_, _) => await UninstallServiceAsync();
        var refreshButton = new Button { Text = "Refresh status" };
        refreshButton.Click += (_, _) => RefreshServiceStatus();

        panel.Controls.Add(_installButton, 0, 1);
        panel.Controls.Add(_startButton, 1, 1);
        panel.Controls.Add(_stopButton, 2, 1);
        panel.Controls.Add(_uninstallButton, 3, 1);
        panel.Controls.Add(refreshButton, 4, 1);

        _serviceStatusLabel.Text = "Service status: Unknown";
        _serviceStatusLabel.Dock = DockStyle.Fill;
        panel.Controls.Add(_serviceStatusLabel, 0, 2);
        panel.SetColumnSpan(_serviceStatusLabel, 5);

        return panel;
    }

    private ContextMenuStrip BuildTrayMenu()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add("Show", null, (_, _) => RestoreFromTray());
        menu.Items.Add("Start service", null, async (_, _) => await StartServiceAsync());
        menu.Items.Add("Stop service", null, async (_, _) => await StopServiceAsync());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Exit", null, (_, _) => Close());
        return menu;
    }

    private void LoadConfiguration(string? selectDevice = null)
    {
        var previousSelection = selectDevice ?? (_deviceList.SelectedItem as DeviceProfile)?.DeviceName;

        _configuration = _configurationStore.LoadAsync().GetAwaiter().GetResult();
        _serviceLogWriter.UpdateLogDirectory(_configuration.ServiceLogDirectory);

        _devices.Clear();
        var indexToSelect = -1;
        var currentIndex = 0;
        foreach (var device in _configuration.Devices.OrderBy(d => d.DeviceName))
        {
            _devices.Add(device);
            if (previousSelection is not null &&
                device.DeviceName.Equals(previousSelection, StringComparison.OrdinalIgnoreCase))
            {
                indexToSelect = currentIndex;
            }

            currentIndex++;
        }

        PopulateSerialPorts();
        if (indexToSelect >= 0)
        {
            _deviceList.SelectedIndex = indexToSelect;
        }
        else if (_devices.Count > 0)
        {
            _deviceList.SelectedIndex = 0;
        }
        else
        {
            _deviceList.ClearSelected();
        }

        DisplaySelectedDevice();
    }

    private void PopulateSerialPorts()
    {
        var previous = _ports.SelectedItem as string;
        var ports = SerialPort.GetPortNames().OrderBy(name => name).ToArray();
        _ports.Items.Clear();
        if (ports.Length == 0)
        {
            _ports.Items.Add("No COM ports detected");
            _ports.SelectedIndex = 0;
            _ports.Enabled = false;
        }
        else
        {
            _ports.Enabled = true;
            _ports.Items.AddRange(ports);
            if (previous is not null && ports.Contains(previous))
            {
                _ports.SelectedItem = previous;
            }
            else
            {
                _ports.SelectedIndex = 0;
            }
        }
    }

    private async Task SaveDeviceAsync()
    {
        try
        {
            var profile = CollectProfile();
            var existing = _configuration.Devices.FirstOrDefault(d => d.DeviceName.Equals(profile.DeviceName, StringComparison.OrdinalIgnoreCase));
            if (existing is not null)
            {
                existing.ComPort = profile.ComPort;
                existing.BaudRate = profile.BaudRate;
                existing.OutputDirectory = profile.OutputDirectory;
                existing.LogDirectory = profile.LogDirectory;
            }
            else
            {
                _configuration.Devices.Add(profile);
            }

            await _configurationStore.SaveAsync(_configuration);
            LoadConfiguration(profile.DeviceName);
            _serviceLogWriter.Info("GUI", $"Saved device '{profile.DeviceName}' configuration");
            MessageBox.Show($"Device '{profile.DeviceName}' saved.", "AHG LIS Project", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Failed to save device", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task DeleteDeviceAsync()
    {
        if (_deviceList.SelectedItem is not DeviceProfile profile)
        {
            MessageBox.Show("Select a device to delete.", "AHG LIS Project", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (MessageBox.Show($"Delete device '{profile.DeviceName}'?", "Confirm", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
        {
            _configuration.Devices.Remove(profile);
            await _configurationStore.SaveAsync(_configuration);
            LoadConfiguration();
            _serviceLogWriter.Warn("GUI", $"Deleted device '{profile.DeviceName}'");
        }
    }

    private async Task InstallServiceAsync()
    {
        try
        {
            await _serviceManager.InstallAsync(CancellationToken.None);
            _serviceLogWriter.Info("GUI", "Service installed");
            RefreshServiceStatus();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Failed to install service", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task UninstallServiceAsync()
    {
        try
        {
            await _serviceManager.UninstallAsync(CancellationToken.None);
            _serviceLogWriter.Warn("GUI", "Service uninstalled");
            RefreshServiceStatus();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Failed to uninstall service", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task StartServiceAsync()
    {
        try
        {
            await _serviceManager.StartAsync(CancellationToken.None);
            _serviceLogWriter.Info("GUI", "Service start requested");
            RefreshServiceStatus();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Failed to start service", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task StopServiceAsync()
    {
        try
        {
            await _serviceManager.StopAsync(CancellationToken.None);
            _serviceLogWriter.Warn("GUI", "Service stop requested");
            RefreshServiceStatus();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Failed to stop service", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void RefreshServiceStatus()
    {
        var status = _serviceManager.GetStatus();
        var installed = status is not null;

        _installButton.Enabled = _serviceManager.ServiceExecutableExists && !installed;
        _uninstallButton.Enabled = installed;
        _startButton.Enabled = installed && status != ServiceControllerStatus.Running;
        _stopButton.Enabled = installed && status == ServiceControllerStatus.Running;

        var statusText = installed ? status.ToString() : "Not installed";
        _serviceStatusLabel.Text = $"Service status: {statusText}";
        _notifyIcon.Text = $"AHG LIS Project - {statusText}";
    }

    private void DisplaySelectedDevice()
    {
        if (_deviceList.SelectedItem is not DeviceProfile profile)
        {
            _deviceName.Text = string.Empty;
            _ports.SelectedIndex = _ports.Items.Count > 0 ? 0 : -1;
            _baudRates.Text = "9600";
            _outputDirectory.Text = AppConfiguration.DefaultRoot;
            _logDirectory.Text = Path.Combine(AppConfiguration.DefaultRoot, "Logs");
            return;
        }

        _deviceName.Text = profile.DeviceName;
        _ports.SelectedItem = profile.ComPort;
        if (_ports.SelectedItem is null && _ports.Items.Count > 0)
        {
            _ports.SelectedIndex = 0;
        }

        _baudRates.Text = profile.BaudRate.ToString();
        _outputDirectory.Text = profile.OutputDirectory;
        _logDirectory.Text = profile.LogDirectory;
    }

    private DeviceProfile CollectProfile()
    {
        if (string.IsNullOrWhiteSpace(_deviceName.Text))
        {
            throw new InvalidOperationException("Device name is required.");
        }

        if (!_ports.Enabled || _ports.SelectedItem is null)
        {
            throw new InvalidOperationException("Select a serial port.");
        }

        if (!int.TryParse(_baudRates.Text, out var baud) || baud <= 0)
        {
            throw new InvalidOperationException("Enter a valid baud rate.");
        }

        if (string.IsNullOrWhiteSpace(_outputDirectory.Text))
        {
            throw new InvalidOperationException("Select an output folder.");
        }

        if (string.IsNullOrWhiteSpace(_logDirectory.Text))
        {
            throw new InvalidOperationException("Select a log folder.");
        }

        return new DeviceProfile
        {
            DeviceName = _deviceName.Text.Trim(),
            ComPort = _ports.SelectedItem.ToString()!,
            BaudRate = baud,
            OutputDirectory = _outputDirectory.Text,
            LogDirectory = _logDirectory.Text,
        };
    }

    private void SelectFolder(TextBox target)
    {
        using var dialog = new FolderBrowserDialog
        {
            SelectedPath = string.IsNullOrWhiteSpace(target.Text) ? AppConfiguration.DefaultRoot : target.Text,
            ShowNewFolderButton = true,
        };

        if (dialog.ShowDialog() == DialogResult.OK)
        {
            target.Text = dialog.SelectedPath;
        }
    }

    private void HandleResize(object? sender, EventArgs e)
    {
        if (WindowState == FormWindowState.Minimized)
        {
            Hide();
            _notifyIcon.Visible = true;
            _notifyIcon.BalloonTipTitle = "AHG LIS Project";
            _notifyIcon.BalloonTipText = "Running in the background. Double-click the shield icon to reopen.";
            _notifyIcon.ShowBalloonTip(2000);
        }
    }

    private void HandleClosing(object? sender, FormClosingEventArgs e)
    {
        _notifyIcon.Visible = false;
        _notifyIcon.Dispose();
    }

    private void RestoreFromTray()
    {
        Show();
        WindowState = FormWindowState.Normal;
        Activate();
    }
}
