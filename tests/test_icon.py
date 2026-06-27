"""Smoke tests for the in-memory tray icon."""

from mi_monitor_light_tray.icon import make_tray_icon


def test_icon_is_rgba_image():
    img = make_tray_icon(64, on=True)
    assert img.mode == "RGBA"
    assert img.size == (64, 64)


def test_icon_off_state():
    img = make_tray_icon(32, on=False)
    assert img.size == (32, 32)
