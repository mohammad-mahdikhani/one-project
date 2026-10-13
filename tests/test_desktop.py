from pathlib import Path

from ste.desktop import URL, app_window_args


def test_app_window_uses_standalone_chrome_flags():
    args = app_window_args("/usr/bin/google-chrome", Path("/tmp/ste-profile"))
    assert args[1] == f"--app={URL}"
    assert "--disable-infobars" in args
    assert any(item.startswith("--user-data-dir=") for item in args)
