#!/usr/bin/env python3
"""
Thin wrapper that reuses the watcher in wifi.py.
Keeps the reset listener in sync with the main automation logic.
"""
from wifi import check_for_reset_command


if __name__ == "__main__":
    check_for_reset_command()
