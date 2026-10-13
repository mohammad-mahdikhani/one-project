"""Windows launcher that does not depend on python -m."""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ste.app import APP


def main() -> None:
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5055")).start()
    APP.run(host="127.0.0.1", port=5055, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
