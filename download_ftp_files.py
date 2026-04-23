#!/usr/bin/env python3
import ftplib
import json
import os
import sys
import zipfile
import shutil

SCRIPT_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.environ.get("FTP_CONFIG_FILE")
DEFAULT_CONFIG_FILES = [
    os.path.join(SCRIPT_DIR, "ftp_config.local.json"),
    os.path.join(SCRIPT_DIR, "ftp_config.json"),
]

def load_config():
    """从配置文件加载FTP与下载参数"""
    config_file = CONFIG_FILE
    if config_file:
        candidate_files = [config_file]
    else:
        candidate_files = DEFAULT_CONFIG_FILES
        config_file = next((path for path in candidate_files if os.path.exists(path)), None)

    if not config_file or not os.path.exists(config_file):
        raise FileNotFoundError(
            "未找到配置文件。请创建 ftp_config.local.json，或复制 ftp_config.example.json 为 ftp_config.local.json 后填写。"
        )

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    ftp_config = config.get("ftp", {})
    download_config = config.get("download", {})

    required_ftp_keys = ["host", "user", "password"]
    missing_ftp_keys = [k for k in required_ftp_keys if not ftp_config.get(k)]
    if missing_ftp_keys:
        raise ValueError(f"配置文件缺少FTP字段: {', '.join(missing_ftp_keys)}")

    required_download_keys = ["local_dir", "folder_name", "zip_name"]
    missing_download_keys = [k for k in required_download_keys if not download_config.get(k)]
    if missing_download_keys:
        raise ValueError(f"配置文件缺少下载字段: {', '.join(missing_download_keys)}")

    ftp_config.setdefault("encoding", "gbk")
    return ftp_config, download_config

def decode_filename(raw_bytes, encodings=['gbk', 'gb18030', 'gb2312', 'utf-8', 'latin1']):
    """尝试多种编码解码文件名"""
    for encoding in encodings:
        try:
            decoded = raw_bytes.decode(encoding)
            # 检查是否包含有效的中文字符或其他有效字符
            if len(decoded) > 0 and not all(ord(c) < 32 for c in decoded if c != '\n' and c != '\r'):
                return decoded, encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode('utf-8', errors='ignore'), 'utf-8-ignore'

def parse_ftp_list(raw_data):
    """解析FTP LIST命令返回的原始数据，提取文件信息"""
    files = []
    lines = raw_data.split(b'\r\n')

    for line in lines:
        line = line.strip()
        if not line or line.startswith(b'total'):
            continue

        # 解析文件列表行（格式：权限 链接数 所有者 组 大小 日期 时间 文件名）
        parts = line.split()
        if len(parts) < 9:
            continue

        # 提取文件大小和原始文件名
        try:
            size = int(parts[4])
            # 文件名是从第9部分开始（可能有空格）
            filename_raw = b' '.join(parts[8:])

            # 尝试解码文件名
            filename_decoded, encoding = decode_filename(filename_raw)
            filename_decoded = filename_decoded.strip()

            # 排除目录
            if filename_decoded not in ['.', '..']:
                files.append({
                    'filename': filename_decoded,
                    'filename_raw': filename_raw,
                    'size': size,
                    'encoding': encoding
                })
        except Exception as e:
            print(f"解析文件行失败: {line}, 错误: {e}")
            continue

    return files

def download_and_package_ftp_files():
    """连接到FTP服务器，下载所有文件，并打包压缩"""
    try:
        ftp_config, download_config = load_config()
        ftp_host = ftp_config["host"]
        ftp_user = ftp_config["user"]
        ftp_pass = ftp_config["password"]
        ftp_encoding = ftp_config["encoding"]
        local_dir = download_config["local_dir"]
        folder_name = download_config["folder_name"]
        zip_name = download_config["zip_name"]

        # 创建目标文件夹
        target_folder = os.path.join(local_dir, folder_name)
        if os.path.exists(target_folder):
            print(f"文件夹 '{folder_name}' 已存在，清空内容...")
            shutil.rmtree(target_folder)
        os.makedirs(target_folder, exist_ok=True)
        print(f"创建文件夹: {target_folder}")
        
        # 连接到FTP服务器
        print(f"正在连接到FTP服务器 {ftp_host}...")
        ftp = ftplib.FTP()
        ftp.encoding = ftp_encoding
        ftp.connect(ftp_host)
        ftp.login(ftp_user, ftp_pass)
        print("连接成功！")

        # 获取文件列表（使用二进制模式获取，避免编码问题）
        print("获取文件列表...")

        # 使用 LIST 命令的原始二进制数据
        data = []
        ftp.retrbinary('LIST', data.append)
        raw_list = b''.join(data)

        # 解析文件列表
        files_info = parse_ftp_list(raw_list)

        print(f"找到 {len(files_info)} 个文件:")
        for file_info in files_info:
            print(f"  - {file_info['filename']} ({file_info['size']} 字节) [{file_info['encoding']}]")

        # 下载每个文件到目标文件夹
        downloaded_files = []
        for file_info in files_info:
            filename_local = file_info['filename']
            encoding = file_info['encoding']
            local_path = os.path.join(target_folder, filename_local)

            print(f"正在下载: {filename_local} ({file_info['size']} 字节)")

            try:
                with open(local_path, 'wb') as f:
                    # 对于GBK编码的文件，使用当前的GBK连接
                    if encoding == 'gbk':
                        ftp.retrbinary(f'RETR {filename_local}', f.write)
                        downloaded_files.append(local_path)
                        print(f"  下载完成: {filename_local}")
                    else:
                        # 对于UTF-8编码的文件，重新建立连接
                        print(f"  检测到UTF-8编码，重新建立连接...")
                        ftp.close()

                        ftp_utf8 = ftplib.FTP()
                        ftp_utf8.encoding = 'utf-8'
                        ftp_utf8.connect(ftp_host)
                        ftp_utf8.login(ftp_user, ftp_pass)
                        ftp_utf8.retrbinary(f'RETR {filename_local}', f.write)
                        ftp_utf8.close()

                        # 重新建立GBK连接以便后续文件
                        ftp = ftplib.FTP()
                        ftp.encoding = ftp_encoding
                        ftp.connect(ftp_host)
                        ftp.login(ftp_user, ftp_pass)

                        downloaded_files.append(local_path)
                        print(f"  下载完成: {filename_local}")
            except Exception as e:
                print(f"  下载失败 {filename_local}: {e}")

        # 关闭FTP连接
        ftp.quit()
        print("所有文件下载完成！")

        # 验证下载的文件
        print("\n下载的文件列表:")
        total_size = 0
        for file_info in files_info:
            filename = file_info['filename']
            local_path = os.path.join(target_folder, filename)
            if os.path.exists(local_path):
                size = os.path.getsize(local_path)
                total_size += size
                print(f"  - {filename} ({size} 字节)")
            else:
                print(f"  - {filename} (未找到)")
        
        print(f"总大小: {total_size} 字节")
        
        # 创建ZIP压缩文件
        print(f"\n正在创建压缩文件: {zip_name}")
        zip_path = os.path.join(local_dir, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(target_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 在ZIP文件中保持相对路径
                    arcname = os.path.relpath(file_path, local_dir)
                    zipf.write(file_path, arcname)
                    print(f"  添加: {arcname}")
        
        zip_size = os.path.getsize(zip_path)
        print(f"压缩文件创建完成: {zip_path} ({zip_size} 字节)")
        
        # 清理：删除临时文件夹（可选）
        print(f"\n清理临时文件夹: {target_folder}")
        shutil.rmtree(target_folder)
        print("临时文件夹已删除")
        
        # 最终结果
        print(f"\n✅ 任务完成！")
        print(f"   从FTP服务器下载了 {len(files_info)} 个文件")
        print(f"   创建了压缩文件: {zip_name} ({zip_size} 字节)")
        print(f"   文件位置: {zip_path}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    download_and_package_ftp_files()
