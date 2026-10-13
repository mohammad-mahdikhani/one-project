"""Start STE as a desktop app window, not a browser tab."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ste.app import APP

HOST = "127.0.0.1"
PORT = 5055
URL = f"http://{HOST}:{PORT}"


def start_server() -> None:
    APP.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


def wait_ready(seconds: float = 8) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urlopen(URL, timeout=0.4):
                return True
        except (URLError, OSError):
            time.sleep(0.15)
    return False


def browser_path() -> str | None:
    names = [
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in names:
        if path and os.path.isfile(path):
            return path
    return shutil.which("msedge") or shutil.which("chrome")


def open_desktop_window() -> None:
    browser = browser_path()
    profile = ROOT / "app-profile"
    profile.mkdir(exist_ok=True)
    if browser:
        process = subprocess.Popen(
            [
                browser,
                f"--app={URL}",
                "--window-size=1280,860",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            cwd=str(ROOT),
        )
        process.wait()
        return
    webbrowser.open(URL)
    threading.Event().wait()


def main() -> None:
    threading.Thread(target=start_server, daemon=True).start()
    if not wait_ready():
        raise SystemExit("STE server did not start")
    open_desktop_window()


if __name__ == "__main__":
    main()
