import json
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


def fertiliser_products(config_dir=None):
    return load_config("fertiliser_products.yaml", config_dir)["products"]


def crop_requirements(config_dir=None):
    return load_config("crop_requirements.yaml", config_dir)


def tomcast_table(config_dir=None):
    return load_config("tomcast_table.yaml", config_dir)


def demo_scenario(config_dir=None):
    return load_config("demo_scenario.yaml", config_dir)


def production(config_dir=None):
    return load_config("production.yaml", config_dir)


def damage_functions(config_dir=None):
    return load_config("damage_functions.yaml", config_dir)


@lru_cache(maxsize=4)
def _load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def state_boundaries(config_dir=None):
    base = Path(config_dir or current_app.config["CONFIG_DIR"])
    return _load_json(str(base / "malaysia_states.geojson"))
