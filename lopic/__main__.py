"""lopic entry point: `python -m lopic` or via start.bat"""

import sys

from .app import run

if __name__ == "__main__":
    sys.exit(run())