"""اجرای آفلاین دفترچی روی ویندوز."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
    if port_open("127.0.0.1", port):
        print(f"دفترچی از قبل روی {url} باز است.")
        webbrowser.open(url)
        return

    import app as appmod

    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    print("دفترچی بدون نیاز به اینترنت روی این سیستم اجرا می‌شود.")
    print(f"آدرس: {url}")
    print("برای توقف، این پنجره را ببندید.")
    print("فروش، انبار، حسابداری، صندوق و لایسنس نقد/کارت آفلاین کار می‌کنند.")
    print("درگاه زیبال، ووکامرس و پیامک اینترنتی فقط وقتی نت وصل باشد کار می‌کنند.")
    appmod.main()


if __name__ == "__main__":
    main()
