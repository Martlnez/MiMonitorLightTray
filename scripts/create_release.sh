#!/bin/bash
# 一键推送代码并创建 GitHub Release
# 使用方法: bash scripts/create_release.sh

set -e

cd "$(dirname "$0")/.."

VERSION="v1.1.0"
EXE_PATH="dist/MiMonitorLightTray.exe"
RELEASE_NOTES="RELEASE_NOTES_v1.1.0.md"

echo "=== Mi Monitor Light Tray Release Script ==="
echo "Version: $VERSION"
echo ""

# 检查文件是否存在
if [ ! -f "$EXE_PATH" ]; then
    echo "错误: 找不到 $EXE_PATH"
    echo "请先运行: python scripts/build_exe.py"
    exit 1
fi

if [ ! -f "$RELEASE_NOTES" ]; then
    echo "错误: 找不到 $RELEASE_NOTES"
    exit 1
fi

echo "步骤 1: 推送代码到 GitHub"
git push origin main || {
    echo "推送失败，请检查网络连接或手动推送："
    echo "  git push origin main"
    exit 1
}

echo ""
echo "步骤 2: 创建 Git Tag"
git tag -a "$VERSION" -m "Release $VERSION - Major UI/UX improvements" || {
    echo "Tag 已存在，跳过..."
}
git push origin "$VERSION" || {
    echo "Tag 推送失败，请手动推送："
    echo "  git push origin $VERSION"
}

echo ""
echo "步骤 3: 创建 GitHub Release"
gh release create "$VERSION" \
    --title "Mi Monitor Light Tray $VERSION - Windows 11 Fluent Design" \
    --notes-file "$RELEASE_NOTES" \
    "$EXE_PATH#MiMonitorLightTray.exe" || {
    echo "创建 Release 失败，请手动创建："
    echo "  gh release create $VERSION --notes-file $RELEASE_NOTES $EXE_PATH"
    exit 1
}

echo ""
echo "✅ Release 创建成功！"
echo ""
echo "查看 Release: https://github.com/Martlnez/MiMonitorLightTray/releases/tag/$VERSION"
echo ""
echo "下载链接:"
echo "  https://github.com/Martlnez/MiMonitorLightTray/releases/download/$VERSION/MiMonitorLightTray.exe"
