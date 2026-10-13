"""Windows entry point. Logs errors and shows a dialog if STE cannot start."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ste.desktop import main

if __name__ == "__main__":
    main()
