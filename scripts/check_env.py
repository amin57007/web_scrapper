#!/usr/bin/env python3
"""Verify that the runtime environment can import ulscrape."""

from __future__ import annotations

import sys


def main() -> int:
    if sys.version_info < (3, 11):  # noqa: UP036
        print(f"Python 3.11+ required, found {sys.version}", file=sys.stderr)
        return 1
    try:
        import bs4  # noqa: F401
        import httpx  # noqa: F401
        import pydantic  # noqa: F401
        import typer  # noqa: F401

        from ulscrape import __version__
    except ImportError as exc:
        print(f"missing dependency: {exc}", file=sys.stderr)
        print("run: pip install -r requirements.txt && pip install -e .", file=sys.stderr)
        return 1
    print(f"environment OK  python={sys.version.split()[0]}  ulscrape={__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
