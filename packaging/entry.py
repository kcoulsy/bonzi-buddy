"""PyInstaller entry point. Imports the package so relative imports resolve."""

import sys

from bonzi.app import main

if __name__ == "__main__":
    sys.exit(main())
