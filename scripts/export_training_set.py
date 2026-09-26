"""Export expert-confirmed scans as folder-per-class training data.

    python scripts/export_training_set.py --out data/exports/training-set [--crop chilli]

Writes <out>/<crop>/<label>/scan_<id>.jpg and <out>/manifest.csv. Retrain with:
    python -m ml.train --data data/chilli --extra data/exports/training-set/chilli --version v2
"""
import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from app import create_app  # noqa: E402
from app.services.review import training_set_zip  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "exports" / "training-set"))
    ap.add_argument("--crop", choices=["chilli", "tomato"])
    args = ap.parse_args()
    with create_app().app_context():
        buf, n = training_set_zip(args.crop)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(buf) as zf:
        zf.extractall(args.out)
    print(f"exported {n} confirmed scans to {args.out}")


if __name__ == "__main__":
    main()
