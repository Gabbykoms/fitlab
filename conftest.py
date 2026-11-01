"""Pytest configuration.

Puts the project root on ``sys.path`` so the test modules can import the
project's own modules (``critique``, ``weather``, ``db``, ``generator``)
without the project needing to be installed as a package.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
