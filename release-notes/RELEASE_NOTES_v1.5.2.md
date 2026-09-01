# v1.5.2

## 🐛 关键修复 · 稳定性补丁

v1.5.2 是 **v1.5.1 休眠恢复大改之后**的稳定性修复版，集中解决了 v1.5.1 上线后发现的两个严重 Bug：并发字典迭代导致的偶发崩溃，以及冷启动时托盘图标状态不刷新的问题。同时优化了 CI Release 流程，并完成了 GitHub 用户名从 `Martlnez` → `awakaze` 的迁移。

## 🐛 Bug 修复

### 1. 字典并发 re-key 崩溃（#Critical）

**触发路径**：冷启动 model 为空的设备在首次连接成功后，`_on_model_resolved` 会对 `_lights` 字典做原地 re-key（`_lights[new_id] = _lights.pop(old_id)`）。此时 Flyout 的 `_open` / `_bg_refresh_all` / `_any_on` / `_on_toggle_all` 以及 `App._on_state_changed` 都在用 live dict view 遍历 `items()` / `values()`。CPython 迭代器在版本戳变更时抛出 `RuntimeError: dictionary changed size during iteration`，UI 回调未捕获，会导致弹窗渲染中断或进程退出。

**修复**：5 处 `_lights` 遍历统一改为 `list(self._lights.items())` / `list(self._lights.values())` 快照。

**新增测试**：`tests/test_concurrency_regressions.py`（4 passed · 1 skipped），覆盖：
- list() 快照在高并发 re-key 压力下不崩溃
- `MonitorSleepListener.stop()` 必须等待旧线程完全退出
- 异常消息泵不会导致调用者死锁
- 包含阳性对照用例（未打补丁时 live dict view 必抛 RuntimeError）

### 2. MonitorSleepListener 重启后双回调 → 唤醒不复原

**触发路径**：`_restart_power_listener` 会先 `stop()` 旧监听器再启动新的。旧实现里 `stop()` 只 `PostMessage(WM_CLOSE)` 就返回，没有 `join` 旧窗口线程。新监听器立即创建后，新旧两个 HWND 会**同时**订阅 `PBT_POWERSETTINGCHANGE`，同一个显示器关闭事件会触发两次 `on_monitor_sleep`：第二次调用读到 `state.is_on=False`（灯已经关了），覆盖了 pre_sleep_state。于是 on_monitor_wake 认为睡前就是关的，直接跳过恢复供电 —— 用户表现为「显示器息屏再点亮，灯不会自动恢复」。

**修复**：`stop()` 对窗口线程执行 `join(timeout=3.0)`；异常消息泵加 3s 安全帽，超时仅记录 warning 不会死锁调用者。

### 3. 灯启动时托盘图标没有变亮

**触发路径**：程序刚启动时托盘图标默认设为「暗（关）」，之后通过状态回调翻转。但初始化路径里存在状态推送窗口过早创建 / 事件顺序错乱导致的图标不刷新问题 —— 即使灯实际已经是开的，托盘图标依旧是暗色，直到第一次手动点弹窗才刷新。

**修复**：[__main__.py](mi_monitor_light_tray/__main__.py) 重构了启动时的状态推送流程，确保灯的初始状态完整传递后再刷新托盘图标聚合态。

## 🔧 工程与基础设施

### CI Release 自动读取 Release Notes

`.github/workflows/build.yml` 的 Release Job 现在会自动从 `release-notes/RELEASE_NOTES_<tag>.md` 读取 Markdown 内容作为 GitHub Release Body，不再需要手工粘贴。tag 名与文件名严格按 `v1.5.2` ↔ `RELEASE_NOTES_v1.5.2.md` 对应。

## 🧭 账号迁移

- GitHub 用户名已从 **Martlnez** 变更为 **awakaze**
- 仓库地址：`https://github.com/awakaze/MiMonitorLightTray`
- 所有源码、配置、文档、Release Notes 中的旧 URL 均已同步更新
- GitHub Pages 站点：`https://awakaze.github.io/MiMonitorLightTray/`

## 对比

[v1.5.1 → v1.5.2 完整变更](https://github.com/awakaze/MiMonitorLightTray/compare/v1.5.1...v1.5.2)
