#!/usr/bin/env python3
"""Aggregate result of the CI jobs. Reads the `needs` context (JSON) from the RESULTS env var.

A job that was skipped by a path filter counts as fine; anything else that is not `success` fails the gate.
This is the one status check to require on main.
"""
from __future__ import annotations

import json
import os
import sys


def main() -> int:
    needs = json.loads(os.environ["RESULTS"])
    for name, info in needs.items():
        print(f"{name:20s} {info['result']}")
    bad = {name: info["result"] for name, info in needs.items() if info["result"] not in ("success", "skipped")}
    if bad:
        print(f"\nFAILED: {bad}")
        return 1
    print("\nall relevant jobs passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
