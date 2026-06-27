"""Twinkle Tray-style flyout window with brightness + color-temp sliders."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .miio_client import Debouncer, LightState, MiMonitorLight

log = logging.getLogger(__name__)


class FlyoutWindow:
    """Borderless Tk window with Windows 11 Fluent Design aesthetics.

    Modern features: rounded corners, acrylic-inspired blur, soft shadows,
    updated color palette matching Windows 11 system UI.
    """

    WIDTH = 340
    HEIGHT = 220
    PAD = 18

    # Windows 11 Fluent Design color palette
    BG_COLOR = "#202020"          # Dark mica background
    CARD_BG = "#2b2b2b"           # Elevated card background
    TEXT_PRIMARY = "#ffffff"      # Primary text
    TEXT_SECONDARY = "#b4b4b4"    # Secondary/muted text
    ACCENT = "#60cdff"            # Windows 11 accent blue
    BORDER = "#3a3a3a"            # Subtle borders
    SLIDER_TRACK = "#404040"      # Slider track
    SLIDER_THUMB = "#ffffff"      # Slider thumb

    def __init__(self, light: MiMonitorLight, on_open_setup: Callable[[], None]) -> None:
        self._light = light
        self._on_open_setup = on_open_setup

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("Mi Monitor Light")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)

        # Windows 11 style: rounded corners and transparency
        try:
            self._root.attributes("-alpha", 0.96)
            # Try to enable rounded corners on Windows 11 (requires Win32 API)
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
                DWM_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWM_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
                    ctypes.sizeof(ctypes.c_int),
                )
            except Exception:
                pass  # Rounded corners not critical, fail silently
        except tk.TclError:
            pass

        self._build_ui()

        self._brightness_debounce = Debouncer(delay=0.12)
        self._color_temp_debounce = Debouncer(delay=0.18)
        self._suppress_callback = False
        self._visible = False

        self._root.bind("<FocusOut>", self._on_focus_out)
        self._root.bind("<Escape>", lambda _e: self.hide())

    # ---------- UI construction ----------

    def _build_ui(self) -> None:
        frame = tk.Frame(self._root, bg=self.BG_COLOR, padx=self.PAD, pady=self.PAD)
        frame.pack(fill="both", expand=True)

        header = tk.Frame(frame, bg=self.BG_COLOR)
        header.pack(fill="x", pady=(0, 8))

        self._title_var = tk.StringVar(value="Mi Monitor Light")
        title_lbl = tk.Label(
            header,
            textvariable=self._title_var,
            fg=self.TEXT_PRIMARY,
            bg=self.BG_COLOR,
            font=("Segoe UI Variable Display", 12, "bold"),
            anchor="w",
        )
        title_lbl.pack(side="left", fill="x", expand=True)

        self._power_btn = tk.Button(
            header,
            text="Off",
            width=6,
            command=self._on_toggle_power,
            relief="flat",
            bg=self.CARD_BG,
            fg=self.TEXT_PRIMARY,
            activebackground=self.ACCENT,
            activeforeground=self.TEXT_PRIMARY,
            borderwidth=0,
            font=("Segoe UI Variable Text", 9),
            cursor="hand2",
        )
        self._power_btn.pack(side="right")

        self._status_var = tk.StringVar(value="")
        status_lbl = tk.Label(
            frame,
            textvariable=self._status_var,
            fg=self.TEXT_SECONDARY,
            bg=self.BG_COLOR,
            font=("Segoe UI Variable Text", 8),
            anchor="w",
        )
        status_lbl.pack(fill="x", pady=(0, 12))

        style = ttk.Style(self._root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Windows 11 inspired slider style
        style.configure(
            "Fluent.Horizontal.TScale",
            background=self.BG_COLOR,
            troughcolor=self.SLIDER_TRACK,
            borderwidth=0,
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
        )
        style.map(
            "Fluent.Horizontal.TScale",
            background=[("active", self.BG_COLOR)],
            troughcolor=[("active", self.SLIDER_TRACK)],
        )

        self._build_slider_row(
            frame,
            label="Brightness",
            from_=MiMonitorLight.BRIGHTNESS_MIN,
            to=MiMonitorLight.BRIGHTNESS_MAX,
            value_attr="_brightness_var",
            slider_attr="_brightness_slider",
            display_attr="_brightness_display",
            on_change=self._on_brightness_change,
            unit="",
        )

        self._build_slider_row(
            frame,
            label="Color temp",
            from_=MiMonitorLight.COLOR_TEMP_MIN,
            to=MiMonitorLight.COLOR_TEMP_MAX,
            value_attr="_color_temp_var",
            slider_attr="_color_temp_slider",
            display_attr="_color_temp_display",
            on_change=self._on_color_temp_change,
            unit="K",
        )

        footer = tk.Frame(frame, bg=self.BG_COLOR)
        footer.pack(fill="x", pady=(12, 0))

        tk.Button(
            footer,
            text="⚙ Settings",
            command=self._open_settings,
            relief="flat",
            bg=self.BG_COLOR,
            fg=self.TEXT_SECONDARY,
            activebackground=self.CARD_BG,
            activeforeground=self.TEXT_PRIMARY,
            borderwidth=0,
            font=("Segoe UI Variable Text", 9),
            cursor="hand2",
        ).pack(side="right")

    def _build_slider_row(
        self,
        parent: tk.Widget,
        *,
        label: str,
        from_: int,
        to: int,
        value_attr: str,
        slider_attr: str,
        display_attr: str,
        on_change: Callable[[str], None],
        unit: str,
    ) -> None:
        row = tk.Frame(parent, bg=self.BG_COLOR)
        row.pack(fill="x", pady=(6, 0))

        tk.Label(
            row,
            text=label,
            fg=self.TEXT_SECONDARY,
            bg=self.BG_COLOR,
            font=("Segoe UI Variable Text", 9),
            anchor="w",
        ).pack(side="left")

        display_var = tk.StringVar(value="--")
        setattr(self, display_attr, display_var)
        tk.Label(
            row,
            textvariable=display_var,
            fg=self.TEXT_PRIMARY,
            bg=self.BG_COLOR,
            font=("Segoe UI Variable Display", 10, "bold"),
            width=6,
            anchor="e",
        ).pack(side="right")

        value_var = tk.IntVar(value=from_)
        setattr(self, value_attr, value_var)

        slider = ttk.Scale(
            parent,
            from_=from_,
            to=to,
            variable=value_var,
            orient="horizontal",
            command=on_change,
            style="Fluent.Horizontal.TScale",
            cursor="hand2",
        )
        slider.pack(fill="x", pady=(2, 8))
        setattr(self, slider_attr, slider)

        # Update label text alongside the slider.
        def _sync(*_args, _var=value_var, _unit=unit, _disp=display_var) -> None:
            _disp.set(f"{int(_var.get())}{_unit}")

        value_var.trace_add("write", _sync)

    # ---------- thread-safe entry points ----------

    def schedule_open(self, x: int, y: int) -> None:
        self._root.after(0, lambda: self._open(x, y))

    def schedule_close(self) -> None:
        self._root.after(0, self.hide)

    def schedule_apply_state(self, state: LightState) -> None:
        self._root.after(0, lambda: self._apply_state(state))

    def shutdown(self) -> None:
        self._brightness_debounce.cancel()
        self._color_temp_debounce.cancel()
        try:
            self._root.after(0, self._root.destroy)
        except tk.TclError:
            pass

    def run(self) -> None:
        self._root.mainloop()

    # ---------- main thread helpers ----------

    def _open(self, x: int, y: int) -> None:
        threading.Thread(target=self._refresh_in_background, daemon=True).start()
        self._position(x, y)
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        self._visible = True

    def hide(self) -> None:
        if not self._visible:
            return
        self._root.withdraw()
        self._visible = False

    def _on_focus_out(self, _event: tk.Event) -> None:
        # Tk fires FocusOut while we still own focus during creation; only hide
        # when no widget of ours has focus.
        if self._root.focus_get() is None:
            self.hide()

    def _position(self, anchor_x: int, anchor_y: int) -> None:
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = anchor_x - self.WIDTH // 2
        y = anchor_y - self.HEIGHT - 16
        x = max(8, min(screen_w - self.WIDTH - 8, x))
        y = max(8, min(screen_h - self.HEIGHT - 8, y))
        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _apply_state(self, state: LightState) -> None:
        self._suppress_callback = True
        try:
            self._brightness_var.set(max(MiMonitorLight.BRIGHTNESS_MIN, state.brightness or MiMonitorLight.BRIGHTNESS_MIN))
            self._color_temp_var.set(state.color_temp or 4000)
        finally:
            self._suppress_callback = False

        self._power_btn.configure(text="On" if state.is_on else "Off")
        if state.reachable:
            self._status_var.set("Connected" if state.is_on else "Standby")
        else:
            self._status_var.set(f"Offline — {state.error or 'unreachable'}")

    # ---------- callbacks ----------

    def _refresh_in_background(self) -> None:
        state = self._light.refresh()
        self._root.after(0, lambda: self._apply_state(state))

    def _on_brightness_change(self, _value: str) -> None:
        if self._suppress_callback:
            return
        target = int(float(_value))
        self._brightness_debounce.call(self._light.set_brightness, target)

    def _on_color_temp_change(self, _value: str) -> None:
        if self._suppress_callback:
            return
        target = int(float(_value))
        self._color_temp_debounce.call(self._light.set_color_temp, target)

    def _on_toggle_power(self) -> None:
        threading.Thread(target=self._toggle_thread, daemon=True).start()

    def _toggle_thread(self) -> None:
        new_state = self._light.toggle()
        state = self._light.state
        self._root.after(0, lambda: self._power_btn.configure(text="On" if new_state else "Off"))
        if not state.reachable:
            self._root.after(0, lambda: self._status_var.set(f"Offline — {state.error or 'unreachable'}"))

    def _open_settings(self) -> None:
        self.hide()
        self._on_open_setup()
