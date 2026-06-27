"""PyInstaller helper: produces a single-file Windows binary for the tray app.

Run from the project root with the dev/build extras installed:

    pip install -e ".[build]"
    python scripts/build_exe.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "mi_monitor_light_tray" / "__main__.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def main() -> int:
    if shutil.which("pyinstaller") is None:
        print("pyinstaller is not installed. Run: pip install -e \".[build]\"", file=sys.stderr)
        return 1

    cmd = [
        "pyinstaller",
        "--name",
        "MiMonitorLightTray",
        "--onefile",
        "--noconsole",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        str(ENTRY),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
