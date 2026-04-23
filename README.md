# FTP Download Tools

从 FTP 服务器批量下载当前目录下的文件，打包为 ZIP，并在完成后清理临时文件夹。面向 macOS，兼顾中文文件名与常见 FTP 编码（如 GBK）。

## 功能概览

- 通过 JSON 配置文件管理 FTP 账号与输出路径（无需改 Python 源码）
- 兼容中文文件名：对 `LIST` 结果按多种编码尝试解码（`gbk` / `gb18030` / `gb2312` / `utf-8` 等）
- 逐个下载到本地临时目录，再压缩为 ZIP
- 压缩完成后删除临时下载目录
- 支持终端运行与 macOS 双击运行（`.command`）

## 目录结构

```text
FtpDownload/
├── README.md
├── 大都会下载.command          # 仓库根目录：双击运行（激活 venv 后执行 Python 脚本）
└── ftp_download_tools/
    ├── download_ftp_files.py   # 主程序：读配置、下载、打包、清理
    ├── ftp_config.example.json # 配置示例（可复制后改名填写）
    ├── ftp_config.local.json   # 本地配置（推荐；已被 .gitignore 忽略）
    ├── ftp_download_env/       # Python 虚拟环境（勿提交）
    └── run_ftp_download.sh     # 可选：终端包装脚本（若内含固定绝对路径，请按本机路径修改）
```

## 运行环境

- macOS
- Python 3.8+
- 可访问目标 FTP 的网络环境

仅使用标准库（`ftplib`、`zipfile`、`json`、`shutil` 等），一般无需安装第三方包。

## 配置说明

程序按以下顺序查找配置文件：

1. 环境变量 `FTP_CONFIG_FILE` 指向的单个文件（若设置）
2. 否则在 `ftp_download_tools/` 下依次尝试：`ftp_config.local.json` → `ftp_config.json`

建议复制示例文件并填写敏感信息：

```bash
cd ftp_download_tools
cp ftp_config.example.json ftp_config.local.json
# 编辑 ftp_config.local.json，填写 host、user、password 与 download 路径等
```

`ftp` 段常用字段：

| 字段 | 说明 |
|------|------|
| `host` | FTP 主机 |
| `user` / `password` | 登录凭据 |
| `encoding` | 连接编码，默认 `gbk`（可按服务器调整） |

`download` 段必填字段：

| 字段 | 说明 |
|------|------|
| `local_dir` | ZIP 与临时目录的父路径（例如桌面路径） |
| `folder_name` | 临时下载文件夹名（下载完成后会删除） |
| `zip_name` | 输出的 ZIP 文件名（含 `.zip` 后缀） |

## 快速开始

### 1) 创建虚拟环境（首次）

在仓库中执行：

```bash
cd ftp_download_tools
python3 -m venv ftp_download_env
```

### 2) 准备配置

按上一节创建并编辑 `ftp_config.local.json`。

### 3) 运行

**方式 A：双击（macOS）**

在 Finder 中双击仓库根目录下的 `大都会下载.command`。

**方式 B：终端**

```bash
cd ftp_download_tools
source ftp_download_env/bin/activate
python3 download_ftp_files.py
deactivate
```

## 输出结果

成功执行后，ZIP 会出现在配置里 `local_dir` 与 `zip_name` 所指定的位置；临时目录为 `local_dir` 下的 `folder_name`，打包完成后会被删除。

## 代码逻辑简述

`download_and_package_ftp_files()` 大致流程：

1. 加载 JSON 配置并校验必填字段  
2. 清空并重建本地临时目录  
3. 连接 FTP（使用配置中的 `encoding`）  
4. 用 `LIST` 的原始字节解析文件列表并解码文件名  
5. 逐个下载（必要时对 UTF-8 文件名切换连接编码）  
6. 校验本地文件与总大小  
7. 写入 ZIP 后删除临时目录  

## 注意事项

- 凭据放在 `ftp_config.local.json` 等本地文件中，勿将含密码的文件提交到公开仓库。  
- 当前逻辑主要针对 FTP **当前目录下的文件**；子目录递归下载需自行扩展。  
- 若文件名仍乱码，可在 `decode_filename()` 中调整编码尝试顺序。

## 常见问题

- **提示未找到配置文件**：确认已创建 `ftp_config.local.json` 或 `ftp_config.json`，或设置 `FTP_CONFIG_FILE`。  
- **虚拟环境不存在**：在 `ftp_download_tools` 下执行 `python3 -m venv ftp_download_env`。  
- **连接失败**：检查主机、账号密码、网络与白名单/防火墙。  
