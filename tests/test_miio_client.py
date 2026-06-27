"""Unit tests for the miio wrapper — focus on error capture and listener wiring.

These tests stub out python-miio's ``Yeelight`` so they run offline. The point
is to verify our wrapper's contract: errors should be captured into state,
listeners should fire, and no DeviceException should escape.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from miio.exceptions import DeviceException

from mi_monitor_light_tray import miio_client


@pytest.fixture
def fake_yeelight(monkeypatch):
    """Replace miio.Yeelight in the wrapper with a MagicMock factory."""
    factory = MagicMock()
    monkeypatch.setattr(miio_client, "Yeelight", factory)
    return factory


def _make(fake_yeelight, **device_methods):
    device = MagicMock()
    for name, value in device_methods.items():
        method = MagicMock(side_effect=value) if isinstance(value, Exception) else MagicMock(return_value=value)
        setattr(device, name, method)
    fake_yeelight.return_value = device
    return miio_client.MiMonitorLight(ip="1.2.3.4", token="t" * 32), device


def test_set_brightness_captures_device_exception(fake_yeelight):
    light, dev = _make(fake_yeelight, set_brightness=DeviceException("boom"))
    result = light.set_brightness(50)
    assert result == 50  # clamped value still returned
    assert light.state.reachable is False
    assert "boom" in light.state.error
    dev.set_brightness.assert_called_once_with(50)


def test_set_brightness_clamps(fake_yeelight):
    light, dev = _make(fake_yeelight, set_brightness=None)
    assert light.set_brightness(999) == 100
    assert light.set_brightness(-5) == 1
    assert light.state.brightness == 1
    assert light.state.reachable is True


def test_set_color_temp_clamps_and_captures(fake_yeelight):
    light, dev = _make(fake_yeelight, set_color_temp=DeviceException("nope"))
    assert light.set_color_temp(10000) == miio_client.MiMonitorLight.COLOR_TEMP_MAX
    assert light.set_color_temp(0) == miio_client.MiMonitorLight.COLOR_TEMP_MIN
    assert light.state.error == "nope"
    assert light.state.reachable is False


def test_listener_is_called_on_state_change(fake_yeelight):
    light, _ = _make(fake_yeelight, set_brightness=None)
    seen = []
    light.set_listener(lambda s: seen.append((s.brightness, s.reachable)))
    light.set_brightness(42)
    light.set_brightness(80)
    assert seen == [(42, True), (80, True)]


def test_toggle_captures_exception(fake_yeelight):
    light, _ = _make(fake_yeelight, toggle=DeviceException("offline"))
    # Should not raise — should just record the error.
    result = light.toggle()
    assert isinstance(result, bool)
    assert light.state.reachable is False
    assert light.state.error == "offline"


def test_refresh_offline_returns_state(fake_yeelight):
    light, _ = _make(fake_yeelight, status=DeviceException("noop"))
    state = light.refresh()
    assert state.reachable is False
    assert state.error == "noop"


def test_lock_serialises_calls(fake_yeelight):
    """Two threads calling set_brightness should not interleave inside the lock."""
    light, dev = _make(fake_yeelight, set_brightness=None)

    inside = []
    barrier = threading.Event()

    def slow(_value):
        inside.append("enter")
        barrier.wait(timeout=0.1)
        inside.append("exit")

    dev.set_brightness = MagicMock(side_effect=slow)

    t1 = threading.Thread(target=light.set_brightness, args=(30,))
    t2 = threading.Thread(target=light.set_brightness, args=(60,))
    t1.start()
    t2.start()
    barrier.set()
    t1.join()
    t2.join()

    # Each call must be fully bracketed (enter, exit) before the next starts.
    assert inside == ["enter", "exit", "enter", "exit"]


def test_debouncer_coalesces_rapid_calls():
    d = miio_client.Debouncer(delay=0.05)
    calls = []
    for v in range(10):
        d.call(calls.append, v)
    # The timer fires after the delay; wait it out.
    import time
    time.sleep(0.15)
    assert calls == [9]
    d.cancel()
