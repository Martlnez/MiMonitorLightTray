"""PyInstaller entry point.

PyInstaller invokes its target file as a top-level script, so the package's
own ``__main__.py`` (which uses relative imports like ``from .config import ...``)
cannot be used directly. This thin wrapper imports the package properly and
delegates to ``main()``.
"""

from __future__ import annotations

import sys

from mi_monitor_light_tray.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
