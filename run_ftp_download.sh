#!/bin/bash

# FTP下载脚本运行器
# 这个脚本会激活Python虚拟环境并运行FTP下载脚本

echo "=== FTP文件下载脚本运行器 ==="
echo ""

# 检查虚拟环境是否存在
VENV_DIR="/Users/heloveyy/Desktop/ftp_download_tools/ftp_download_env"
if [ ! -d "$VENV_DIR" ]; then
    echo "错误: 虚拟环境不存在: $VENV_DIR"
    echo "请先创建虚拟环境: python3 -m venv ftp_download_tools/ftp_download_env"
    exit 1
fi

# 检查Python脚本是否存在
SCRIPT_PATH="/Users/heloveyy/Desktop/ftp_download_tools/download_ftp_files.py"
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "错误: Python脚本不存在: $SCRIPT_PATH"
    exit 1
fi

echo "1. 激活虚拟环境..."
# 使用点号替代source，更兼容
. "$VENV_DIR/bin/activate"

echo "2. 检查Python版本和路径..."
which python
which python3
python --version || python3 --version

echo "3. 检查所需包..."
pip list 2>/dev/null | grep -E "ftplib|zipfile|shutil" || echo "这些是Python标准库中的模块"

echo "4. 运行FTP下载脚本..."
echo "========================================"
python "$SCRIPT_PATH" || python3 "$SCRIPT_PATH"
EXIT_CODE=$?
echo "========================================"

echo "5. 脚本执行完成，退出代码: $EXIT_CODE"

# 停用虚拟环境
deactivate 2>/dev/null || true

echo ""
echo "=== 运行完成 ==="
echo "压缩文件已创建到桌面: 大都会.zip"
echo "要再次运行，请重新执行此脚本"
