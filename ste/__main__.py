import threading
import webbrowser

from .app import APP


def main() -> None:
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5055")).start()
    APP.run(host="127.0.0.1", port=5055, debug=False)


if __name__ == "__main__":
    main()
