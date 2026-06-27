"""Application entrypoint: wires config, tray icon, flyout, and setup wizard."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import AppConfig
from .flyout import FlyoutWindow
from .miio_client import LightState, MiMonitorLight
from .setup_wizard import SetupWizard
from .tray import TrayController

log = logging.getLogger("mi_monitor_light_tray")


def _quiet_miio_warnings() -> None:
    """Suppress python-miio's noisy startup warnings.

    - ``spec_helper`` warns "Unknown model" for Mi monitor lights even though
      the standard Yeelight commands work for them.
    - ``miioprotocol`` logs every UDP discovery hiccup at WARNING; we already
      surface unreachable devices via state.error, so demote that channel.
    """
    logging.getLogger("miio.integrations.light.yeelight.spec_helper").setLevel(
        logging.ERROR
    )
    logging.getLogger("miio.miioprotocol").setLevel(logging.ERROR)


class App:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._light = self._build_light(config)
        self._flyout = FlyoutWindow(self._light, on_open_setup=self._open_settings)
        self._tray = TrayController(
            title=config.device.name or "Mi Monitor Light",
            on_left_click=self._on_tray_click,
            on_open_settings=self._open_settings,
            on_exit=self._on_exit,
        )
        self._light.set_listener(self._on_state_changed)

    def _build_light(self, config: AppConfig) -> MiMonitorLight:
        return MiMonitorLight(
            ip=config.device.ip,
            token=config.device.token,
            model=config.device.model,
        )

    def run(self) -> int:
        self._tray.start()
        try:
            self._flyout.run()
        finally:
            self._tray.stop()
        return 0

    # ---------- callbacks ----------

    def _on_tray_click(self, x: int, y: int) -> None:
        self._flyout.schedule_open(x, y)

    def _on_state_changed(self, state: LightState) -> None:
        # Called from worker threads — marshal to Tk thread.
        self._flyout.schedule_apply_state(state)
        self._tray.set_state(state.is_on)

    def _open_settings(self) -> None:
        # Tk doesn't allow opening a second Tk root from another thread; route
        # through the flyout's Tk loop with after(0) so the wizard is created
        # on the main thread.
        self._flyout._root.after(0, self._show_settings)

    def _show_settings(self) -> None:
        SetupWizard(
            self._config,
            on_saved=self._on_config_saved,
            parent=self._flyout._root,
        )

    def _on_config_saved(self, config: AppConfig) -> None:
        log.info("Config updated; reconnecting to %s", config.device.ip)
        self._config = config
        self._light = self._build_light(config)
        self._light.set_listener(self._on_state_changed)
        self._flyout._light = self._light
        self._tray.set_title(config.device.name or "Mi Monitor Light")

    def _on_exit(self) -> None:
        self._flyout.shutdown()


def _run_setup_only(config: AppConfig) -> int:
    saved: dict = {}

    def _on_saved(updated: AppConfig) -> None:
        saved["config"] = updated

    wizard = SetupWizard(config, on_saved=_on_saved)
    wizard.run()
    return 0 if saved else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mi-monitor-light-tray")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Open the settings wizard and exit, even if a saved config exists.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _quiet_miio_warnings()

    config = AppConfig.load()

    if args.setup or not config.device.is_complete():
        rc = _run_setup_only(config)
        if rc != 0:
            return rc
        config = AppConfig.load()
        if not config.device.is_complete():
            log.error("Setup not completed; exiting.")
            return 1

    app = App(config)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
