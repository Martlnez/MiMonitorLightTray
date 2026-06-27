# Mi Monitor Light Tray

A Windows system-tray app that adjusts the brightness and color temperature of
Xiaomi / Mi (Yeelight) monitor light bars, in the same flyout-slider style as
[Twinkle Tray](https://twinkletray.com/). Built on top of
[python-miio](https://github.com/rytilahti/python-miio).

> Works with Mi monitor light bars and similar Yeelight devices that expose the
> standard `set_bright` / `set_ct_abx` miio commands (e.g. `yeelink.light.monitor1`,
> `yeelink.light.monitor2`, and other Yeelight white-tunable WiFi lights).

## Features

- Tray icon with a Twinkle Tray-style flyout that anchors near the cursor
- Brightness slider (1-100) and color temperature slider (2700K-6500K)
- Power toggle in the flyout header
- Slider movements are debounced so dragging produces one miio call per ~150ms,
  not one per pixel
- Persistent config under `%APPDATA%/MiMonitorLightTray/config.json`
- Settings window with a "Test connection" button
- First-run wizard if no config exists yet
- Headless `--setup` flag for re-running the wizard without touching the tray

## Install

### From source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
mi-monitor-light-tray
```

Requires Python 3.9+.

### Pre-built Windows binary

Every push to `main` and every tagged release produces a single-file
`MiMonitorLightTray.exe` via the [build workflow](.github/workflows/build.yml).
Grab it from the run's artifacts or from the GitHub release page.

## First-run setup

You need two things to talk to the light:

1. **The device's LAN IP** — visible in the Mi Home app under the device's
   info page, or in your router's DHCP table.
2. **The 32-character miio token** — extract it once with a tool such as
   [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor),
   or with `miiocli cloud login` (shipped with python-miio).

On first launch the settings wizard opens; paste both fields, click
**Test connection**, then **Save**. The token is stored locally only.

To re-open the wizard later: right-click the tray icon → Settings, or run
`mi-monitor-light-tray --setup`.

## Usage

- **Left-click** the tray icon → flyout opens above the icon
- Drag sliders to adjust brightness / color temperature in real time
- Click **On** / **Off** in the flyout header to toggle power
- Click outside the flyout (or press `Esc`) to dismiss it
- Right-click the tray icon for Settings / Exit

## Build a single-file EXE locally

```bash
pip install -e ".[build]"
python scripts/build_exe.py
```

Output: `dist/MiMonitorLightTray.exe`.

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

The test suite covers config persistence and icon generation. UI and miio
network paths are out of scope for unit tests and exercised manually.

## Project layout

```
mi_monitor_light_tray/
  __main__.py        entrypoint, wires tray + flyout + config
  config.py          AppConfig / DeviceConfig persistence
  flyout.py          Borderless Tk flyout window with sliders
  icon.py            Programmatic PIL tray icon (no binary assets)
  miio_client.py     Threaded Yeelight wrapper + slider debouncer
  setup_wizard.py    IP / token capture window with connection test
  tray.py            pystray TrayController
scripts/build_exe.py PyInstaller helper
tests/               pytest suite
```

## Troubleshooting

- **"Offline — Unable to discover the device"**: confirm the IP is right and
  the light is on the same LAN as your PC. Mi devices are LAN-only over miio.
- **"miio error: Invalid token"**: re-extract the token with the
  cloud-tokens-extractor; tokens rotate when you re-pair the device.
- **Tray icon doesn't appear**: another instance may already be running, or
  Windows Explorer's icon overflow has hidden it — check the overflow tray.

## Acknowledgements

- [python-miio](https://github.com/rytilahti/python-miio) — the protocol library
- [Twinkle Tray](https://twinkletray.com/) — UX inspiration
- [pystray](https://github.com/moses-palmer/pystray) — the tray plumbing

## License

MIT — see [LICENSE](LICENSE).
