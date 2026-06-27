"""Single-instance lock using a named mutex on Windows.

Prevents multiple instances of the app from running simultaneously by holding
a system-wide named mutex for the lifetime of the process.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

log = logging.getLogger(__name__)

# Windows API constants
ERROR_ALREADY_EXISTS = 183

# Load kernel32.dll functions
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CreateMutexW = kernel32.CreateMutexW
CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
CreateMutexW.restype = wintypes.HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


class SingleInstance:
    """System-wide single-instance lock.

    Usage:
        lock = SingleInstance("MyApp")
        if not lock.acquired:
            print("Another instance is already running")
            sys.exit(1)
        # ... run app ...
        lock.release()  # optional; auto-released on process exit
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._mutex_name = f"Global\\{name}"
        self._handle = None
        self._acquired = False
        self._try_acquire()

    def _try_acquire(self) -> None:
        self._handle = CreateMutexW(None, False, self._mutex_name)
        if self._handle == 0:
            log.error("CreateMutexW failed")
            return
        last_error = ctypes.get_last_error()
        if last_error == ERROR_ALREADY_EXISTS:
            log.info("Another instance is already running (mutex exists)")
            CloseHandle(self._handle)
            self._handle = None
            self._acquired = False
        else:
            log.debug("Acquired single-instance mutex")
            self._acquired = True

    @property
    def acquired(self) -> bool:
        return self._acquired

    def release(self) -> None:
        if self._handle is not None:
            CloseHandle(self._handle)
            self._handle = None
            self._acquired = False
            log.debug("Released single-instance mutex")

    def __del__(self) -> None:
        self.release()
