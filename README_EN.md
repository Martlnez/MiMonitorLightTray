# Mi Monitor Light Tray

> 中文版：**[README.md](README.md)**

A Windows system-tray utility that controls Xiaomi / Yeelight monitor light bars with the same flyout-slider experience as [Twinkle Tray](https://twinkletray.com/). Built on [python-miio](https://github.com/rytilahti/python-miio), talks to the light over the **local LAN** (no cloud calls).

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

## Supported devices

Any Xiaomi / Yeelight tunable-white light that speaks the standard Yeelight miio commands (`set_bright` / `set_ct_abx`):

- `yeelink.light.monitor1` — Mi monitor light bar (default model)
- `yeelink.light.monitor2`
- `yeelink.light.lamp22` and other Yeelight white-tunable WiFi lights

## Features

- **Twinkle Tray-style flyout** — appears near the cursor, dismisses on outside click or `Esc`
- **Brightness & color-temperature sliders** — brightness 1–100, color temperature 2700K–6500K
- **Debounced slider updates** — drags are coalesced into one miio call every ~120/180 ms instead of one per pixel
- **Single-instance lock** — a Windows named mutex prevents duplicate launches and shows a friendly dialog instead
- **Auto-rediscovery on IP change** — when DHCP rotates the light's IP, the app locates it again by device ID and updates the config silently
- **Fluent Design look** — native DWM rounded corners, semi-transparent dark surface, Win11 accent color
- **Minimal vector tray icon** — drawn with Pillow, sharp on any DPI, distinct on/off states
- **First-run wizard** — IP/Token capture with a built-in **Test connection** button
- **Persistent config** — atomic write to `%APPDATA%\MiMonitorLightTray\config.json`
- **No install required** — single-file EXE, no Python on the target machine

## Install

### Option 1: pre-built binary (recommended)

Grab `MiMonitorLightTray.exe` from [Releases](https://github.com/Martlnez/MiMonitorLightTray/releases). Every push to `main` and every tag triggers a CI build (see [build.yml](.github/workflows/build.yml)).

### Option 2: run from source

```bash
git clone https://github.com/Martlnez/MiMonitorLightTray.git
cd MiMonitorLightTray

python -m venv .venv
.venv\Scripts\activate
pip install -e .

mi-monitor-light-tray
```

Requires Python 3.9+.

## First-run setup

You need two pieces of information to talk to the light: the **device's LAN IP** and its **32-character miio Token**.

### 1. Find the device IP

**Option A — Mi Home app**

1. Open Mi Home, locate the monitor light
2. Open the device page → **⋮** (top-right) → **Device info**
3. Note the IP (e.g. `192.168.1.100`)

**Option B — your router**

Log in to the router admin page (often `192.168.1.1` or `192.168.0.1`), open the **Connected devices** / **DHCP client list**, and look for a device whose hostname contains `yeelight` or `monitor`.

### 2. Get the miio Token

The token is a 32-char hex string used to authenticate with the device. Mi Home doesn't expose it directly — extract it once with an external tool.

**Recommended: [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)**

Download the Python script or the Windows EXE, sign in with your Xiaomi account when prompted, and it'll dump every device's IP and token.

**Alternative: `miiocli` (bundled with python-miio)**

```bash
.venv\Scripts\activate
miiocli cloud
# Sign in with your Xiaomi account; tokens for all devices are printed.
```

### 3. Launch and configure

The first launch opens the setup wizard:

- **Device IP**: from step 1
- **miio Token**: from step 2
- **Display name**: anything — shown in the tray tooltip
- **Model**: leave blank; the app auto-detects it after connecting

Click **Test connection** to verify, then **Save**. The token is written **locally only** to `%APPDATA%\MiMonitorLightTray\config.json` — it never leaves your machine.

### (Optional) verify connectivity by hand

```python
from miio import Yeelight

light = Yeelight(ip="192.168.1.xxx", token="your-32-char-token")
status = light.status()
print(f"Power: {'on' if status.is_on else 'off'}")
print(f"Brightness: {status.brightness}%")
print(f"Color temp: {status.color_temp}K")
```

## Usage

- **Left-click** the tray icon → flyout opens near the cursor
- Drag the **Brightness** slider (1–100) and the **Color temperature** slider (2700K warm — 6500K cool)
- Click **⏻** in the footer to toggle power, **⚙** to open settings
- Click outside the flyout, or press `Esc`, to dismiss it
- **Right-click** the tray icon:
  - **调整亮度** (Adjust) — open the flyout
  - **设置** (Settings) — reconfigure the device
  - **退出** (Exit) — quit the app

> The right-click menu is intentionally localized to Chinese to match the rest of the device's ecosystem (Mi Home is Chinese-first); the English README mirrors the labels for reference.

### Run at startup

Press `Win+R`, run `shell:startup`, drop a shortcut to `MiMonitorLightTray.exe` into the folder that opens.

### Command-line flags

```bash
MiMonitorLightTray.exe --setup    # force-open the setup wizard
MiMonitorLightTray.exe --debug    # enable DEBUG logging
```

## Build a single-file EXE locally

```bash
pip install -e ".[build]"
python scripts/build_exe.py
```

Outputs to `dist\MiMonitorLightTray.exe`. The script invokes PyInstaller with `--onefile --noconsole`, and uses `--collect-data miio` to bundle python-miio's YAML/JSON spec files (without that, the device-info parser crashes at runtime).

## Run tests

```bash
pip install -e ".[dev]"
pytest -q
```

Coverage: config serialization ([tests/test_config.py](tests/test_config.py)), tray icon rendering ([tests/test_icon.py](tests/test_icon.py)), miio wrapper and debouncer ([tests/test_miio_client.py](tests/test_miio_client.py)). UI and live-network paths are exercised manually.

## Project layout

```
mi_monitor_light_tray/
  __main__.py          entrypoint: single-instance lock → config → tray + flyout
  config.py            AppConfig / DeviceConfig persistence (atomic write)
  miio_client.py       thread-safe Yeelight wrapper + slider Debouncer
  flyout.py            borderless Tk window with Canvas dark sliders
  icon.py              Pillow-generated tray icon (no binary assets)
  setup_wizard.py      IP/Token capture window with connection test
  tray.py              pystray system-tray controller
  single_instance.py   Windows named-mutex single-instance lock
  discovery.py         UDP-broadcast device discovery, re-locate by device_id
scripts/
  build_exe.py         PyInstaller helper
  run_app.py           PyInstaller entry (avoids relative-import issues)
tests/                 pytest unit suite
```

## Config file

Location: `%APPDATA%\MiMonitorLightTray\config.json`

```json
{
  "device": {
    "ip": "192.168.1.100",
    "token": "...32 hex chars...",
    "name": "Mi Monitor Light",
    "model": "",
    "device_id": 12345678
  },
  "last_brightness": 50,
  "last_color_temp": 4000,
  "start_with_windows": false
}
```

`device_id` is captured automatically on the first successful connect and is what enables auto-rediscovery when the IP changes.

## Troubleshooting

**"Another instance is already running"**
The app is already up — check the tray overflow area (the up-arrow on the right of the taskbar).

**Status shows "Offline — Unable to discover the device"**
1. Confirm the light is powered on and on the same LAN as your PC
2. Re-check the IP via Mi Home or the router
3. miio uses UDP/54321 — corporate firewalls sometimes block it; try disabling the firewall briefly to confirm
4. If `device_id` was captured before, the app keeps retrying discovery in the background

**"miio error: Invalid token"**
Tokens rotate when the device is re-paired in Mi Home — re-extract with cloud-tokens-extractor.

**Tray icon doesn't appear**
Windows Explorer may have hidden it in the overflow area; click the up-arrow on the taskbar.

**Sliders feel ~0.1 s laggy while dragging**
That's intentional debouncing (120 ms brightness / 180 ms color temperature) to avoid flooding the device. The final value commits as soon as you let go.

## Acknowledgements

- [python-miio](https://github.com/rytilahti/python-miio) — the protocol library
- [pystray](https://github.com/moses-palmer/pystray) — Python system-tray glue
- [Pillow](https://python-pillow.org/) — icon rendering
- [Twinkle Tray](https://twinkletray.com/) — UX inspiration

## License

[MIT License](LICENSE)
