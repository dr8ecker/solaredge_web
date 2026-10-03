# Copyright (c) 2026 8ecker.de
"""Local process, browser, successful scrape and MQTT health snapshot."""

import argparse
import json
import os
import time
from pathlib import Path

from .config import Config
from .files import write_private_json


class HealthManager:
    def __init__(self, config: Config):
        self.path = config.data_dir / "health.json"
        self.snapshot = {
            "pid": os.getpid(), "started_at": time.time(),
            "heartbeat_at": time.time(), "last_page_success": None,
            "last_scrape_success": None, "mqtt_connected": None,
            "browser_connected": False, "consecutive_failures": 0,
            "max_retries": config.max_retries,
            "max_age_seconds": config.health_max_age,
            "heartbeat_max_age": max(150, config.page_timeout // 1000 * 2 + 30),
            "phase": config.mode, "status": "starting",
        }

    def update(self, **values) -> None:
        self.snapshot.update(values, heartbeat_at=time.time())
        write_private_json(self.path, self.snapshot)


def process_alive(pid: int) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    # Windows os.kill(pid, 0) sends a console event; it is not a read-only
    # existence check. Query the process handle for local development instead.
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == 259
    finally:
        kernel.CloseHandle(handle)


def healthy(path: Path, *, now: float | None = None) -> bool:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        now = time.time() if now is None else now
        if not process_alive(snapshot["pid"]):
            return False
        if now - snapshot["heartbeat_at"] > snapshot.get("heartbeat_max_age", 150):
            return False
        if snapshot["status"] == "offline":
            return False
        # Startup grace covers the first slow DNS/page/browser attempt.
        success = snapshot['last_scrape_success'] if snapshot.get('phase') == 'normal' else snapshot['last_page_success']
        if snapshot.get('phase') == 'normal' and snapshot['mqtt_connected'] is False and now - snapshot['started_at'] >= 300:
            return False
        if success is None:
            return now - snapshot["started_at"] < 300
        if not snapshot["browser_connected"]:
            return False
        age = now - success
        return age <= snapshot["max_age_seconds"] or (
            snapshot["consecutive_failures"] < snapshot["max_retries"]
            and age <= snapshot["max_age_seconds"] * 2
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("/data/runtime"))
    args = parser.parse_args()
    return 0 if healthy(args.data_dir / "health.json") else 1


if __name__ == "__main__":
    raise SystemExit(main())
