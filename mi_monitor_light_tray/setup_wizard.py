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
        self._root.geometry("520x480")
        self._root.resizable(False, False)
        self._root.configure(bg="#f0f0f0")

        # Apply modern styling
        style = ttk.Style()
        style.theme_use('vista' if 'vista' in style.theme_names() else 'clam')
        style.configure('TLabel', background='#f0f0f0', font=('Microsoft YaHei UI', 9))
        style.configure('TEntry', padding=6)
        style.configure('TButton', padding=(12, 6))

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 16, "pady": 10}

        frm = ttk.Frame(self._root, padding=20)
        frm.pack(fill="both", expand=True)
        frm.configure(style='TFrame')

        # Title
        title_lbl = ttk.Label(frm, text="设备配置",
                              font=("Microsoft YaHei UI", 12, "bold"))
        title_lbl.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))

        # IP 输入框
        ttk.Label(frm, text="设备 IP 地址", font=("Microsoft YaHei UI", 9)).grid(
            row=1, column=0, sticky="w", **pad)
        self._ip_var = tk.StringVar(value=self._config.device.ip)
        ip_entry = ttk.Entry(frm, textvariable=self._ip_var, width=28, font=("Consolas", 10))
        ip_entry.grid(row=1, column=1, sticky="ew", **pad)

        # IP 提示标签
        ip_hint = ttk.Label(frm, text="如: 192.168.1.100",
                            foreground="#666666", font=("Microsoft YaHei UI", 8))
        ip_hint.grid(row=2, column=1, sticky="w", padx=16, pady=(0, 8))

        # Token 输入框
        ttk.Label(frm, text="miio Token", font=("Microsoft YaHei UI", 9)).grid(
            row=3, column=0, sticky="w", **pad)
        self._token_var = tk.StringVar(value=self._config.device.token)
        token_entry = ttk.Entry(frm, textvariable=self._token_var, width=28,
                                show="*", font=("Consolas", 9))
        token_entry.grid(row=3, column=1, sticky="ew", **pad)

        # Token 提示标签
        token_hint = ttk.Label(frm, text="32 位十六进制字符串",
                               foreground="#666666", font=("Microsoft YaHei UI", 8))
        token_hint.grid(row=4, column=1, sticky="w", padx=16, pady=(0, 8))

        self._show_token = tk.BooleanVar(value=False)

        def _toggle_show() -> None:
            token_entry.configure(show="" if self._show_token.get() else "*")

        ttk.Checkbutton(
            frm,
            text="显示 Token",
            variable=self._show_token,
            command=_toggle_show,
        ).grid(row=5, column=1, sticky="w", padx=16, pady=(0, 10))

        # 设备名称
        ttk.Label(frm, text="显示名称", font=("Microsoft YaHei UI", 9)).grid(
            row=6, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar(value=self._config.device.name or "显示器挂灯")
        name_entry = ttk.Entry(frm, textvariable=self._name_var, width=28,
                               font=("Microsoft YaHei UI", 10))
        name_entry.grid(row=6, column=1, sticky="ew", **pad)

        name_hint = ttk.Label(frm, text="托盘显示的设备名称",
                              foreground="#666666", font=("Microsoft YaHei UI", 8))
        name_hint.grid(row=7, column=1, sticky="w", padx=16, pady=(0, 8))

        # 型号（可选）
        ttk.Label(frm, text="型号（可选）", font=("Microsoft YaHei UI", 9)).grid(
            row=8, column=0, sticky="w", **pad)
        self._model_var = tk.StringVar(value=self._config.device.model)
        ttk.Entry(frm, textvariable=self._model_var, width=28,
                  font=("Consolas", 9)).grid(row=8, column=1, sticky="ew", **pad)

        model_hint = ttk.Label(frm, text="留空自动识别",
                               foreground="#666666", font=("Microsoft YaHei UI", 8))
        model_hint.grid(row=9, column=1, sticky="w", padx=16, pady=(0, 12))

        frm.columnconfigure(1, weight=1)

        # 分隔线
        sep = ttk.Separator(frm, orient="horizontal")
        sep.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(12, 8))

        # 帮助文本框
        help_label = ttk.Label(frm, text="如何获取参数？",
                               font=("Microsoft YaHei UI", 9, "bold"))
        help_label.grid(row=11, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 4))

        help_box = tk.Text(
            frm,
            height=7,
            wrap="word",
            background="#f9f9f9",
            relief="solid",
            borderwidth=1,
            font=("Microsoft YaHei UI", 9),
            padx=8,
            pady=8,
        )
        help_box.insert("1.0", _HELP_TEXT)
        help_box.configure(state="disabled")
        help_box.grid(row=12, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 12))

        # 状态标签
        self._status_var = tk.StringVar(value="")
        status_lbl = ttk.Label(frm, textvariable=self._status_var,
                               foreground="#0066cc", font=("Microsoft YaHei UI", 9))
        status_lbl.grid(row=13, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

        # 按钮行
        btn_row = ttk.Frame(frm)
        btn_row.grid(row=14, column=0, columnspan=2, sticky="e", pady=(12, 0), padx=16)

        ttk.Button(btn_row, text="取消", command=self._close).pack(side="left", padx=4)
        self._test_btn = ttk.Button(btn_row, text="测试连接", command=self._on_test)
        self._test_btn.pack(side="left", padx=4)
        self._save_btn = ttk.Button(btn_row, text="保存", command=self._on_save, style='Accent.TButton')
        self._save_btn.pack(side="left", padx=4)

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
