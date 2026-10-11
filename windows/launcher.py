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


def open_browser(url: str):
    for _ in range(40):
        if port_open("127.0.0.1", int(os.environ["PORT"])):
            webbrowser.open(url)
            return
        time.sleep(0.25)


def main():
    port = int(os.environ.get("PORT", "8080"))
    url = f"http://127.0.0.1:{port}"
    log = Path(os.environ.get("TEMP", str(HERE))) / "daftarchi-run.log"
    try:
        if port_open("127.0.0.1", port):
            print(f"Daftarchi already running at {url}")
            webbrowser.open(url)
            return

        import app as appmod

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
