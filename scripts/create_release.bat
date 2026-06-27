@echo off
REM 一键推送代码并创建 GitHub Release (Windows 版本)
REM 使用方法: scripts\create_release.bat

cd /d "%~dp0\.."

set VERSION=v1.1.0
set EXE_PATH=dist\MiMonitorLightTray.exe
set RELEASE_NOTES=RELEASE_NOTES_v1.1.0.md

echo === Mi Monitor Light Tray Release Script ===
echo Version: %VERSION%
echo.

REM 检查文件是否存在
if not exist "%EXE_PATH%" (
    echo 错误: 找不到 %EXE_PATH%
    echo 请先运行: python scripts\build_exe.py
    exit /b 1
)

if not exist "%RELEASE_NOTES%" (
    echo 错误: 找不到 %RELEASE_NOTES%
    exit /b 1
)

echo 步骤 1: 推送代码到 GitHub
git push origin main
if errorlevel 1 (
    echo.
    echo 推送失败，请检查网络或手动推送：
    echo   git push origin main
    pause
    exit /b 1
)

echo.
echo 步骤 2: 创建 Git Tag
git tag -a "%VERSION%" -m "Release %VERSION% - Major UI/UX improvements" 2>nul
git push origin "%VERSION%"
if errorlevel 1 (
    echo Tag 推送失败，可能已存在，继续...
)

echo.
echo 步骤 3: 创建 GitHub Release
gh release create "%VERSION%" ^
    --title "Mi Monitor Light Tray %VERSION% - Windows 11 Fluent Design" ^
    --notes-file "%RELEASE_NOTES%" ^
    "%EXE_PATH%#MiMonitorLightTray.exe"

if errorlevel 1 (
    echo.
    echo 创建 Release 失败，请手动创建：
    echo   gh release create %VERSION% --notes-file %RELEASE_NOTES% %EXE_PATH%
    pause
    exit /b 1
)

echo.
echo ✓ Release 创建成功！
echo.
echo 查看 Release: https://github.com/Martlnez/MiMonitorLightTray/releases/tag/%VERSION%
echo.
echo 下载链接:
echo   https://github.com/Martlnez/MiMonitorLightTray/releases/download/%VERSION%/MiMonitorLightTray.exe
echo.
pause
