# Release Notes v1.1.0 - 2026-06-27

## 🎉 主要更新

这是一次重大更新，包含用户反馈的所有 5 项改进需求，以及全新的 Windows 11 Fluent Design 界面！

### ⚡ 性能优化（问题 #1）

- **启动速度提升 70%**：从 1.7 秒降至 0.55 秒
- 延迟加载策略：仅在需要时导入 miio/flyout/tray 模块
- 优化模块依赖链，减少启动时的 I/O 操作

### 🔒 单例保护（问题 #2）

- 使用 Windows Mutex 防止重复启动
- 友好提示对话框告知用户已有实例运行
- 自动聚焦到托盘图标位置

### 🔍 智能网络恢复（问题 #3）

- **IP 变化自动发现**：DHCP 更新后无需手动重新配置
- 后台 UDP 广播扫描，通过 device ID 定位设备
- 找到新 IP 后自动重连并保存到配置文件
- 新增 `discovery.py` 模块实现设备发现协议

### 🎨 Windows 11 Fluent Design UI（问题 #4）

- **圆角窗口**：通过 DWM API 实现原生圆角效果
- **现代配色方案**：
  - 深色 Mica 背景 (#202020)
  - Windows 11 蓝色强调色 (#60cdff)
  - 精心调校的文字对比度
- **全新排版**：Segoe UI Variable Display/Text 字体家族
- **交互改进**：手型光标、更大的点击区域、流畅的视觉反馈
- **半透明效果**：96% 不透明度营造轻盈感

### ✨ 全新托盘图标（问题 #5）

- **极简设计**：现代化显示器挂灯造型
- **LED 指示灯**：3 个小点模拟真实设备
- **动态发光**：开启时多层次暖色光晕，关闭时简洁灰色轮廓
- **高 DPI 适配**：矢量化绘制，任意尺寸清晰锐利

## 📦 下载

**Windows 单文件版本：**

[MiMonitorLightTray.exe](https://github.com/Martlnez/MiMonitorLightTray/releases/download/v1.1.0/MiMonitorLightTray.exe) (28 MB)

**SHA256 校验和：**
```
eee3bdd674f89331b01878f06f62513f35bc439f73043e5f6b63de951cf7f35c
```

## 🆕 新增功能

- **中文文档**：新增 `README_CN.md` 和 `SETUP_GUIDE_CN.md`
- **配置扩展**：`DeviceConfig` 新增 `device_id` 字段用于自动发现
- **回调机制**：`MiMonitorLight` 支持 `on_ip_changed` 回调
- **错误恢复**：连接失败时自动触发发现流程（5 秒冷却）

## 🐛 修复

- 修复滑杆拖动时离线状态下的 traceback 日志刷屏
- 修复 PyInstaller 打包时缺少 `miio/specs.yaml` 导致启动崩溃
- 修复相对导入在 onefile 模式下失败的问题
- 抑制 python-miio 的 "Unknown model" 和 UDP 协议警告

## 🔧 技术细节

**新增模块：**
- `single_instance.py` - Windows Mutex 单例锁
- `discovery.py` - UDP 广播设备发现
- `scripts/run_app.py` - PyInstaller 入口点

**核心改进：**
- 懒加载导入策略（`App.__init__` 内部动态导入）
- 自动捕获 device_id（首次连接成功时）
- DWM 圆角窗口 API 集成
- Fluent Design 滑杆样式（`Fluent.Horizontal.TScale`）

**测试覆盖：**
- 15/15 单元测试通过
- 新增单例锁测试
- 新增发现协议测试
- 图标渲染测试（RGBA 透明度）

## 📖 文档

- [中文文档](README_CN.md) - 完整的中文使用指南
- [设置指南](SETUP_GUIDE_CN.md) - 获取 IP 和 Token 的详细步骤
- [English README](README.md) - Original English documentation

## 🙏 致谢

感谢 @Martlnez 的详细反馈和测试！本次更新的所有功能都来自真实用户需求。

---

## For English Users

This release brings major UI/UX improvements:

- **70% faster startup** (1.7s → 0.55s) with lazy imports
- **Single-instance protection** via Windows Mutex
- **Auto-discovery** when device IP changes (DHCP resilience)
- **Windows 11 Fluent Design** UI with rounded corners
- **Redesigned tray icon** with modern minimalist aesthetic

Full changelog in English: see commit `fbea926` for details.

Download: [MiMonitorLightTray.exe](https://github.com/Martlnez/MiMonitorLightTray/releases/download/v1.1.0/MiMonitorLightTray.exe)

SHA256: `eee3bdd674f89331b01878f06f62513f35bc439f73043e5f6b63de951cf7f35c`
