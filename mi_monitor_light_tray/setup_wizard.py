"""First-run / settings wizard for capturing the device IP and miio token."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from .config import AppConfig, DeviceConfig
from .miio_client import quick_ping

log = logging.getLogger(__name__)

_HELP_TEXT = (
    "How to get the miio token:\n"
    "  - Open the Mi Home app, pair the light, then extract the 32-char\n"
    "    token using a tool such as Xiaomi-cloud-tokens-extractor or\n"
    "    'miiocli cloud' (run 'miiocli cloud --help').\n"
    "  - The IP is the local LAN address shown for the device in the app\n"
    "    or your router.\n"
)


class SetupWizard:
    """Modal-ish settings window. Runs its own Tk root so it works standalone."""

    def __init__(
        self,
        config: AppConfig,
        on_saved: Callable[[AppConfig], None],
        *,
        parent: Optional[tk.Tk] = None,
    ) -> None:
        self._config = config
        self._on_saved = on_saved

        self._owns_root = parent is None
        if parent is None:
            self._root = tk.Tk()
        else:
            self._root = tk.Toplevel(parent)

        self._root.title("Mi Monitor Light — Setup")
        self._root.geometry("420x340")
        self._root.resizable(False, False)

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        frm = ttk.Frame(self._root, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Device IP").grid(row=0, column=0, sticky="w", **pad)
        self._ip_var = tk.StringVar(value=self._config.device.ip)
        ttk.Entry(frm, textvariable=self._ip_var, width=32).grid(row=0, column=1, sticky="ew", **pad)

        ttk.Label(frm, text="miio token").grid(row=1, column=0, sticky="w", **pad)
        self._token_var = tk.StringVar(value=self._config.device.token)
        token_entry = ttk.Entry(frm, textvariable=self._token_var, width=32, show="*")
        token_entry.grid(row=1, column=1, sticky="ew", **pad)

        self._show_token = tk.BooleanVar(value=False)

        def _toggle_show() -> None:
            token_entry.configure(show="" if self._show_token.get() else "*")

        ttk.Checkbutton(
            frm,
            text="Show token",
            variable=self._show_token,
            command=_toggle_show,
        ).grid(row=2, column=1, sticky="w", padx=12)

        ttk.Label(frm, text="Display name").grid(row=3, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar(value=self._config.device.name or "Mi Monitor Light")
        ttk.Entry(frm, textvariable=self._name_var, width=32).grid(row=3, column=1, sticky="ew", **pad)

        ttk.Label(frm, text="Model (optional)").grid(row=4, column=0, sticky="w", **pad)
        self._model_var = tk.StringVar(value=self._config.device.model)
        ttk.Entry(frm, textvariable=self._model_var, width=32).grid(row=4, column=1, sticky="ew", **pad)

        frm.columnconfigure(1, weight=1)

        help_box = tk.Text(
            frm,
            height=6,
            wrap="word",
            background="#f7f7f7",
            relief="flat",
            font=("Segoe UI", 8),
        )
        help_box.insert("1.0", _HELP_TEXT)
        help_box.configure(state="disabled")
        help_box.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 4))

        self._status_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self._status_var, foreground="#555").grid(
            row=6, column=0, columnspan=2, sticky="w", padx=12
        )

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=7, column=0, columnspan=2, sticky="e", pady=(8, 0))

        self._test_btn = ttk.Button(btn_row, text="Test connection", command=self._on_test)
        self._test_btn.pack(side="left", padx=4)

        self._save_btn = ttk.Button(btn_row, text="Save", command=self._on_save)
        self._save_btn.pack(side="left", padx=4)

        ttk.Button(btn_row, text="Cancel", command=self._close).pack(side="left", padx=4)

    # ---------- actions ----------

    def _collect(self) -> DeviceConfig:
        return DeviceConfig(
            ip=self._ip_var.get().strip(),
            token=self._token_var.get().strip(),
            name=self._name_var.get().strip() or "Mi Monitor Light",
            model=self._model_var.get().strip(),
        )

    def _on_test(self) -> None:
        dev = self._collect()
        if not dev.is_complete():
            messagebox.showerror(
                "Invalid input",
                "IP and a 32-character token are both required.",
                parent=self._root,
            )
            return
        self._status_var.set("Testing connection…")
        self._test_btn.configure(state="disabled")
        threading.Thread(target=self._test_thread, args=(dev,), daemon=True).start()

    def _test_thread(self, dev: DeviceConfig) -> None:
        ok, message = quick_ping(dev.ip, dev.token)
        self._root.after(0, lambda: self._after_test(ok, message))

    def _after_test(self, ok: bool, message: str) -> None:
        self._test_btn.configure(state="normal")
        self._status_var.set(message)
        if ok:
            messagebox.showinfo("Connection OK", message, parent=self._root)
        else:
            messagebox.showerror("Connection failed", message, parent=self._root)

    def _on_save(self) -> None:
        dev = self._collect()
        if not dev.is_complete():
            messagebox.showerror(
                "Invalid input",
                "IP and a 32-character token are both required.",
                parent=self._root,
            )
            return
        self._config.device = dev
        try:
            self._config.save()
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self._root)
            return
        self._on_saved(self._config)
        self._close()

    def _close(self) -> None:
        try:
            self._root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        if self._owns_root:
            self._root.mainloop()
