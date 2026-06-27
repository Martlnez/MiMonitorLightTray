"""Persistent user configuration stored under %APPDATA%/MiMonitorLightTray/config.json."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def _default_config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "MiMonitorLightTray"
    return Path.home() / ".mi-monitor-light-tray"


@dataclass
class DeviceConfig:
    ip: str = ""
    token: str = ""
    name: str = "Mi Monitor Light"
    model: str = ""

    def is_complete(self) -> bool:
        return bool(self.ip) and bool(self.token) and len(self.token) == 32


@dataclass
class AppConfig:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    last_brightness: int = 50
    last_color_temp: int = 4000
    start_with_windows: bool = False

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        path = path or default_config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to read config %s: %s", path, exc)
            return cls()
        dev = DeviceConfig(**data.get("device", {}))
        return cls(
            device=dev,
            last_brightness=int(data.get("last_brightness", 50)),
            last_color_temp=int(data.get("last_color_temp", 4000)),
            start_with_windows=bool(data.get("start_with_windows", False)),
        )

    def save(self, path: Optional[Path] = None) -> None:
        path = path or default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "device": asdict(self.device),
            "last_brightness": self.last_brightness,
            "last_color_temp": self.last_color_temp,
            "start_with_windows": self.start_with_windows,
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)


def default_config_path() -> Path:
    return _default_config_dir() / "config.json"
