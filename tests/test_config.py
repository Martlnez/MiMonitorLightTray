"""Unit tests for AppConfig serialisation and DeviceConfig validation."""

import json
from pathlib import Path

import pytest

from mi_monitor_light_tray.config import AppConfig, DeviceConfig


def test_device_config_is_complete():
    assert not DeviceConfig().is_complete()
    assert not DeviceConfig(ip="192.168.1.10", token="short").is_complete()
    assert DeviceConfig(ip="192.168.1.10", token="x" * 32).is_complete()


def test_appconfig_roundtrip(tmp_path: Path):
    cfg = AppConfig(
        device=DeviceConfig(ip="10.0.0.5", token="a" * 32, name="Bar", model="yeelink.light.monitor1"),
        last_brightness=72,
        last_color_temp=4500,
        start_with_windows=True,
    )
    p = tmp_path / "cfg.json"
    cfg.save(p)
    loaded = AppConfig.load(p)
    assert loaded.device.ip == "10.0.0.5"
    assert loaded.device.token == "a" * 32
    assert loaded.device.name == "Bar"
    assert loaded.device.model == "yeelink.light.monitor1"
    assert loaded.last_brightness == 72
    assert loaded.last_color_temp == 4500
    assert loaded.start_with_windows is True


def test_appconfig_missing_file_returns_default(tmp_path: Path):
    p = tmp_path / "missing.json"
    cfg = AppConfig.load(p)
    assert cfg.device.ip == ""
    assert cfg.last_brightness == 50


def test_appconfig_bad_json_returns_default(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    cfg = AppConfig.load(p)
    assert cfg.device.ip == ""


def test_appconfig_save_atomic(tmp_path: Path):
    p = tmp_path / "cfg.json"
    AppConfig(device=DeviceConfig(ip="1.2.3.4", token="t" * 32)).save(p)
    parsed = json.loads(p.read_text(encoding="utf-8"))
    assert parsed["device"]["ip"] == "1.2.3.4"
    # No leftover tmp file.
    assert not (tmp_path / "cfg.json.tmp").exists()
