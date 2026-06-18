"""Run the full Make-Room-for-SF pipeline end to end.

    uv run main.py            # pull (if missing) -> transit -> filter -> model -> export
    uv run main.py --force    # re-pull all raw inputs first

Individual steps live in scripts/ and can be run on their own; see README.md.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

STEPS = [
    "scripts/pull_data.py",
    "scripts/compute_transit.py",
    "scripts/filter_candidates.py",
    "scripts/economic_model.py",
    "scripts/export_site_data.py",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="force re-pull of raw data")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    for step in STEPS:
        print(f"\n{'='*70}\n# {step}\n{'='*70}")
        argv = [step]
        if step.endswith("pull_data.py") and args.force:
            argv.append("--force")
        sys.argv = argv
        runpy.run_path(str(root / step), run_name="__main__")


if __name__ == "__main__":
    main()
