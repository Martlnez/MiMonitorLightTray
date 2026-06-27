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

    When the device becomes unreachable (e.g., IP changed via DHCP), the wrapper
    can attempt auto-discovery if device_id is known.
    """

    BRIGHTNESS_MIN = 1
    BRIGHTNESS_MAX = 100
    COLOR_TEMP_MIN = 2700
    COLOR_TEMP_MAX = 6500

    DEFAULT_MODEL = "yeelink.light.monitor1"

    def __init__(
        self,
        ip: str,
        token: str,
        model: str = "",
        device_id: int = 0,
        on_ip_changed: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._ip = ip
        self._token = token
        self._model = model or self.DEFAULT_MODEL
        self._device_id = device_id
        self._on_ip_changed = on_ip_changed
        self._lock = threading.Lock()
        self._device = Yeelight(ip=ip, token=token, model=self._model)
        self._state = LightState()
        self._listener: Optional[StateListener] = None
        self._last_error_log = 0.0
        self._discovery_in_progress = False

    @property
    def state(self) -> LightState:
        return self._state

    @property
    def device_id(self) -> int:
        """Return the device ID if known (retrieved from info() on first success)."""
        return self._device_id

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

        # If we have a device_id and discovery isn't already running, try to find the new IP.
        if (
            self._device_id > 0
            and not self._discovery_in_progress
            and "Unable to discover" in str(exc)
        ):
            log.info("Device unreachable; attempting auto-discovery...")
            threading.Thread(target=self._try_rediscover, daemon=True).start()

    def _try_rediscover(self) -> None:
        self._discovery_in_progress = True
        try:
            from .discovery import find_device_by_id

            new_ip = find_device_by_id(self._device_id, timeout=6.0)
            if new_ip and new_ip != self._ip:
                log.info("Device found at new IP: %s (was %s)", new_ip, self._ip)
                self._ip = new_ip
                with self._lock:
                    self._device = Yeelight(
                        ip=new_ip, token=self._token, model=self._model
                    )
                if self._on_ip_changed:
                    self._on_ip_changed(new_ip)
                # Retry status immediately.
                self.refresh()
            else:
                log.warning("Auto-discovery did not find device %08x", self._device_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("Auto-discovery failed: %s", exc)
        finally:
            self._discovery_in_progress = False

    def _record_success(self) -> None:
        self._state.reachable = True
        self._state.error = None

        # Capture device_id on first successful connection if not already known.
        if self._device_id == 0:
            try:
                info = self._device.info()
                self._device_id = info.device_id
                log.info("Captured device ID: %08x", self._device_id)
            except Exception:  # noqa: BLE001
                pass

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
