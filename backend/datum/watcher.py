"""Datum filesystem watcher — stub for Task 8 implementation.

This module exists so docker-compose's `python -m datum.watcher` command
doesn't fail with ModuleNotFoundError. The real implementation is Task 8.
"""
import sys


def main():
    print("datum-watcher: stub — real implementation in Task 8", file=sys.stderr)
    print("datum-watcher: waiting for implementation...", file=sys.stderr)
    # Block so the container doesn't exit-loop
    import time
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
