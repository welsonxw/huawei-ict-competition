"""Download the tomato ResNet9 weights published in AgriTech (MIT, Om Roy) into ml/weights/.

Usage: python scripts/download_model.py [--force]
Non-fatal: if the download fails, the app falls back to a clearly marked stub prediction.
"""
import os
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://raw.githubusercontent.com/omroy07/AgriTech/main/"
    "Plant%20Disease%20Detection/plant-disease-model.pth"
)
MODEL_DIR = Path(os.getenv("MODEL_DIR", Path(__file__).resolve().parents[1] / "ml" / "weights"))
TARGET = MODEL_DIR / "plant-disease-model.pth"


def main():
    if TARGET.exists() and "--force" not in sys.argv:
        print(f"model already present: {TARGET}")
        return 0
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TARGET.with_suffix(".part")
    try:
        print(f"downloading {URL}")
        urllib.request.urlretrieve(URL, tmp)
        tmp.replace(TARGET)
        print(f"saved {TARGET}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"model download failed ({exc}); the app will use stub predictions", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
