"""Thin wrapper around python-miio with caching, threading, and protocol dispatch.

The wrapper supports two underlying protocols and picks one per device model:

* **Legacy Yeelight** — string-keyed properties (``set_bright`` / ``set_ct_abx``).
  Used by older monitor / desk lamps such as ``yeelink.light.lamp1``/``2``/``4``.
* **MIoT** — properties addressed as ``(siid, piid)`` tuples and discovered via
  per-model spec mappings. Used by ``yeelink.light.lamp22`` (Mi Smart Monitor
  Light Bar 1S) and newer devices.

Both protocols share the miio handshake/transport, so ``info()`` and the
device-id capture work identically. Only application-level reads/writes differ;
the ``_Backend`` abstraction hides that difference from ``MiMonitorLight``.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from miio import Device, Yeelight
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice
from miio.integrations.light.yeelight.spec_helper import (
    YeelightSpecHelper,
    YeelightSubLightType,
)

log = logging.getLogger(__name__)

StateListener = Callable[["LightState"], None]


# Single shared spec helper — its model cache is class-level inside python-miio
# (parsed from specs.yaml once), so constructing more instances costs nothing
# extra. We keep a reference to make the dependency explicit.
_SPEC_HELPER = YeelightSpecHelper()


# ---------------------------------------------------------------------------
# MIoT spec mappings — keyed by model id.
#
# Verified against home.miot-spec.com. Each entry must list the three
# properties the UI needs: power, brightness, color_temperature.
# ---------------------------------------------------------------------------
_MIOT_MAPPINGS: Dict[str, Dict[str, Dict[str, int]]] = {
    # yeelink.light.lamp22 — 米家智能显示器挂灯 1S (default model)
    # urn:miot-spec-v2:device:light:0000A001:yeelink-lamp22:1
    "yeelink.light.lamp22": {
        "power":             {"siid": 2, "piid": 1},
        "brightness":        {"siid": 2, "piid": 2},
        "color_temperature": {"siid": 2, "piid": 3},
    },
}

# Generic Light-service mapping used as a fallback when the user opts to treat
# unknown models as MIoT. Matches the spec layout shared by most Mi/Yeelight
# monitor lights and desk lamps (Service 2 = Main Light, properties 1/2/3 =
# power/brightness/color-temperature).
_GENERIC_MIOT_LIGHT_MAPPING: Dict[str, Dict[str, int]] = _MIOT_MAPPINGS[
    "yeelink.light.lamp22"
]


def _extract_device_id(device: Device) -> int:
    """Read the miio header device_id captured during the last handshake.

    Works for both ``Yeelight`` and ``MiotDevice``: both inherit from
    ``miio.Device`` and stash the 4-byte device id from the response header on
    ``_protocol._device_id``. That matches what the UDP broadcast discovery
    parser extracts, so it's the right value for IP rediscovery to match
    against. Returns 0 if the protocol hasn't seen a response yet or the layout
    changes in a future python-miio version.
    """
    proto = getattr(device, "_protocol", None)
    raw = getattr(proto, "_device_id", b"") if proto is not None else b""
    if not raw or len(raw) != 4:
        return 0
    try:
        return int.from_bytes(raw, "big")
    except (TypeError, ValueError):
        return 0


@dataclass
class LightState:
    is_on: bool = False
    brightness: int = 0
    color_temp: int = 4000
    reachable: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Backend abstraction — uniform interface over legacy Yeelight vs. MIoT.
# ---------------------------------------------------------------------------


@dataclass
class _StatusSnapshot:
    """Minimal status shape consumed by ``MiMonitorLight.refresh``."""

    is_on: bool
    brightness: int
    color_temp: int


class _LegacyBackend:
    """Wraps ``miio.Yeelight`` for devices speaking legacy string properties."""

    def __init__(self, ip: str, token: str, model: str) -> None:
        # python-miio's Yeelight tolerates an empty/unknown model — it only
        # affects an internal spec helper that we silence in __main__.
        self._dev = Yeelight(ip=ip, token=token, model=model or "")

    @property
    def device(self) -> Device:
        return self._dev

    def info(self):
        return self._dev.info()

    def status(self) -> _StatusSnapshot:
        s = self._dev.status()
        return _StatusSnapshot(
            is_on=bool(s.is_on),
            brightness=int(s.brightness or 0),
            color_temp=int(s.color_temp or 4000),
        )

    def on(self) -> None:
        self._dev.on()

    def off(self) -> None:
        self._dev.off()

    def toggle(self) -> None:
        self._dev.toggle()

    def set_brightness(self, value: int) -> None:
        self._dev.set_brightness(value)

    def set_color_temp(self, value: int) -> None:
        self._dev.set_color_temp(value)


class _MiotBackend:
    """Wraps ``miio.MiotDevice`` with a property mapping passed at construction.

    Mapping keys are fixed: ``power`` / ``brightness`` / ``color_temperature``.
    ``_make_backend`` picks the right mapping per model (or supplies the
    generic Light-service mapping for the opt-in probe path).
    """

    def __init__(self, ip: str, token: str, model: str,
                 mapping: Dict[str, Dict[str, int]]) -> None:
        self._dev = MiotDevice(ip=ip, token=token, model=model, mapping=mapping)

    @property
    def device(self) -> Device:
        return self._dev

    def info(self):
        return self._dev.info()

    def status(self) -> _StatusSnapshot:
        # get_properties_for_mapping returns a list of dicts shaped like
        # {"did": "power", "siid": ..., "piid": ..., "code": 0, "value": True}
        props = self._dev.get_properties_for_mapping()
        values: Dict[str, Any] = {}
        for p in props:
            did = p.get("did")
            if did and p.get("code", 0) == 0:
                values[did] = p.get("value")
        return _StatusSnapshot(
            is_on=bool(values.get("power", False)),
            brightness=int(values.get("brightness", 0) or 0),
            color_temp=int(values.get("color_temperature", 4000) or 4000),
        )

    def on(self) -> None:
        self._dev.set_property("power", True)

    def off(self) -> None:
        self._dev.set_property("power", False)

    def toggle(self) -> None:
        # MIoT has no atomic toggle action in the Light service. Read-then-flip.
        # If the read fails we let the exception propagate to _record_error.
        current = self._dev.get_properties_for_mapping()
        is_on = False
        for p in current:
            if p.get("did") == "power" and p.get("code", 0) == 0:
                is_on = bool(p.get("value"))
                break
        self._dev.set_property("power", not is_on)

    def set_brightness(self, value: int) -> None:
        self._dev.set_property("brightness", value)

    def set_color_temp(self, value: int) -> None:
        self._dev.set_property("color_temperature", value)


def _make_backend(ip: str, token: str, model: str, *, enable_miot_for_unknown: bool = False):
    """Pick the right backend for ``model``.

    Resolution order:
      1. ``model`` is in ``_MIOT_MAPPINGS`` → MIoT with the model-specific mapping.
      2. ``enable_miot_for_unknown`` is True → MIoT with the generic Light-service
         mapping (siid=2, piids 1/2/3). Best-effort probe for newer Yeelight
         devices that share the standard spec but aren't whitelisted yet.
      3. Otherwise → legacy Yeelight.
    """
    if model and model in _MIOT_MAPPINGS:
        return _MiotBackend(ip=ip, token=token, model=model,
                            mapping=_MIOT_MAPPINGS[model])
    if enable_miot_for_unknown:
        return _MiotBackend(ip=ip, token=token, model=model or "",
                            mapping=_GENERIC_MIOT_LIGHT_MAPPING)
    return _LegacyBackend(ip=ip, token=token, model=model)


class MiMonitorLight:
    """Synchronous, thread-safe controller for a Mi/Yeelight monitor light bar.

    The underlying ``miio`` calls are not reentrant on a single device handle,
    so a lock serialises access. State is cached so the UI can render without
    waiting on the network for every paint. Errors are captured into
    ``state.error`` rather than raised so callers don't need a try/except at
    every site.

    When the device becomes unreachable (e.g., IP changed via DHCP), the wrapper
    can attempt auto-discovery if device_id is known.

    Protocol selection (legacy Yeelight vs. MIoT) happens at construction time
    based on ``model``; if the configured model is empty or wrong, ``info()``
    from the first successful call resolves the real one and the backend is
    rebuilt accordingly.
    """

    BRIGHTNESS_MIN = 1
    BRIGHTNESS_MAX = 100
    COLOR_TEMP_MIN = 2700
    COLOR_TEMP_MAX = 6500

    DEFAULT_MODEL = "yeelink.light.lamp22"

    # Color-temperature ranges (Kelvin) per model — *overrides* for cases where
    # python-miio's bundled YeelightSpecHelper data is wrong or missing.
    # Resolution order in ``ct_range_for``:
    #   1. this dict (curated overrides)
    #   2. python-miio's YeelightSpecHelper (~50 bundled Yeelight models)
    #   3. conservative class default (2700–6500K)
    # Keep this dict small. Add an entry only when (a) the model is missing
    # from specs.yaml AND verified against miot-spec.org, or (b) the bundled
    # value is provably wrong on real hardware.
    MODEL_CT_RANGES: dict[str, tuple[int, int]] = {
        "yeelink.light.lamp2": (2500, 4800),  # 米家台灯 Pro — not in python-miio specs.yaml
    }

    @classmethod
    def ct_range_for(cls, model: str) -> tuple[int, int]:
        """Return (min, max) Kelvin for ``model``.

        Resolution order:
          1. ``MODEL_CT_RANGES`` overrides
          2. python-miio's bundled YeelightSpecHelper (~50 known Yeelight models)
          3. Class default (2700–6500K)
        """
        if model and model in cls.MODEL_CT_RANGES:
            return cls.MODEL_CT_RANGES[model]
        if model and model in _SPEC_HELPER.supported_models:
            info = _SPEC_HELPER.get_model_info(model)
            ct = info.lamps[YeelightSubLightType.Main].color_temp
            return int(ct.min), int(ct.max)
        return cls.COLOR_TEMP_MIN, cls.COLOR_TEMP_MAX

    def __init__(
        self,
        ip: str,
        token: str,
        model: str = "",
        device_id: int = 0,
        on_ip_changed: Optional[Callable[[str], None]] = None,
        on_range_changed: Optional[Callable[[int, int], None]] = None,
        enable_miot_for_unknown: bool = False,
    ) -> None:
        self._ip = ip
        self._token = token
        self._model = model or self.DEFAULT_MODEL
        self._device_id = device_id
        self._on_ip_changed = on_ip_changed
        self._on_range_changed = on_range_changed
        self._enable_miot_for_unknown = enable_miot_for_unknown
        self._lock = threading.Lock()
        self._device = _make_backend(
            ip, token, self._model,
            enable_miot_for_unknown=enable_miot_for_unknown,
        )
        self._state = LightState()
        self._listener: Optional[StateListener] = None
        self._last_error_log = 0.0
        self._discovery_in_progress = False
        self._color_temp_min, self._color_temp_max = self.ct_range_for(self._model)
        # Whether info() has reported a model since this session began. Until
        # then we keep probing on success in case the configured model is wrong
        # or the user left it blank.
        self._model_resolved = False

    @property
    def state(self) -> LightState:
        return self._state

    @property
    def device_id(self) -> int:
        """Return the device ID if known (retrieved from info() on first success)."""
        return self._device_id

    @property
    def model(self) -> str:
        """Return the resolved model id (configured value or device-reported)."""
        return self._model

    @property
    def color_temp_min(self) -> int:
        return self._color_temp_min

    @property
    def color_temp_max(self) -> int:
        return self._color_temp_max

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
                    self._device = _make_backend(
                        new_ip, self._token, self._model,
                        enable_miot_for_unknown=self._enable_miot_for_unknown,
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

        # First-time bookkeeping: capture device_id (used for IP auto-rediscovery)
        # and resolve the model id (used to pick the right CT range and protocol
        # backend). Both come from info(); we issue at most one info() per session.
        if self._model_resolved and self._device_id != 0:
            return
        try:
            info = self._device.info()
        except Exception:  # noqa: BLE001 — info is best-effort
            return

        if self._device_id == 0:
            self._device_id = _extract_device_id(self._device.device)
            if self._device_id:
                log.info("Captured device ID: %08x", self._device_id)

        if not self._model_resolved:
            reported = getattr(info, "model", "") or ""
            # info.model can be anything (some mocks/tests return non-strings,
            # and a future python-miio may return None). Only act on real strings.
            if not isinstance(reported, str):
                reported = ""
            if reported and reported != self._model:
                log.info("Device model reported as %s (was %s)", reported, self._model)
                self._model = reported
                # The reported model may need a different protocol than what we
                # started with. Swap the backend if the protocol family differs.
                current_is_miot = isinstance(self._device, _MiotBackend)
                target_is_miot = reported in _MIOT_MAPPINGS
                if current_is_miot != target_is_miot:
                    log.info(
                        "Switching backend to %s for model %s",
                        "MIoT" if target_is_miot else "legacy",
                        reported,
                    )
                    self._device = _make_backend(
                        self._ip, self._token, reported,
                        enable_miot_for_unknown=self._enable_miot_for_unknown,
                    )
            new_range = self.ct_range_for(self._model)
            if new_range != (self._color_temp_min, self._color_temp_max):
                self._color_temp_min, self._color_temp_max = new_range
                log.info("Color-temp range for %s: %d-%dK",
                         self._model, *new_range)
                # Re-clamp the current cached value into the new window.
                self._state.color_temp = max(
                    self._color_temp_min,
                    min(self._color_temp_max, self._state.color_temp or 4000),
                )
                callback = self._on_range_changed
                if callback is not None:
                    try:
                        callback(self._color_temp_min, self._color_temp_max)
                    except Exception:  # noqa: BLE001
                        log.exception("on_range_changed listener raised")
            self._model_resolved = True

    def refresh(self) -> LightState:
        with self._lock:
            try:
                status = self._device.status()
                self._state = LightState(
                    is_on=status.is_on,
                    brightness=status.brightness,
                    color_temp=status.color_temp,
                    reachable=True,
                    error=None,
                )
                self._record_success()
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
                # Auto-on: legacy Yeelight's auto-on behavior is firmware-dependent
                # and MIoT lamps don't auto-on at all. Explicitly power on first
                # if the cached state says we're off — otherwise the slider drag
                # would do nothing visible.
                if not self._state.is_on:
                    self._device.on()
                    self._state.is_on = True
                self._device.set_brightness(value)
                self._state.brightness = value
                self._record_success()
            except DeviceException as exc:
                self._record_error(exc, "set_brightness")
        self._notify()
        return value

    def set_color_temp(self, value: int) -> int:
        value = max(self._color_temp_min, min(self._color_temp_max, int(value)))
        with self._lock:
            try:
                if not self._state.is_on:
                    self._device.on()
                    self._state.is_on = True
                self._device.set_color_temp(value)
                self._state.color_temp = value
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


def quick_ping(ip: str, token: str, timeout: float = 3.0) -> tuple[bool, str, int]:
    """Return (ok, message, device_id) for a minimal connectivity check.

    Used by the setup wizard. device_id is 0 on failure or when the protocol
    layout changes; non-zero values should be persisted to config so
    auto-discovery can work later if the IP changes.

    Uses ``miio.Device`` directly (not ``Yeelight``) because ``info()`` is a
    protocol-layer command — every miio device supports it regardless of
    whether the application layer speaks legacy Yeelight or MIoT.
    """
    try:
        dev = Device(ip=ip, token=token)
        dev.timeout = timeout
        info = dev.info()
        device_id = _extract_device_id(dev)
        return True, f"Connected: {info.model} (firmware {info.firmware_version})", device_id
    except DeviceException as exc:
        return False, f"miio error: {exc}", 0
    except Exception as exc:  # noqa: BLE001 - surface anything else to the user
        return False, f"{type(exc).__name__}: {exc}", 0
