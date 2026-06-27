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
    "如何获取 miio Token：\n\n"
    "1. 下载 Xiaomi Cloud Tokens Extractor\n"
    "   https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor/releases\n"
    "   (下载 token_extractor.exe 或 .py 版本)\n\n"
    "2. 运行工具，输入小米账号和密码\n"
    "   工具会列出所有设备的 IP 和 32 位 Token\n\n"
    "3. 找到你的显示器挂灯设备，复制 IP 和 Token 填入下方\n\n"
    "IP 地址也可以从米家 App → 设备详情 → 右上角 ⋮ → 设备信息 中查看\n"
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

        self._root.title("小米显示器挂灯 — 设置")
        self._root.geometry("480x420")
        self._root.resizable(False, False)

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        frm = ttk.Frame(self._root, padding=12)
        frm.pack(fill="both", expand=True)

        # IP 输入框
        ttk.Label(frm, text="设备 IP 地址").grid(row=0, column=0, sticky="w", **pad)
        self._ip_var = tk.StringVar(value=self._config.device.ip)
        ip_entry = ttk.Entry(frm, textvariable=self._ip_var, width=32)
        ip_entry.grid(row=0, column=1, sticky="ew", **pad)

        # IP 提示标签
        ip_hint = ttk.Label(frm, text="从米家 App 或路由器查看，如 192.168.1.100",
                            foreground="#666666", font=("Segoe UI", 8))
        ip_hint.grid(row=0, column=2, sticky="w", padx=(4,0))

        # Token 输入框
        ttk.Label(frm, text="miio Token").grid(row=1, column=0, sticky="w", **pad)
        self._token_var = tk.StringVar(value=self._config.device.token)
        token_entry = ttk.Entry(frm, textvariable=self._token_var, width=32, show="*")
        token_entry.grid(row=1, column=1, sticky="ew", **pad)

        # Token 提示标签
        token_hint = ttk.Label(frm, text="32 位十六进制字符串",
                               foreground="#666666", font=("Segoe UI", 8))
        token_hint.grid(row=1, column=2, sticky="w", padx=(4,0))

        self._show_token = tk.BooleanVar(value=False)

        def _toggle_show() -> None:
            token_entry.configure(show="" if self._show_token.get() else "*")

        ttk.Checkbutton(
            frm,
            text="显示 Token",
            variable=self._show_token,
            command=_toggle_show,
        ).grid(row=2, column=1, sticky="w", padx=12)

        # 设备名称
        ttk.Label(frm, text="显示名称").grid(row=3, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar(value=self._config.device.name or "显示器挂灯")
        name_entry = ttk.Entry(frm, textvariable=self._name_var, width=32)
        name_entry.grid(row=3, column=1, sticky="ew", **pad)

        name_hint = ttk.Label(frm, text="托盘显示的设备名称",
                              foreground="#666666", font=("Segoe UI", 8))
        name_hint.grid(row=3, column=2, sticky="w", padx=(4,0))

        # 型号（可选）
        ttk.Label(frm, text="型号（可选）").grid(row=4, column=0, sticky="w", **pad)
        self._model_var = tk.StringVar(value=self._config.device.model)
        ttk.Entry(frm, textvariable=self._model_var, width=32).grid(row=4, column=1, sticky="ew", **pad)

        model_hint = ttk.Label(frm, text="留空自动识别",
                               foreground="#666666", font=("Segoe UI", 8))
        model_hint.grid(row=4, column=2, sticky="w", padx=(4,0))

        frm.columnconfigure(1, weight=1)

        # 帮助文本框
        help_box = tk.Text(
            frm,
            height=8,
            wrap="word",
            background="#f7f7f7",
            relief="flat",
            font=("Microsoft YaHei UI", 9),
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

        self._test_btn = ttk.Button(btn_row, text="测试连接", command=self._on_test)
        self._test_btn.pack(side="left", padx=4)

        self._save_btn = ttk.Button(btn_row, text="保存", command=self._on_save)
        self._save_btn.pack(side="left", padx=4)

        ttk.Button(btn_row, text="取消", command=self._close).pack(side="left", padx=4)

    # ---------- actions ----------

    def _collect(self) -> DeviceConfig:
        return DeviceConfig(
            ip=self._ip_var.get().strip(),
            token=self._token_var.get().strip(),
            name=self._name_var.get().strip() or "显示器挂灯",
            model=self._model_var.get().strip(),
        )

    def _on_test(self) -> None:
        dev = self._collect()
        if not dev.is_complete():
            messagebox.showerror(
                "输入错误",
                "请填写设备 IP 地址和 32 位 Token",
                parent=self._root,
            )
            return
        self._status_var.set("正在测试连接…")
        self._test_btn.configure(state="disabled")
        threading.Thread(target=self._test_thread, args=(dev,), daemon=True).start()

    def _test_thread(self, dev: DeviceConfig) -> None:
        ok, message = quick_ping(dev.ip, dev.token)
        self._root.after(0, lambda: self._after_test(ok, message))

    def _after_test(self, ok: bool, message: str) -> None:
        self._test_btn.configure(state="normal")
        self._status_var.set(message)
        if ok:
            messagebox.showinfo("连接成功", f"设备在线\n{message}", parent=self._root)
        else:
            messagebox.showerror("连接失败", f"无法连接到设备\n{message}", parent=self._root)

    def _on_save(self) -> None:
        dev = self._collect()
        if not dev.is_complete():
            messagebox.showerror(
                "输入错误",
                "请填写设备 IP 地址和 32 位 Token",
                parent=self._root,
            )
            return
        self._config.device = dev
        try:
            self._config.save()
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self._root)
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
