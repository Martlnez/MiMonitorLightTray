"""Twinkle Tray-style flyout — one row per control, icon + slider + value."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .miio_client import Debouncer, LightState, MiMonitorLight

log = logging.getLogger(__name__)


class FlyoutWindow:
    WIDTH  = 300
    HEIGHT = 160   # grows with each row at build time
    PAD_X  = 14
    PAD_Y  = 12

    BG          = "#1f1f1f"
    ROW_BG      = "#1f1f1f"
    FOOTER_BG   = "#1f1f1f"
    TEXT        = "#ffffff"
    MUTED       = "#8a8a8a"
    ACCENT      = "#60cdff"      # Win11 blue
    TRACK       = "#3d3d3d"
    ICON_HOVER  = "#3a3a3a"

    def __init__(self, light: MiMonitorLight, on_open_setup: Callable[[], None]) -> None:
        self._light         = light
        self._on_open_setup = on_open_setup

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.configure(bg=self.BG)
        try:
            self._root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        self._apply_rounded_corners()

        self._brightness_debounce = Debouncer(delay=0.12)
        self._color_temp_debounce = Debouncer(delay=0.18)
        self._suppress = False
        self._visible  = False

        self._build_ui()
        self._root.bind("<FocusOut>", self._on_focus_out)
        self._root.bind("<Escape>",   lambda _e: self.hide())

    # ── Win11 rounded corners ────────────────────────────────────────────────

    def _apply_rounded_corners(self) -> None:
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            DWMWCP_ROUND = 2
            val = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(val), 4)
        except Exception:
            pass

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._frame = tk.Frame(self._root, bg=self.BG)
        self._frame.pack(fill="both", expand=True,
                         padx=self.PAD_X, pady=(self.PAD_Y, 8))

        # Slider style
        style = ttk.Style(self._root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TT.Horizontal.TScale",
                         background=self.BG,
                         troughcolor=self.TRACK,
                         sliderlength=16,
                         borderwidth=0,
                         lightcolor=self.ACCENT,
                         darkcolor=self.ACCENT)
        style.map("TT.Horizontal.TScale",
                  background=[("active", self.BG)],
                  troughcolor=[("active", self.TRACK)])

        # ── Device rows ──────────────────────────────────────────────────────
        self._brightness_var  = tk.IntVar(value=50)
        self._color_temp_var  = tk.IntVar(value=4000)

        self._build_device_row(
            icon      = "",          # Segoe MDL2: monitor
            name_var  = None,
            name_text = "显示器挂灯",
            slider_var= self._brightness_var,
            from_     = MiMonitorLight.BRIGHTNESS_MIN,
            to_       = MiMonitorLight.BRIGHTNESS_MAX,
            unit      = "",
            on_change = self._on_brightness,
        )

        self._build_device_row(
            icon      = "",          # Segoe MDL2: brightness / sun
            name_var  = None,
            name_text = "色温",
            slider_var= self._color_temp_var,
            from_     = MiMonitorLight.COLOR_TEMP_MIN,
            to_       = MiMonitorLight.COLOR_TEMP_MAX,
            unit      = "K",
            on_change = self._on_color_temp,
        )

        # ── Footer ───────────────────────────────────────────────────────────
        sep = tk.Frame(self._root, height=1, bg="#2e2e2e")
        sep.pack(fill="x", padx=0)

        footer = tk.Frame(self._root, bg=self.FOOTER_BG)
        footer.pack(fill="x", padx=self.PAD_X, pady=(6, 8))

        self._status_var = tk.StringVar(value="调整亮度")
        tk.Label(footer, textvariable=self._status_var,
                 fg=self.MUTED, bg=self.FOOTER_BG,
                 font=("Segoe UI", 9), anchor="w"
                 ).pack(side="left")

        # Icon buttons on the right (Segoe MDL2 Assets glyphs)
        # 从右到左：设置 > 链接 > 电源
        icons = [
            ("", self._open_settings,    "设置"),       # E713: Settings
            ("", lambda: None,           "链接设备"),    # E710: Link (for future multi-device)
            ("", self._on_toggle_power,  "电源开关"),    # E7E8: Power button
        ]
        for glyph, cmd, tip in reversed(icons):
            self._icon_btn(footer, glyph, cmd)

    def _build_device_row(
        self,
        icon: str,
        name_var: Optional[tk.StringVar],
        name_text: str,
        slider_var: tk.IntVar,
        from_: int,
        to_: int,
        unit: str,
        on_change: Callable[[str], None],
    ) -> None:
        row = tk.Frame(self._frame, bg=self.ROW_BG)
        row.pack(fill="x", pady=(0, 8))

        # Top line: icon + name
        top = tk.Frame(row, bg=self.ROW_BG)
        top.pack(fill="x")

        icon_lbl = tk.Label(top, text=icon,
                            fg=self.MUTED, bg=self.ROW_BG,
                            font=("Segoe MDL2 Assets", 11))
        icon_lbl.pack(side="left")

        name_lbl_text = name_var or tk.StringVar(value=name_text)
        tk.Label(top, textvariable=name_lbl_text,
                 fg=self.TEXT, bg=self.ROW_BG,
                 font=("Segoe UI Variable Text", 10),
                 anchor="w", padx=6,
                 ).pack(side="left", fill="x", expand=True)

        # Bottom line: slider + value
        bot = tk.Frame(row, bg=self.ROW_BG)
        bot.pack(fill="x", pady=(2, 0))

        slider = ttk.Scale(
            bot, from_=from_, to=to_,
            variable=slider_var, orient="horizontal",
            command=on_change,
            style="TT.Horizontal.TScale",
            cursor="hand2",
        )
        slider.pack(side="left", fill="x", expand=True)

        val_var = tk.StringVar(value="--")
        tk.Label(bot, textvariable=val_var,
                 fg=self.TEXT, bg=self.ROW_BG,
                 font=("Segoe UI Variable Display", 13, "bold"),
                 width=5, anchor="e",
                 ).pack(side="right")

        # Sync label
        def _sync(*_, _sv=slider_var, _vv=val_var, _u=unit):
            _vv.set(f"{int(_sv.get())}{_u}")
        slider_var.trace_add("write", _sync)
        _sync()

        if unit == "":
            self._brightness_slider = slider
        else:
            self._color_temp_slider = slider

    def _icon_btn(self, parent: tk.Widget, glyph: str, cmd: Callable) -> tk.Button:
        btn = tk.Label(
            parent, text=glyph,
            fg=self.MUTED, bg=self.FOOTER_BG,
            font=("Segoe MDL2 Assets", 13),
            padx=6, cursor="hand2",
        )
        btn.pack(side="right")
        btn.bind("<Button-1>", lambda _e: cmd())
        btn.bind("<Enter>", lambda _e: btn.configure(fg=self.TEXT))
        btn.bind("<Leave>", lambda _e: btn.configure(fg=self.MUTED))
        return btn

    # ── Thread-safe entry points ─────────────────────────────────────────────

    def schedule_open(self, x: int, y: int) -> None:
        self._root.after(0, lambda: self._open(x, y))

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

    # ── Main thread helpers ──────────────────────────────────────────────────

    def _open(self, x: int, y: int) -> None:
        threading.Thread(target=self._bg_refresh, daemon=True).start()
        self._position(x, y)
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        self._visible = True

    def hide(self) -> None:
        if self._visible:
            self._root.withdraw()
            self._visible = False

    def _on_focus_out(self, _e: tk.Event) -> None:
        if self._root.focus_get() is None:
            self.hide()

    def _position(self, ax: int, ay: int) -> None:
        self._root.update_idletasks()
        w = self._root.winfo_reqwidth()  or self.WIDTH
        h = self._root.winfo_reqheight() or self.HEIGHT
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = max(8, min(sw - w - 8, ax - w // 2))
        y = max(8, min(sh - h - 8, ay - h - 12))
        self._root.geometry(f"{w}x{h}+{x}+{y}")

    def _apply_state(self, state: LightState) -> None:
        self._suppress = True
        try:
            b = max(MiMonitorLight.BRIGHTNESS_MIN, state.brightness or MiMonitorLight.BRIGHTNESS_MIN)
            self._brightness_var.set(b)
            self._color_temp_var.set(state.color_temp or 4000)
        finally:
            self._suppress = False

        if state.reachable:
            self._status_var.set("已连接" if state.is_on else "待机")
        else:
            self._status_var.set(f"离线 — {(state.error or '')[:40]}")

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _bg_refresh(self) -> None:
        state = self._light.refresh()
        self._root.after(0, lambda: self._apply_state(state))

    def _on_brightness(self, v: str) -> None:
        if self._suppress:
            return
        self._brightness_debounce.call(self._light.set_brightness, int(float(v)))

    def _on_color_temp(self, v: str) -> None:
        if self._suppress:
            return
        self._color_temp_debounce.call(self._light.set_color_temp, int(float(v)))

    def _on_toggle_power(self) -> None:
        threading.Thread(target=self._toggle_thread, daemon=True).start()

    def _toggle_thread(self) -> None:
        new = self._light.toggle()
        st  = self._light.state
        self._root.after(0, lambda: self._status_var.set(
            "已连接" if new else "待机"
        ))
        if not st.reachable:
            self._root.after(0, lambda: self._status_var.set(
                f"离线 — {(st.error or '')[:40]}"
            ))

    def _open_settings(self) -> None:
        self.hide()
        self._on_open_setup()
