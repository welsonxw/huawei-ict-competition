from functools import lru_cache
from pathlib import Path

import yaml
from flask import current_app


@lru_cache(maxsize=32)
def _load(path: str):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config(name: str, config_dir: Path | None = None):
    base = Path(config_dir or current_app.config["CONFIG_DIR"])
    return _load(str(base / name))


def thresholds(config_dir=None):
    return load_config("thresholds.yaml", config_dir)


def disease_profiles(config_dir=None):
    data = load_config("disease_profiles.yaml", config_dir)
    defaults = data.get("defaults", {})
    return {(p["crop"], p["disease"]): {**defaults, **p} for p in data["profiles"]}


def regions(config_dir=None):
    return load_config("regions.yaml", config_dir)["regions"]
