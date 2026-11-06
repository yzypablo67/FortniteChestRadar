"""Writable portable data beside the EXE; bundled resources stay inside the bundle."""
import sys
from pathlib import Path

def app_root():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent

def resource_path(name):
    return Path(__file__).resolve().parent/name
