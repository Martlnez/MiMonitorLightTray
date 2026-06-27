# 小米显示器挂灯托盘控制器

一款 Windows 系统托盘应用，用于控制小米/米家显示器挂灯的亮度和色温，采用类似 [Twinkle Tray](https://twinkletray.com/) 的弹出式滑杆设计。基于 [python-miio](https://github.com/rytilahti/python-miio) 构建。

> 支持所有使用标准 Yeelight miio 命令的小米显示器挂灯，如 `yeelink.light.monitor1`、`yeelink.light.monitor2`、`yeelink.light.lamp22` 等型号。

## ✨ 特性

- 🎨 **现代 UI** - Windows 11 Fluent Design 风格，圆角窗口、半透明背景
- ⚡ **快速启动** - 延迟加载优化，启动时间 < 0.6 秒
- 🔒 **单例保护** - 自动阻止重复启动，避免冲突
- 🔍 **智能发现** - IP 变化时自动搜索设备并重新连接
- 🎚️ **实时控制** - 亮度滑杆（1-100%）和色温滑杆（2700K-6500K）
- 🎯 **防抖优化** - 拖动滑杆时自动合并请求，约 150ms 发送一次，流畅无卡顿
- 💾 **持久化配置** - 配置保存在 `%APPDATA%\MiMonitorLightTray\config.json`
- ⚙️ **设置向导** - 内置 IP 和 Token 配置界面，支持连接测试
- 📦 **免安装** - 单文件 EXE，无需 Python 环境

## 📦 安装

### 方式 1: 下载预编译版本（推荐）

从 [Releases](https://github.com/Martlnez/MiMonitorLightTray/releases) 页面下载最新的 `MiMonitorLightTray.exe`，直接运行即可。

### 方式 2: 从源码运行

```bash
# 克隆仓库
git clone https://github.com/Martlnez/MiMonitorLightTray.git
cd MiMonitorLightTray

# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# 运行
python -m mi_monitor_light_tray
```

需要 Python 3.9+。

## 🚀 首次使用

### 1. 获取设备 IP 地址

**方法 A：通过米家 App**
1. 打开米家 App
2. 找到显示器挂灯设备
3. 点击右上角 **⋮** → **设备信息**
4. 记下 IP 地址（如 `192.168.1.100`）

**方法 B：通过路由器**
1. 登录路由器管理页面（通常是 `192.168.1.1`）
2. 查看 **已连接设备** 或 **DHCP 客户端列表**
3. 找到名称包含 `yeelight` 或 `monitor` 的设备

### 2. 获取 miio Token

Token 是 32 位十六进制字符串，用于设备认证。

**推荐工具：[Xiaomi Cloud Tokens Extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)**

```bash
# 下载工具（Windows 用户可下载 .exe 版本）
# 运行后输入小米账号和密码，工具会列出所有设备及其 Token
```

**或使用本项目内置工具：**

```bash
# 进入虚拟环境
cd MiMonitorLightTray
.\.venv\Scripts\activate

# 登录小米云账号
python -m miio.cloud
# 按提示登录，然后会显示所有设备的 Token
```

### 3. 配置并启动

首次运行会自动打开设置向导：

1. **Device IP**：填入设备 IP（如 `192.168.1.100`）
2. **miio token**：填入 32 位 Token（如 `a1b2c3d4...`）
3. **Display name**：随意命名（如"显示器挂灯"）
4. **Model**：留空即可（自动识别）
5. 点击 **Test connection** 测试连接
6. 测试成功后点击 **Save** 保存

## 🎮 使用方法

- **左键点击**托盘图标 → 弹出控制窗口
- 拖动 **Brightness** 滑杆调节亮度（1-100%）
- 拖动 **Color temp** 滑杆调节色温（2700K 暖白 - 6500K 冷白）
- 点击窗口顶部 **On/Off** 按钮开关灯
- 点击窗口外或按 `Esc` 关闭控制窗口
- **右键点击**托盘图标：
  - **Adjust…** - 打开控制窗口
  - **Settings** - 重新配置设备
  - **Exit** - 退出程序

## 🔧 高级功能

### 开机自启动

1. 按 `Win+R` 输入 `shell:startup` 回车
2. 将 `MiMonitorLightTray.exe` 的快捷方式复制到启动文件夹

### IP 地址变化自动恢复

当设备 IP 因 DHCP 租约更新而变化时，程序会：
1. 检测到连接失败
2. 自动在局域网内搜索设备（通过 device ID）
3. 找到新 IP 后自动重连并更新配置

无需手动干预！

### 命令行选项

```bash
# 打开设置向导（即使已有配置）
MiMonitorLightTray.exe --setup

# 启用调试日志
MiMonitorLightTray.exe --debug
```

## 🏗️ 从源码构建

```bash
# 安装构建依赖
pip install -e ".[build]"

# 构建单文件 EXE
python scripts/build_exe.py

# 输出：dist\MiMonitorLightTray.exe
```

## 🧪 运行测试

```bash
pip install -e ".[dev]"
pytest -v
```

测试覆盖配置持久化、图标生成、错误处理、滑杆防抖、单例锁等核心功能。

## 📂 项目结构

```
mi_monitor_light_tray/
  __main__.py           入口，连接托盘、弹窗、配置
  config.py             配置持久化（AppConfig / DeviceConfig）
  miio_client.py        miio 协议封装，包含滑杆防抖和自动发现
  flyout.py             Fluent Design 风格弹窗（Tkinter）
  icon.py               动态生成托盘图标（PIL）
  setup_wizard.py       IP/Token 配置向导，支持连接测试
  tray.py               系统托盘控制器（pystray）
  single_instance.py    单例锁（Windows Mutex）
  discovery.py          UDP 广播设备发现
scripts/
  build_exe.py          PyInstaller 构建脚本
  run_app.py            PyInstaller 入口点
tests/                  pytest 测试套件
```

## 🐛 常见问题

**Q: 提示"Another instance is already running"**  
A: 程序已在运行，检查系统托盘右下角是否有灯条图标。

**Q: 显示"Offline — Unable to discover the device"**  
A: 
- 确认设备已开机并连接到与电脑相同的局域网
- 检查 IP 地址是否正确（可在米家 App 中查看）
- 防火墙可能阻止了 UDP 广播，尝试临时关闭防火墙测试

**Q: 提示"Invalid token"**  
A: Token 可能已过期。重新配对设备到米家 App 后，Token 会刷新，需要重新提取。

**Q: 托盘图标不显示**  
A: Windows 可能隐藏了图标，点击托盘溢出区域（向上箭头）查看。

**Q: 滑杆拖动时灯光变化有延迟**  
A: 这是正常的防抖优化。拖动时每 ~150ms 发送一次命令，避免网络拥塞。

## 🙏 致谢

- [python-miio](https://github.com/rytilahti/python-miio) - miio 协议库
- [Twinkle Tray](https://twinkletray.com/) - UI 设计灵感
- [pystray](https://github.com/moses-palmer/pystray) - 系统托盘支持

## 📄 开源协议

MIT License - 详见 [LICENSE](LICENSE)

---

## English Version

For the English documentation, see [README.md](README.md).
