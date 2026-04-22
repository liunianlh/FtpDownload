#!/usr/bin/env python3
"""从 FTP 服务器批量下载文件并打包为 ZIP。

关键设计：把 FTP 连接的 encoding 设为 "latin-1"（单字节、1:1 可逆），
这样无论服务器文件名原始编码是 GBK 还是 UTF-8，都能安全地拿到原始
字节串再在本地按多编码猜测用于显示，同时 RETR 时又能把字符串 1:1
还原成服务器期望的字节，避免了为不同编码反复重连 FTP。
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from ftplib import FTP, all_errors
from pathlib import Path
from typing import Iterable, Iterator

# ---------- 默认配置（可被环境变量 / 命令行参数覆盖） ----------
DEFAULTS = {
    "FTP_HOST": "124.71.204.53",
    "FTP_USER": "huameisftp",
    "FTP_PASS": "huameisftp*&78",
    "LOCAL_DIR": str(Path.home() / "Desktop"),
    "FOLDER_NAME": "大都会",
    "ZIP_NAME": "大都会.zip",
}

DISPLAY_ENCODINGS: tuple[str, ...] = ("gbk", "gb18030", "utf-8")
WIRE_ENCODING = "latin-1"  # FTP 连接编码，保证字节 1:1 可逆
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0

log = logging.getLogger("ftp_download")


# ---------- 数据结构 ----------
@dataclass(frozen=True)
class RemoteFile:
    wire_name: str        # 用 latin-1 解码得到的“线路名”，可直接回传给 FTP
    display_name: str     # 给人看的名字（尽量按 GBK/UTF-8 解码成可读中文）
    size: int


# ---------- 工具函数 ----------
def decode_for_display(raw: bytes) -> str:
    """尽量按常见中文编码解码，仅用于控制台显示和本地文件名。"""
    for enc in DISPLAY_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_list_line(line: bytes) -> RemoteFile | None:
    """解析一行 UNIX 风格 LIST 输出。返回 None 表示忽略此行。"""
    line = line.strip()
    if not line or line.startswith(b"total"):
        return None

    parts = line.split(maxsplit=8)
    if len(parts) < 9:
        return None

    perm = parts[0]
    if perm.startswith(b"d") or perm.startswith(b"l"):
        return None  # 跳过目录和符号链接

    try:
        size = int(parts[4])
    except ValueError:
        return None

    name_raw = parts[8].rstrip(b"\r\n")
    if name_raw in (b".", b".."):
        return None

    return RemoteFile(
        wire_name=name_raw.decode(WIRE_ENCODING),
        display_name=decode_for_display(name_raw).strip(),
        size=size,
    )


def parse_ftp_list(raw: bytes) -> list[RemoteFile]:
    files: list[RemoteFile] = []
    for line in raw.split(b"\r\n"):
        item = parse_list_line(line)
        if item is not None:
            files.append(item)
    return files


def human_size(n: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:,.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{n} B"


# ---------- FTP 交互 ----------
@contextmanager
def ftp_connection(host: str, user: str, password: str) -> Iterator[FTP]:
    ftp = FTP()
    ftp.encoding = WIRE_ENCODING
    ftp.connect(host, timeout=30)
    try:
        ftp.login(user, password)
        yield ftp
    finally:
        try:
            ftp.quit()
        except all_errors:
            ftp.close()


def list_remote_files(ftp: FTP) -> list[RemoteFile]:
    chunks: list[bytes] = []
    ftp.retrbinary("LIST", chunks.append)
    return parse_ftp_list(b"".join(chunks))


class ProgressWriter:
    """包装文件句柄，在 write 时输出单行刷新的进度条。

    仅在 TTY 下启用回车刷新；非交互场景（被重定向/日志文件）下
    退化为“只在显著百分比变化时打印一行”，避免刷屏。
    """

    def __init__(self, fp, total: int, label: str) -> None:
        self._fp = fp
        self._total = max(total, 0)
        self._label = label
        self._written = 0
        self._last_emit = 0.0
        self._last_pct = -1
        self._is_tty = sys.stdout.isatty()

    def write(self, data: bytes) -> int:
        n = self._fp.write(data)
        self._written += len(data)
        self._maybe_emit(final=False)
        return n

    def _maybe_emit(self, final: bool) -> None:
        now = time.monotonic()
        pct = int(self._written * 100 / self._total) if self._total > 0 else 0
        if self._is_tty:
            if final or now - self._last_emit > 0.2:
                self._emit_tty(pct)
                self._last_emit = now
        else:
            # 非 TTY：每 10% 或完成时打印一次
            if final or pct >= self._last_pct + 10:
                self._emit_plain(pct)
                self._last_pct = pct

    def _emit_tty(self, pct: int) -> None:
        if self._total > 0:
            msg = (
                f"  ↳ {self._label}: {human_size(self._written)}"
                f" / {human_size(self._total)} ({pct:3d}%)"
            )
        else:
            msg = f"  ↳ {self._label}: {human_size(self._written)}"
        sys.stdout.write("\r" + msg.ljust(80))
        sys.stdout.flush()

    def _emit_plain(self, pct: int) -> None:
        if self._total > 0:
            log.info(
                "  ↳ %s: %s / %s (%d%%)",
                self._label, human_size(self._written), human_size(self._total), pct,
            )
        else:
            log.info("  ↳ %s: %s", self._label, human_size(self._written))

    def finish(self) -> None:
        self._maybe_emit(final=True)
        if self._is_tty:
            sys.stdout.write("\n")
            sys.stdout.flush()


def download_file(ftp: FTP, remote: RemoteFile, local_path: Path) -> None:
    tmp_path = local_path.with_suffix(local_path.suffix + ".part")
    with open(tmp_path, "wb") as fp:
        writer = ProgressWriter(fp, remote.size, remote.display_name)
        try:
            ftp.retrbinary(f"RETR {remote.wire_name}", writer.write)
        finally:
            writer.finish()
    tmp_path.replace(local_path)


def download_with_retry(
    connect_args: tuple[str, str, str],
    ftp: FTP,
    remote: RemoteFile,
    local_path: Path,
) -> FTP:
    """下载单个文件，失败时重试。必要时重建连接后返回新的 FTP 句柄。"""
    host, user, pwd = connect_args
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            download_file(ftp, remote, local_path)
            return ftp
        except all_errors as err:
            last_err = err
            log.warning(
                "下载 %s 失败（第 %d/%d 次）：%s",
                remote.display_name, attempt, MAX_RETRIES, err,
            )
            try:
                ftp.close()
            except all_errors:
                pass
            if attempt == MAX_RETRIES:
                break
            time.sleep(RETRY_BACKOFF_SEC * attempt)
            ftp = FTP()
            ftp.encoding = WIRE_ENCODING
            ftp.connect(host, timeout=30)
            ftp.login(user, pwd)
    raise RuntimeError(f"重试 {MAX_RETRIES} 次仍无法下载：{remote.display_name}") from last_err


# ---------- 打包 ----------
def create_zip(src_dir: Path, zip_path: Path, base_dir: Path) -> int:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zipf:
        for file_path in sorted(src_dir.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = file_path.relative_to(base_dir)
            zipf.write(file_path, arcname)
            log.info("  + %s", arcname)
    return zip_path.stat().st_size


# ---------- 主流程 ----------
def run(
    host: str,
    user: str,
    password: str,
    local_dir: Path,
    folder_name: str,
    zip_name: str,
    keep_folder: bool,
) -> None:
    target_folder = local_dir / folder_name
    if target_folder.exists():
        log.info("清空已存在的目录：%s", target_folder)
        shutil.rmtree(target_folder)
    target_folder.mkdir(parents=True, exist_ok=True)
    log.info("创建目录：%s", target_folder)

    log.info("连接 FTP %s ...", host)
    with ftp_connection(host, user, password) as ftp:
        log.info("登录成功，拉取文件列表...")
        files = list_remote_files(ftp)
        if not files:
            log.warning("远程目录为空，什么都没下载。")
            return

        total_remote = sum(f.size for f in files)
        log.info("共 %d 个文件，合计 %s", len(files), human_size(total_remote))

        connect_args = (host, user, password)
        for idx, remote in enumerate(files, 1):
            log.info(
                "[%d/%d] %s (%s)",
                idx, len(files), remote.display_name, human_size(remote.size),
            )
            local_path = target_folder / remote.display_name
            ftp = download_with_retry(connect_args, ftp, remote, local_path)

    total_local = sum(p.stat().st_size for p in target_folder.rglob("*") if p.is_file())
    log.info("下载完成，本地总大小 %s", human_size(total_local))

    zip_path = local_dir / zip_name
    log.info("打包 ZIP：%s", zip_path)
    zip_size = create_zip(target_folder, zip_path, local_dir)
    log.info("ZIP 创建完成：%s（%s）", zip_path, human_size(zip_size))

    if not keep_folder:
        shutil.rmtree(target_folder)
        log.info("已清理临时目录：%s", target_folder)

    log.info("✅ 任务完成：共 %d 个文件 → %s", len(files), zip_path)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="从 FTP 下载文件并打包为 ZIP")
    p.add_argument("--host", default=os.environ.get("FTP_HOST", DEFAULTS["FTP_HOST"]))
    p.add_argument("--user", default=os.environ.get("FTP_USER", DEFAULTS["FTP_USER"]))
    p.add_argument("--password", default=os.environ.get("FTP_PASS", DEFAULTS["FTP_PASS"]))
    p.add_argument("--local-dir", default=os.environ.get("FTP_LOCAL_DIR", DEFAULTS["LOCAL_DIR"]))
    p.add_argument("--folder-name", default=os.environ.get("FTP_FOLDER_NAME", DEFAULTS["FOLDER_NAME"]))
    p.add_argument("--zip-name", default=os.environ.get("FTP_ZIP_NAME", DEFAULTS["ZIP_NAME"]))
    p.add_argument("--keep-folder", action="store_true", help="打包后保留下载目录")
    p.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    try:
        run(
            host=args.host,
            user=args.user,
            password=args.password,
            local_dir=Path(args.local_dir).expanduser(),
            folder_name=args.folder_name,
            zip_name=args.zip_name,
            keep_folder=args.keep_folder,
        )
    except KeyboardInterrupt:
        log.error("用户中断。")
        return 130
    except Exception as err:  # noqa: BLE001 — 顶层兜底
        log.error("任务失败：%s", err)
        if args.verbose:
            log.exception("详细堆栈：")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
