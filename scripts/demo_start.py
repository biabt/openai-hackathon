#!/usr/bin/env python3
"""Run the local API and portal together, with portable process cleanup."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_APP = os.environ.get("CITY_OS_API_APP", "city_os.api.app:app")
API_PORT = int(os.environ.get("CITY_OS_API_PORT", "8000"))
WEB_PORT = int(os.environ.get("CITY_OS_WEB_PORT", "3000"))


def wait_for(url: str, process: subprocess.Popen[bytes], seconds: int = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"service exited with status {process.returncode}: {url}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError(f"service did not become ready: {url}")


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def start_services() -> list[subprocess.Popen[bytes]]:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    npm = "npm.cmd" if os.name == "nt" else "npm"
    api = subprocess.Popen(
        [sys.executable, "-m", "uv", "run", "--offline", "--project", "backend", "uvicorn", API_APP, "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=ROOT,
        creationflags=creationflags,
    )
    web = subprocess.Popen(
        [npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(WEB_PORT)],
        cwd=ROOT / "frontend",
        creationflags=creationflags,
    )
    return [api, web]


def main() -> None:
    processes = start_services()
    try:
        wait_for(f"http://127.0.0.1:{API_PORT}/api/bootstrap", processes[0])
        wait_for(f"http://127.0.0.1:{WEB_PORT}", processes[1])
        print(f"CityOS offline demo ready at http://127.0.0.1:{WEB_PORT}")
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        raise RuntimeError("a demo service stopped unexpectedly")
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"demo startup failed: {error}") from error
