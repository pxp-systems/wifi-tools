#!/usr/bin/env python3
"""
Legacy entrypoint kept for compatibility; delegates to wifi.py run_once().
"""
from wifi import run_once


if __name__ == "__main__":
    run_once()
