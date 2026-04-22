# FTP Download Tools

一个用于从 FTP 服务器批量下载文件并自动打包为 ZIP 的小工具，适配 macOS 使用场景。

## 功能概览

- 连接 FTP 服务器并读取目录文件列表
- 兼容中文文件名编码（优先尝试 `gbk` / `gb18030` / `utf-8` 等）
- 按文件逐个下载到本地临时目录
- 自动压缩为 `大都会.zip`
- 压缩完成后自动清理临时下载目录
- 支持脚本运行与 macOS 双击运行

## 目录结构

```text
ftp_download_tools/
├── download_ftp_files.py      # 主程序：下载 + 压缩 + 清理
├── run_ftp_download.sh        # 终端运行脚本（激活虚拟环境后执行）
└── ftp_download_env/          # Python 虚拟环境目录
```

仓库根目录还有：

- `大都会下载.command`：macOS 双击运行入口（适合非命令行用户）

## 运行环境

- macOS
- Python 3.8+
- 可访问目标 FTP 服务器的网络环境

该项目主要依赖 Python 标准库（`ftplib`、`zipfile`、`shutil` 等），一般不需要额外安装第三方包。

## 快速开始

### 1) 创建虚拟环境（首次）

在仓库根目录执行：

```bash
python3 -m venv ftp_download_tools/ftp_download_env
```

### 2) 运行方式

#### 方式 A：终端执行

```bash
cd ftp_download_tools
./run_ftp_download.sh
```

#### 方式 B：双击执行（macOS）

在 Finder 中双击仓库根目录下的 `大都会下载.command`。

## 输出结果

脚本执行成功后会在桌面生成：

- `大都会.zip`

流程中会临时创建下载目录（默认 `~/Desktop/大都会`），压缩完成后自动删除临时目录。

## 主要配置（在 `download_ftp_files.py` 顶部）

- `FTP_HOST`：FTP 主机地址
- `FTP_USER`：FTP 用户名
- `FTP_PASS`：FTP 密码
- `LOCAL_DIR`：本地输出目录（默认桌面）
- `FOLDER_NAME`：临时下载目录名
- `ZIP_NAME`：输出压缩包文件名

如需迁移到其他环境，优先修改上述常量即可。

## 代码逻辑说明

`download_and_package_ftp_files()` 主流程：

1. 初始化并清理本地临时目录
2. 连接 FTP（默认按 `gbk` 编码）
3. 使用 `LIST` 原始二进制结果解析文件列表
4. 多编码尝试解码文件名，确保中文文件可读
5. 下载所有文件（必要时用 UTF-8 连接重试）
6. 校验下载结果并统计总大小
7. 打包压缩为 ZIP
8. 删除临时目录并输出最终结果

## 注意事项

- 当前脚本将 FTP 凭据明文写在代码中，仅建议在受控内网或个人环境中使用。
- 如果计划共享仓库，建议改为环境变量读取账号密码，避免泄露敏感信息。
- 若 FTP 目录包含子目录，当前实现主要按“文件列表”下载；如需递归下载，可在后续版本扩展。

## 常见问题

- **虚拟环境不存在**：先执行创建命令 `python3 -m venv ftp_download_tools/ftp_download_env`
- **连接失败**：确认 FTP 地址、账号密码、网络白名单与防火墙策略
- **文件名乱码**：可在 `decode_filename()` 里调整编码尝试顺序

