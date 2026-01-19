"""
Creador de Videos Virales - Entry Point
"""

import sys
from .pipeline import main

if __name__ == "__main__":
    sys.exit(main() or 0)
