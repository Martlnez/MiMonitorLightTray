"""Twinkle Tray-style flyout — one row per control, icon + slider + value."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .miio_client import Debouncer, LightState, MiMonitorLight

log = logging.getLogger(__name__)


class _DarkSlider(tk.Canvas):
    """Canvas-based horizontal slider with full dark-mode color control.

    Replaces ttk.Scale which cannot reliably render dark in all Windows themes.
    """

    TRACK_H  = 4
    THUMB_R  = 8
    TRACK_BG = "#3d3d3d"
    TRACK_FG = "#60cdff"
    THUMB_BG = "#60cdff"
    THUMB_HOV= "#9de4ff"

    def __init__(self, parent, from_: int, to: int,
                 variable: tk.IntVar,
                 command: Callable[[str], None],
                 bg: str = "#1f1f1f",
                 **kw) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0,
                         height=20, cursor="hand2", **kw)
        self._from = from_
        self._to   = to
        self._var  = variable
        self._cmd  = command
        self._drag = False

        self._var.trace_add("write", self._redraw)
        self.bind("<Configure>",      self._redraw)
        self.bind("<ButtonPress-1>",  self._on_press)
        self.bind("<B1-Motion>",      self._on_drag)
        self.bind("<ButtonRelease-1>",self._on_release)
        self.bind("<MouseWheel>",     self._on_wheel)
        self.bind("<Enter>",          lambda _: self._redraw(hover=True))
        self.bind("<Leave>",          lambda _: self._redraw(hover=False))
        self._hover = False

    def _frac(self) -> float:
        return (self._var.get() - self._from) / max(1, self._to - self._from)

    def _thumb_x(self) -> int:
        w = self.winfo_width()
        r = self.THUMB_R
        return int(r + self._frac() * (w - 2 * r))

    def _redraw(self, *_, hover: Optional[bool] = None) -> None:
        if hover is not None:
            self._hover = hover
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2:
            return
        cy = h // 2
        r  = self.THUMB_R
        tx = self._thumb_x()

        # Track background
        self.create_rounded_rect(r, cy - self.TRACK_H // 2,
                                  w - r, cy + self.TRACK_H // 2,
                                  2, fill=self.TRACK_BG)
        # Track fill (filled portion)
        if tx > r:
            self.create_rounded_rect(r, cy - self.TRACK_H // 2,
                                      tx, cy + self.TRACK_H // 2,
                                      2, fill=self.TRACK_FG)
        # Thumb
        col = self.THUMB_HOV if self._hover else self.THUMB_BG
        self.create_oval(tx - r, cy - r, tx + r, cy + r,
                         fill=col, outline="")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        r = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
        self.create_polygon(
            x1 + r, y1,  x2 - r, y1,
            x2, y1,      x2, y1 + r,
            x2, y2 - r,  x2, y2,
            x2 - r, y2,  x1 + r, y2,
            x1, y2,      x1, y2 - r,
            x1, y1 + r,  x1, y1,
            smooth=True, **kw)

    def _px_to_val(self, x: int) -> int:
        w = self.winfo_width()
        r = self.THUMB_R
        frac = max(0.0, min(1.0, (x - r) / max(1, w - 2 * r)))
        return int(self._from + frac * (self._to - self._from))

    def _on_press(self, e: tk.Event) -> None:
        self._drag = True
        self._set(self._px_to_val(e.x))

    def _on_drag(self, e: tk.Event) -> None:
        if self._drag:
            self._set(self._px_to_val(e.x))

    def _on_release(self, _e: tk.Event) -> None:
        self._drag = False

    def _on_wheel(self, e: tk.Event) -> None:
        step = 1 if e.delta > 0 else -1
        self._set(max(self._from, min(self._to, self._var.get() + step)))

    def _set(self, val: int) -> None:
        self._var.set(val)
        self._cmd(str(val))
        self._redraw()


class FlyoutWindow:
    WIDTH    = 290
    PAD_X    = 12
    PAD_Y    = 10

    BG       = "#1f1f1f"
    TEXT     = "#ffffff"
    MUTED    = "#8a8a8a"
    ACCENT   = "#60cdff"

    def __init__(self, light: MiMonitorLight,
                 on_open_setup: Callable[[], None]) -> None:
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
        self._brightness_debounce = Debouncer(delay=0.12)
        self._color_temp_debounce = Debouncer(delay=0.18)
        self._suppress = False
        self._visible  = False

        self._build_ui()
        self._root.bind("<FocusOut>", self._on_focus_out)
        self._root.bind("<Escape>",   lambda _e: self.hide())

    # ── rounded corners ──────────────────────────────────────────────────────

    def _apply_rounded_corners(self) -> None:
        try:
            import ctypes
            # winfo_id() gives the embedded frame; GetAncestor(GA_ROOT=2) gets the true top-level HWND
            hwnd = ctypes.windll.user32.GetAncestor(self._root.winfo_id(), 2)
            val  = ctypes.c_int(2)   # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(val), 4)
        except Exception:
            pass

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = tk.Frame(self._root, bg=self.BG)
        outer.pack(fill="x", padx=self.PAD_X, pady=(self.PAD_Y, 0))

        self._brightness_var = tk.IntVar(value=50)
        self._color_temp_var = tk.IntVar(value=4000)

        self._build_row(outer, "", "亮度",
                        self._brightness_var,
                        MiMonitorLight.BRIGHTNESS_MIN,
                        MiMonitorLight.BRIGHTNESS_MAX,
                        "", self._on_brightness)

        self._build_row(outer, "", "色温",
                        self._color_temp_var,
                        MiMonitorLight.COLOR_TEMP_MIN,
                        MiMonitorLight.COLOR_TEMP_MAX,
                        "K", self._on_color_temp)

        # ── Footer ───────────────────────────────────────────────────────────
        tk.Frame(self._root, height=1, bg="#2e2e2e").pack(fill="x")
        footer = tk.Frame(self._root, bg=self.BG)
        footer.pack(fill="x", padx=self.PAD_X, pady=(6, 8))

        self._status_var = tk.StringVar(value="调整亮度")
        tk.Label(footer, textvariable=self._status_var,
                 fg=self.MUTED, bg=self.BG,
                 font=("Segoe UI", 9)).pack(side="left")

        for glyph, cmd in reversed([
            ("⚙", self._open_settings),
            ("⏻", self._on_toggle_power),
        ]):
            self._icon_btn(footer, glyph, cmd)

    def _build_row(self, parent, icon: str, label: str,
                   var: tk.IntVar, from_: int, to: int,
                   unit: str, cmd: Callable) -> None:
        row = tk.Frame(parent, bg=self.BG)
        row.pack(fill="x", pady=(0, 12))

        top = tk.Frame(row, bg=self.BG)
        top.pack(fill="x")
        tk.Label(top, text=icon, fg=self.MUTED, bg=self.BG,
                 font=("Segoe MDL2 Assets", 14)).pack(side="left", padx=(0, 6))
        tk.Label(top, text=label, fg=self.TEXT, bg=self.BG,
                 font=("Microsoft YaHei UI", 11),
                 anchor="w").pack(side="left")

        bot = tk.Frame(row, bg=self.BG)
        bot.pack(fill="x", pady=(4, 0))

        val_var = tk.StringVar(value="--")
        tk.Label(bot, textvariable=val_var, fg=self.TEXT, bg=self.BG,
                 font=("Segoe UI Variable Display", 16, "bold"),
                 width=5, anchor="e").pack(side="right")

        slider = _DarkSlider(bot, from_=from_, to=to,
                             variable=var, command=cmd, bg=self.BG)
        slider.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def _sync(*_, _v=var, _vv=val_var, _u=unit):
            _vv.set(f"{int(_v.get())}{_u}")
        var.trace_add("write", _sync)
        _sync()

        if unit == "":
            self._brightness_slider = slider
        else:
            self._color_temp_slider = slider

    def _icon_btn(self, parent, glyph: str, cmd: Callable) -> None:
        btn = tk.Label(parent, text=glyph, fg=self.MUTED, bg=self.BG,
                       font=("Segoe UI Symbol", 14),
                       padx=6, cursor="hand2")
        btn.pack(side="right")
        btn.bind("<Button-1>", lambda _: cmd())
        btn.bind("<Enter>",    lambda _: btn.configure(fg=self.TEXT))
        btn.bind("<Leave>",    lambda _: btn.configure(fg=self.MUTED))

    # ── thread-safe entry points ──────────────────────────────────────────────

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

    # ── main-thread helpers ───────────────────────────────────────────────────

    def _open(self, x: int, y: int) -> None:
        threading.Thread(target=self._bg_refresh, daemon=True).start()
        self._position(x, y)
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        self._visible = True
        # Apply rounded corners after window is visible (DWM requires the HWND to exist)
        self._apply_rounded_corners()

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
        h = self._root.winfo_reqheight()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x  = max(8, min(sw - w - 8, ax - w // 2))
        y  = max(8, min(sh - h - 8, ay - h - 12))
        self._root.geometry(f"{w}x{h}+{x}+{y}")

    def _apply_state(self, state: LightState) -> None:
        self._suppress = True
        try:
            b = max(MiMonitorLight.BRIGHTNESS_MIN,
                    state.brightness or MiMonitorLight.BRIGHTNESS_MIN)
            self._brightness_var.set(b)
            self._color_temp_var.set(state.color_temp or 4000)
        finally:
            self._suppress = False

        if state.reachable:
            self._status_var.set("已连接" if state.is_on else "待机")
        else:
            self._status_var.set(f"离线 — {(state.error or '')[:40]}")

    # ── callbacks ────────────────────────────────────────────────────────────

    def _bg_refresh(self) -> None:
        state = self._light.refresh()
        self._root.after(0, lambda: self._apply_state(state))

    def _on_brightness(self, v: str) -> None:
        if self._suppress:
            return
        self._brightness_debounce.call(
            self._light.set_brightness, int(float(v)))

    def _on_color_temp(self, v: str) -> None:
        if self._suppress:
            return
        self._color_temp_debounce.call(
            self._light.set_color_temp, int(float(v)))

    def _on_toggle_power(self) -> None:
        threading.Thread(target=self._toggle_thread, daemon=True).start()

    def _toggle_thread(self) -> None:
        new = self._light.toggle()
        st  = self._light.state
        self._root.after(0, lambda: self._status_var.set(
            "已连接" if new else "待机"
            if st.reachable else f"离线 — {(st.error or '')[:40]}"))

    def _open_settings(self) -> None:
        self.hide()
        self._on_open_setup()
