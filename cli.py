"""Compatibility wrapper for ``python cli.py``."""
from meli_collector.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
