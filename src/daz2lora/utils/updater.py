from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from daz2lora import VERSION


def _github_repo() -> str:
    from daz2lora.utils.config import AppConfig

    cfg = AppConfig.load()
    return cfg.github_repo or "cognativegames/daz2lora"


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _exe_dir() -> Path:
    return Path(sys.executable).parent if _is_frozen() else Path.cwd()


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "daz2lora-updater"})
    with urllib.request.urlopen(req) as resp:
        dest.write_bytes(resp.read())


def _release_by_tag(repo: str, tag: str) -> Optional[dict]:
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _asset_url(release: dict, suffix: str) -> Optional[str]:
    for a in release.get("assets", []):
        if a["name"].endswith(suffix):
            return a["browser_download_url"]
    return None


def _parse_semver(s: str) -> tuple[int, int, int]:
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", s)
    return tuple(int(g) for g in m.groups()) if m else (0, 0, 0)


class UpdateCheckResult:
    def __init__(
        self, available: bool, latest_version: str = "",
        changelog: str = "", download_url: str = "",
    ) -> None:
        self.available = available
        self.latest_version = latest_version
        self.changelog = changelog
        self.download_url = download_url


def check_for_updates(channel: str = "stable") -> UpdateCheckResult:
    repo = _github_repo()

    if channel == "latest":
        release = _release_by_tag(repo, "latest")
        if release is None:
            return UpdateCheckResult(available=False)
        version = release.get("tag_name", "").lstrip("v")
        changelog = release.get("body", "")
        url = _asset_url(release, ".zip")
        if not url:
            return UpdateCheckResult(available=False)
        return UpdateCheckResult(
            available=True, latest_version=version,
            changelog=changelog, download_url=url,
        )

    # stable — most recent non-prerelease release via GitHub's magic endpoint
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req) as resp:
            release = json.loads(resp.read())
    except Exception:
        return UpdateCheckResult(available=False)

    version = release.get("tag_name", "").lstrip("v")
    changelog = release.get("body", "")
    url = _asset_url(release, ".zip")
    if not url:
        return UpdateCheckResult(available=False)

    if _parse_semver(version) <= _parse_semver(VERSION):
        return UpdateCheckResult(available=False)

    return UpdateCheckResult(
        available=True, latest_version=version,
        changelog=changelog, download_url=url,
    )


def apply_update(result: UpdateCheckResult) -> bool:
    """Download the .zip, replace the running exe, restart.

    Same mechanism for both channels — only the release tag differs.
    """
    exe_dir = _exe_dir()
    zip_path = exe_dir / "update.zip"
    tmp = exe_dir / "update_tmp"

    try:
        _download(result.download_url, zip_path)
        tmp.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)

        script = exe_dir / "apply-update.ps1"
        script.write_text(_SWAP_PS1.format(src=tmp.resolve(), dst=exe_dir.resolve()))
        subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            shell=True,
        )
        return True
    except Exception:
        return False


_SWAP_PS1 = """\
Start-Sleep -Seconds 2
$src = "{src}"
$dst = "{dst}"
$retry = 0
while ($retry -lt 10) {{
    try {{
        Move-Item "$src\\*" "$dst\\" -Force
        Remove-Item "$src" -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item "$dst\\update.zip" -Force -ErrorAction SilentlyContinue
        $exe = Get-ChildItem "$dst\\*.exe" | Select-Object -First 1
        if ($exe) {{ Start-Process $exe.FullName }}
        break
    }} catch {{
        $retry++
        Start-Sleep -Seconds 1
    }}
}}
Remove-Item $MyInvocation.MyCommand.Path -Force
"""
