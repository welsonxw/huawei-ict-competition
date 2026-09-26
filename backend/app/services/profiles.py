from ..extensions import db
from ..models import DiseaseProfile
from .config_loader import disease_profiles


def seed_profiles():
    """Upsert disease_profiles rows from config/disease_profiles.yaml."""
    for (crop, disease), p in disease_profiles().items():
        row = DiseaseProfile.query.filter_by(crop=crop, disease=disease).one_or_none() or DiseaseProfile(crop=crop, disease=disease)
        row.name_en = p["name"]["en"]
        row.name_ms = p["name"]["ms"]
        row.spread_mode = p["spread_mode"]
        row.weather_model = p["weather_model"]
        row.temp_min = p.get("temp_min")
        row.temp_max = p.get("temp_max")
        row.moisture = p.get("moisture")
        row.advice_type = p["advice_type"]
        row.spread_radius_km = p["spread_radius_km"]
        row.report_decay_days = p["report_decay_days"]
        row.source_refs = p.get("source_refs")
        db.session.add(row)
    db.session.commit()


def get_profile(crop, disease):
    row = DiseaseProfile.query.filter_by(crop=crop, disease=disease).one_or_none()
    if row:
        return row.to_dict()
    p = disease_profiles().get((crop, disease))
    return p


def display_name(crop, disease, lang="en"):
    if disease == "healthy":
        return {"en": "Healthy", "ms": "Sihat"}[lang]
    p = get_profile(crop, disease)
    return p["name"][lang] if p else disease.replace("_", " ").capitalize()
