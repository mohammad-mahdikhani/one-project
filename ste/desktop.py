"""Open STE as a standalone desktop window, like an installed website app."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .app import APP

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 5055
URL = f"http://{HOST}:{PORT}"
LOG_FILE = ROOT / "ste-error.log"


def log(message: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        pass


def show_error(message: str) -> None:
    log(message)
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message[:1500], "STE", 0x10)
    except Exception:
        pass


def find_open_port(host: str = HOST, start: int = 5055, count: int = 15) -> int:
    for port in range(start, start + count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
            return port
        except OSError:
            continue
        finally:
            sock.close()
    raise RuntimeError("No free local port for STE")


def start_server(port: int) -> None:
    try:
        APP.run(host=HOST, port=port, debug=False, use_reloader=False, threaded=True)
    except Exception:
        log(traceback.format_exc())


def wait_ready(url: str, seconds: float = 30) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=0.6):
                return True
        except (URLError, OSError):
            time.sleep(0.2)
    return False


def browser_path() -> str | None:
    names = [
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in names:
        if path and os.path.isfile(path):
            return path
    return (
        shutil.which("msedge")
        or shutil.which("chrome")
        or shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )


def app_window_args(browser: str, profile: Path, url: str = URL) -> list[str]:
    return [
        browser,
        f"--app={url}",
        "--window-size=1280,860",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-sync",
        "--disable-infobars",
        "--disable-features=Translate,TranslateUI,ChromeWhatsNewUI",
        "--hide-crash-restore-bubble",
        "--new-window",
    ]


def open_desktop_window(url: str) -> None:
    browser = browser_path()
    profile = ROOT / "app-profile"
    profile.mkdir(exist_ok=True)
    if browser:
        log(f"open app window {browser}")
        try:
            process = subprocess.Popen(app_window_args(browser, profile, url), cwd=str(ROOT))
        except OSError as exc:
            log(f"browser launch failed: {exc}")
            browser = None
        else:
            for _ in range(20):
                time.sleep(0.15)
                if process.poll() is not None:
                    log("browser process exited early; keeping STE open in default browser")
                    browser = None
                    break
            else:
                process.wait()
                return
    log(f"open browser {url}")
    try:
        if sys.platform == "win32":
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            webbrowser.open(url)
    except OSError:
        webbrowser.open(url)
    threading.Event().wait()


def run() -> None:
    global PORT, URL
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    PORT = find_open_port()
    URL = f"http://{HOST}:{PORT}"
    log(f"start STE on {URL}")
    threading.Thread(target=start_server, args=(PORT,), daemon=True).start()
    if not wait_ready(URL):
        raise RuntimeError(
            "STE server did not start. Close old STE windows and run STE.bat again.\n"
            f"Log: {LOG_FILE}"
        )
    open_desktop_window(URL)


def main() -> None:
    try:
        run()
    except Exception:
        text = traceback.format_exc()
        show_error(
            "STE could not start.\n\n"
            f"{text[-900:]}\n\n"
            f"Log file:\n{LOG_FILE}"
        )
        raise SystemExit(1) from None
