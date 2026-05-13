"""Windows self-update support for cotton-filter."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .build_info import BUILD_VERSION
from .constants import APP_NAME

LATEST_RELEASE_API = "https://api.github.com/repos/zhaodesen/cotton-filter/releases/latest"
WINDOWS_ASSET_NAME = "cotton-filter.exe"
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class UpdateInfo:
    """可安装更新信息。"""

    version: str
    download_url: str
    release_url: str
    digest: str = ""


def can_self_update() -> bool:
    """仅 Windows 打包后的 exe 支持自动替换更新。"""

    return sys.platform.startswith("win") and getattr(sys, "frozen", False)


def current_version() -> str:
    """返回当前构建版本。"""

    return normalize_version(BUILD_VERSION)


def normalize_version(version: str) -> str:
    """统一版本号格式，允许 v1.2.3 和 1.2.3 比较。"""

    cleaned = version.strip()
    if cleaned.lower().startswith("v"):
        cleaned = cleaned[1:]
    return cleaned


def get_update_info() -> UpdateInfo | None:
    """检查 GitHub latest release 是否有 Windows 新版本。"""

    if not can_self_update():
        return None

    version = current_version()
    if version == "dev":
        return None

    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": APP_NAME,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            release = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise RuntimeError(
                "无法访问 GitHub latest release，请确认仓库和 Release 对用户公开"
            ) from error
        raise RuntimeError(f"GitHub 更新接口返回 HTTP {error.code}") from error
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", None) or error
        raise RuntimeError(f"无法连接 GitHub 更新接口: {reason}") from error

    release_version = normalize_version(str(release.get("tag_name", "")))
    if not release_version or release_version == version:
        return None

    for asset in release.get("assets", []):
        if asset.get("name") == WINDOWS_ASSET_NAME:
            download_url = asset.get("browser_download_url")
            if download_url:
                return UpdateInfo(
                    version=release_version,
                    download_url=str(download_url),
                    release_url=str(release.get("html_url", "")),
                    digest=str(asset.get("digest", "")),
                )

    raise RuntimeError(f"最新版本 {release_version} 缺少 Windows 更新文件")


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
    if update.digest:
        validate_digest(target_path, update.digest)

    return target_path


def validate_digest(path: Path, expected_digest: str) -> None:
    """校验 GitHub release asset 摘要。"""

    if not expected_digest.startswith("sha256:"):
        return

    expected = expected_digest.removeprefix("sha256:").lower()
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    actual = digest.hexdigest().lower()
    if actual != expected:
        raise RuntimeError("下载的更新文件校验失败，请重新检查更新")


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
