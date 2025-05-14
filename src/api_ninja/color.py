import os


class Colors:
    ENABLED = os.getenv("APININJA_COLOR", "0") == "1"

    RED = "\033[91m" if ENABLED else ""
    YELLOW = "\033[93m" if ENABLED else ""
    CYAN = "\033[96m" if ENABLED else ""
    BOLD = "\033[1m" if ENABLED else ""
    RESET = "\033[0m" if ENABLED else ""
