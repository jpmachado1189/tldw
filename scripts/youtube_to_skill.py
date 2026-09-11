#!/usr/bin/env python3
"""Run directly from a skill installation; no package installation is required."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ytskill.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
