"""Moved to pipeline/entries.py on 2026-10-02 (the build ships; tools/mockup does not).
Kept so `from fixtures import ...` in render.py and sweep.py keeps working."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pipeline"))
from entries import *  # noqa: F401,F403
from entries import FIXTURES, build, ENTRIES  # noqa: F401
