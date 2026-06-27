"""Thin wrapper around python-miio's Yeelight class with caching and threading helpers."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from miio import Yeelight
from miio.exceptions import DeviceException

log = logging.getLogger(__name__)

StateListener = Callable[["LightState"], None]


@dataclass
class LightState:
    is_on: bool = False
    brightness: int = 0
    color_temp: int = 4000
    reachable: bool = False
    error: Optional[str] = None


class MiMonitorLight:
    """Synchronous, thread-safe controller for a Mi/Yeelight monitor light bar.

    The underlying ``miio`` calls are not reentrant on a single device handle,
    so a lock serialises access. State is cached so the UI can render without
    waiting on the network for every paint. Errors are captured into
    ``state.error`` rather than raised so callers don't need a try/except at
    every site.
    """

    BRIGHTNESS_MIN = 1
    BRIGHTNESS_MAX = 100
    COLOR_TEMP_MIN = 2700
    COLOR_TEMP_MAX = 6500

    DEFAULT_MODEL = "yeelink.light.monitor1"

    def __init__(self, ip: str, token: str, model: str = "") -> None:
        self._lock = threading.Lock()
        self._device = Yeelight(ip=ip, token=token, model=model or self.DEFAULT_MODEL)
        self._state = LightState()
        self._listener: Optional[StateListener] = None
        self._last_error_log = 0.0

    @property
    def state(self) -> LightState:
        return self._state

    def set_listener(self, listener: Optional[StateListener]) -> None:
        self._listener = listener

    def _notify(self) -> None:
        listener = self._listener
        if listener is None:
            return
        try:
            listener(self._state)
        except Exception:  # noqa: BLE001
            log.exception("State listener raised")

    def _record_error(self, exc: Exception, action: str) -> None:
        now = time.monotonic()
        if now - self._last_error_log > 5.0:
            log.warning("Device %s failed: %s", action, exc)
            self._last_error_log = now
        self._state.reachable = False
        self._state.error = str(exc)

    def _record_success(self) -> None:
        self._state.reachable = True
        self._state.error = None

    def refresh(self) -> LightState:
        with self._lock:
            try:
                status = self._device.status()
                self._state = LightState(
                    is_on=bool(status.is_on),
                    brightness=int(status.brightness or 0),
                    color_temp=int(status.color_temp or 4000),
                    reachable=True,
                    error=None,
                )
            except DeviceException as exc:
                self._record_error(exc, "status")
        self._notify()
        return self._state

    def set_power(self, on: bool) -> None:
        with self._lock:
            try:
                if on:
                    self._device.on()
                else:
                    self._device.off()
                self._state.is_on = on
                self._record_success()
            except DeviceException as exc:
                self._record_error(exc, "power")
        self._notify()

    def toggle(self) -> bool:
        with self._lock:
            try:
                self._device.toggle()
                self._state.is_on = not self._state.is_on
                self._record_success()
            except DeviceException as exc:
                self._record_error(exc, "toggle")
        self._notify()
        return self._state.is_on

    def set_brightness(self, value: int) -> int:
        value = max(self.BRIGHTNESS_MIN, min(self.BRIGHTNESS_MAX, int(value)))
        with self._lock:
            try:
                self._device.set_brightness(value)
                self._state.brightness = value
                self._state.is_on = True
                self._record_success()
            except DeviceException as exc:
                self._record_error(exc, "set_brightness")
        self._notify()
        return value

    def set_color_temp(self, value: int) -> int:
        value = max(self.COLOR_TEMP_MIN, min(self.COLOR_TEMP_MAX, int(value)))
        with self._lock:
            try:
                self._device.set_color_temp(value)
                self._state.color_temp = value
                self._state.is_on = True
                self._record_success()
            except DeviceException as exc:
                self._record_error(exc, "set_color_temp")
        self._notify()
        return value


class Debouncer:
    """Coalesce rapid slider updates into one network call per ``delay`` window."""

    def __init__(self, delay: float = 0.15) -> None:
        self._delay = delay
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._pending = None

    def call(self, fn, *args) -> None:
        with self._lock:
            self._pending = (fn, args)
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._delay, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            pending = self._pending
            self._pending = None
            self._timer = None
        if pending is None:
            return
        fn, args = pending
        try:
            fn(*args)
        except Exception:
            log.exception("Debounced call failed")

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending = None


def quick_ping(ip: str, token: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Return (ok, message) for a minimal connectivity check used by the setup wizard."""
    try:
        dev = Yeelight(ip=ip, token=token)
        dev.timeout = timeout
        info = dev.info()
        return True, f"Connected: {info.model} (firmware {info.firmware_version})"
    except DeviceException as exc:
        return False, f"miio error: {exc}"
    except Exception as exc:  # noqa: BLE001 - surface anything else to the user
        return False, f"{type(exc).__name__}: {exc}"
