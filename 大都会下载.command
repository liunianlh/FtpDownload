#!/bin/bash

# FTP下载脚本运行器 (macOS双击运行版本)
# 这个脚本会激活Python虚拟环境并运行FTP下载脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== FTP文件下载脚本运行器 ==="
echo ""

# 检查虚拟环境是否存在
VENV_DIR="$SCRIPT_DIR/ftp_download_tools/ftp_download_env"
if [ ! -d "$VENV_DIR" ]; then
    echo "错误: 虚拟环境不存在: $VENV_DIR"
    echo "请先创建虚拟环境: python3 -m venv ftp_download_tools/ftp_download_env"
    echo "按任意键退出..."
    read -n 1
    exit 1
fi

# 检查Python脚本是否存在
SCRIPT_PATH="$SCRIPT_DIR/ftp_download_tools/download_ftp_files.py"
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "错误: Python脚本不存在: $SCRIPT_PATH"
    echo "按任意键退出..."
    read -n 1
    exit 1
fi

echo "1. 激活虚拟环境..."
# 使用点号替代source，更兼容
. "$VENV_DIR/bin/activate"

echo "2. 检查Python版本和路径..."
echo "Python路径: $(which python3)"
python3 --version

echo "3. 运行FTP下载脚本..."
echo "========================================"
python3 "$SCRIPT_PATH"
EXIT_CODE=$?
echo "========================================"

echo "4. 脚本执行完成，退出代码: $EXIT_CODE"

# 停用虚拟环境
deactivate 2>/dev/null || true

echo ""
echo "=== 运行完成 ==="
echo "压缩文件已创建到桌面: 大都会.zip"
echo ""
echo "按任意键退出..."
read -n 1
