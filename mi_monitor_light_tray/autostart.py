"""Windows launch-at-startup toggle via the user Run registry key.

The user-scope ``Run`` key needs no admin rights and runs the program on logon
for the current user only. The Windows registry is the source of truth; we
don't mirror this into config.json to avoid drift if the user edits the entry
manually.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MiMonitorLightTray"


def _executable_command() -> str | None:
    """Return the quoted command Windows should run on logon, or None if we
    can't sensibly autostart (e.g., running from source without a wrapper)."""
    # PyInstaller-bundled EXE: sys.frozen is set and sys.executable points at it.
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Source run: launch via pythonw -m so no console window appears.
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else exe
    return f'"{runner}" -m mi_monitor_light_tray'


def is_enabled() -> bool:
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.debug("Reading autostart key failed: %s", exc)
        return False


def enable() -> bool:
    """Register the current executable to launch on user logon. Returns success."""
    try:
        import winreg
    except ImportError:
        return False
    cmd = _executable_command()
    if not cmd:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, cmd)
        log.info("Autostart enabled: %s", cmd)
        return True
    except OSError as exc:
        log.warning("Enable autostart failed: %s", exc)
        return False


def disable() -> bool:
    """Remove the Run entry. Returns success (also True if it was already absent)."""
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        log.info("Autostart disabled")
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        log.warning("Disable autostart failed: %s", exc)
        return False


def toggle() -> bool:
    """Flip the current state; returns the new state."""
    if is_enabled():
        disable()
        return False
    enable()
    return is_enabled()
