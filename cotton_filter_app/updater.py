"""Windows self-update support for cotton-filter."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .build_info import BUILD_COMMIT
from .constants import APP_NAME

LATEST_RELEASE_API = "https://api.github.com/repos/zhaodesen/cotton-filter/releases/latest"
WINDOWS_ASSET_NAME = "cotton-filter.exe"
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class UpdateInfo:
    """可安装更新信息。"""

    commit: str
    download_url: str
    release_url: str


def can_self_update() -> bool:
    """仅 Windows 打包后的 exe 支持自动替换更新。"""

    return sys.platform.startswith("win") and getattr(sys, "frozen", False)


def current_commit() -> str:
    """返回当前构建 commit。"""

    return BUILD_COMMIT.strip()


def find_release_commit(body: str) -> str | None:
    """从 release body 中提取构建 commit。"""

    match = re.search(r"commit\s+([0-9a-f]{7,40})", body, re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def get_update_info() -> UpdateInfo | None:
    """检查 GitHub latest release 是否有 Windows 新版本。"""

    if not can_self_update():
        return None

    commit = current_commit()
    if commit == "dev":
        return None

    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": APP_NAME,
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        release = json.loads(response.read().decode("utf-8"))

    release_commit = find_release_commit(str(release.get("body", "")))
    if not release_commit or release_commit.startswith(commit) or commit.startswith(release_commit):
        return None

    for asset in release.get("assets", []):
        if asset.get("name") == WINDOWS_ASSET_NAME:
            download_url = asset.get("browser_download_url")
            if download_url:
                return UpdateInfo(
                    commit=release_commit,
                    download_url=str(download_url),
                    release_url=str(release.get("html_url", "")),
                )

    return None


def download_update(update: UpdateInfo) -> Path:
    """下载新版 exe 到临时目录。"""

    target_dir = Path(tempfile.mkdtemp(prefix="cotton-filter-update-"))
    target_path = target_dir / WINDOWS_ASSET_NAME
    request = urllib.request.Request(
        update.download_url,
        headers={"User-Agent": APP_NAME},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        with target_path.open("wb") as output:
            shutil.copyfileobj(response, output)

    if target_path.stat().st_size <= 0:
        raise RuntimeError("下载的更新文件为空")

    return target_path


def install_update_and_restart(downloaded_exe: Path) -> None:
    """启动临时 PowerShell 更新脚本并退出当前程序。"""

    current_exe = Path(sys.executable).resolve()
    script_path = downloaded_exe.with_suffix(".ps1")
    script = f"""
$ErrorActionPreference = "Stop"
$source = "{_escape_powershell(str(downloaded_exe))}"
$target = "{_escape_powershell(str(current_exe))}"
$backup = "$target.bak"
$pidToWait = {os.getpid()}
Wait-Process -Id $pidToWait -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
if (Test-Path $backup) {{ Remove-Item $backup -Force }}
if (Test-Path $target) {{ Move-Item $target $backup -Force }}
Move-Item $source $target -Force
Start-Process $target
Start-Sleep -Seconds 2
if (Test-Path $backup) {{ Remove-Item $backup -Force }}
Remove-Item $MyInvocation.MyCommand.Path -Force
"""
    script_path.write_text(script, encoding="utf-8")
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script_path),
        ],
        close_fds=True,
    )


def _escape_powershell(value: str) -> str:
    """转义 PowerShell 双引号字符串。"""

    return value.replace("`", "``").replace('"', '`"')
