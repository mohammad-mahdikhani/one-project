"""اجرای آفلاین دفترچی روی ویندوز."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DAFTARCHI_DATA", str(ROOT / "data"))
os.environ.setdefault("PORT", "8080")


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def open_app_window(url: str) -> bool:
    if os.name != "nt":
        return False
    import subprocess

    roots = [
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    names = [
        ("Microsoft\\Edge\\Application\\msedge.exe", roots[:2]),
        ("Google\\Chrome\\Application\\chrome.exe", roots),
    ]
    for relative, bases in names:
        for base in bases:
            if not base:
                continue
            exe = os.path.join(base, relative)
            if os.path.isfile(exe):
                subprocess.Popen(
                    [exe, f"--app={url}", "--new-window"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
    return False


def open_browser(url: str):
    for _ in range(40):
        if port_open("127.0.0.1", int(os.environ["PORT"])):
            if not open_app_window(url):
                webbrowser.open(url)
            return
        time.sleep(0.25)


def running_version(port: int) -> str:
    try:
        import json
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as res:
            return str(json.load(res).get("version") or "")
    except Exception:
        return ""


def stop_port(port: int) -> None:
    if os.name != "nt":
        return
    import subprocess

    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return
    pids = set()
    needle = f":{port}"
    for line in out.splitlines():
        if needle in line and "LISTENING" in line.upper():
            pid = line.split()[-1]
            if pid.isdigit() and pid not in {"0", str(os.getpid())}:
                pids.add(pid)
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    port = int(os.environ.get("PORT", "8080"))
    url = f"http://127.0.0.1:{port}"
    log = Path(os.environ.get("TEMP", str(HERE))) / "daftarchi-run.log"
    try:
        import app as appmod

        if port_open("127.0.0.1", port):
            if running_version(port) == appmod.APP_VERSION:
                print(f"Daftarchi already running at {url}")
                if not open_app_window(url):
                    webbrowser.open(url)
                return
            stop_port(port)
            time.sleep(0.6)
            if port_open("127.0.0.1", port):
                if not open_app_window(url):
                    webbrowser.open(url)
                return

        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
        print("Daftarchi offline mode")
        print(f"URL: {url}")
        print("Login: 09120000000 / daftarchi")
        print("Close this window to stop.")
        appmod.main()
    except Exception:
        text = traceback.format_exc()
        try:
            log.write_text(text, encoding="utf-8")
        except Exception:
            pass
        print(text)
        print(f"Log saved: {log}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
