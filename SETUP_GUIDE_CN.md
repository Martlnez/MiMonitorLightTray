# 小米显示器挂灯 - 获取 IP 和 Token 指南

## 方法 1: 通过米家 App 查看 IP 地址

1. 打开 **米家 App**
2. 找到你的 **显示器挂灯** 设备
3. 点击进入设备详情页
4. 右上角 **⋮** (三点) → **设备信息** → 查看 **IP 地址**
   - 例如: `192.168.1.100`

## 方法 2: 通过路由器管理页面查看

1. 登录路由器管理界面 (通常是 `192.168.1.1` 或 `192.168.0.1`)
2. 找到 **已连接设备列表** / **DHCP 客户端列表**
3. 查找名称包含 `yeelight` 或 `monitor` 的设备
4. 记录下它的 IP 地址

## 获取 miio Token

Token 是 32 位的十六进制字符串，需要通过以下工具提取：

### 选项 A: 使用 Xiaomi Cloud Tokens Extractor (推荐)

```bash
# 下载工具
# https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor

# 运行 Python 版本
python token_extractor.py

# 或下载 Windows EXE 版本双击运行
```

按提示输入你的小米账号和密码，工具会列出所有设备的 token。

### 选项 B: 使用本项目自带的 miiocli

```bash
# 进入虚拟环境
cd C:\tool\MiMonitorLightTray
.\.venv\Scripts\activate

# 登录小米云账号
python -m miio.cloud login

# 列出所有设备（包含 token）
python -m miio.cloud devices
```

## 获取到信息后启动程序

运行程序会自动打开设置向导：

```bash
# 方式 1: 运行 Python 版本
.\.venv\Scripts\python.exe -m mi_monitor_light_tray

# 方式 2: 运行 EXE（如果已构建）
.\dist\MiMonitorLightTray.exe
```

在设置向导中填入：
- **Device IP**: `192.168.1.xxx` (你在米家或路由器看到的 IP)
- **miio token**: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (32位十六进制)
- **Display name**: 随意，如 "显示器挂灯"
- **Model**: 留空即可

点击 **Test connection** 测试连接，成功后点 **Save** 保存。

## 手动测试连接（可选）

如果你已经知道 IP 和 token，可以先手动测试：

```python
# 在 Python 中测试
from miio import Yeelight

light = Yeelight(ip="192.168.1.xxx", token="你的32位token")
status = light.status()
print(f"当前状态: {'开' if status.is_on else '关'}")
print(f"亮度: {status.brightness}%")
print(f"色温: {status.color_temp}K")
```
