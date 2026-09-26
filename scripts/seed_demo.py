"""Create or clear the "Simulated scenario" demo data.

    python scripts/seed_demo.py           # ~300 simulated scans over 3 weeks
    python scripts/seed_demo.py --clear   # remove them

Everything created is flagged is_simulated = true and labelled "Simulated scenario" in the UI.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from app import create_app  # noqa: E402
from app.services.demo import clear_demo, seed_demo  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clear", action="store_true", help="remove the simulated scenario")
    args = parser.parse_args()
    with create_app().app_context():
        if args.clear:
            print(f"removed {clear_demo()} simulated scans")
        else:
            print(f"created {seed_demo()} simulated scans (Simulated scenario)")


if __name__ == "__main__":
    main()
