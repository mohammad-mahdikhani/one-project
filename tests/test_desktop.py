from pathlib import Path

from ste.desktop import URL, app_window_args, find_open_port


def test_app_window_uses_standalone_chrome_flags():
    args = app_window_args("/usr/bin/google-chrome", Path("/tmp/ste-profile"), "http://127.0.0.1:5055")
    assert args[1] == "--app=http://127.0.0.1:5055"
    assert "--disable-infobars" in args
    assert "--new-window" in args
    assert any(item.startswith("--user-data-dir=") for item in args)


def test_find_open_port_returns_bindable_port():
    port = find_open_port(start=5055, count=15)
    assert 5055 <= port < 5070
