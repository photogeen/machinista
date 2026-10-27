#!/usr/bin/env python3
"""Compatibility launcher; use tools/machinista.py for Machinista."""
from pathlib import Path
import runpy
globals().update(runpy.run_path(str(Path(__file__).with_name('machinista.py')),run_name=__name__))
