"""Smart fertiliser: cheapest mix of at most N products that meets N, P2O5, K2O within tolerance (LP)."""
import math
from itertools import combinations

import numpy as np
from scipy.optimize import linprog

from ..extensions import db
from ..models import CropRequirement, FertiliserProduct
from .config_loader import crop_requirements, fertiliser_products, thresholds
from .nutrients import to_oxide

NUTRIENTS = ("n", "p2o5", "k2o")
STAGES = ("seedling", "vegetative", "flowering", "fruiting")
LEVELS = ("low", "medium", "high")

NUTRIENT_NAMES = {
    "en": {"n": "nitrogen", "p2o5": "phosphorus", "k2o": "potassium"},
    "ms": {"n": "nitrogen", "p2o5": "fosforus", "k2o": "kalium"},
}
STAGE_NAMES = {
    "en": {"seedling": "Seedling", "vegetative": "Vegetative", "flowering": "Flowering", "fruiting": "Fruiting"},
    "ms": {"seedling": "Anak benih", "vegetative": "Vegetatif", "flowering": "Berbunga", "fruiting": "Berbuah"},
}
CROP_NAMES = {"en": {"chilli": "Chilli", "tomato": "Tomato"}, "ms": {"chilli": "Cili", "tomato": "Tomato"}}

TEXT = {
    "en": {
        "headline": "{crop} – {stage} stage. Recommended: {products}.",
        "product": "{name}, {kg} kg for your plot",
        "why": "Why: {reasons}.",
        "soil_low": "your {nutrient} is low",
        "stage_need": "{stage} plants need more {nutrient}",
        "balanced": "this mix matches the nitrogen, phosphorus and potassium your crop needs at this stage",
        "infeasible": "No mix of up to {max} products supplies nitrogen, phosphorus and potassium each within ±{tol}%. "
        "Closest option: {products} ({gaps}).",
        "gap": "{nutrient} {sign}{pct}%",
        "lime": "Soil pH {ph} is below {min}. Apply lime (e.g. ground magnesium limestone) 1–2 weeks before planting, "
        "and not together with chemical fertiliser.",
        "alkaline": "Soil pH {ph} is above {max}. Do not apply lime; ask your DOA office for a soil test and advice.",
        "ph_ok": "Soil pH {ph} is within the recommended range ({min}–{max}).",
        "ph_unknown_range": "The recommended pH range for {crop} is not configured yet (TODO: DOA source).",
        "deficiency": "Your latest scan of this plot suggests nutrient deficiency – a soil test is recommended.",
        "previous": "You reported previous fertiliser: {previous}. If it was applied recently, reduce the amount and "
        "confirm with a soil test.",
    },
    "ms": {
        "headline": "{crop} – peringkat {stage}. Disyorkan: {products}.",
        "product": "{name}, {kg} kg untuk plot anda",
        "why": "Sebab: {reasons}.",
        "soil_low": "{nutrient} dalam tanah anda rendah",
        "stage_need": "pokok peringkat {stage} memerlukan lebih banyak {nutrient}",
        "balanced": "campuran ini sepadan dengan keperluan nitrogen, fosforus dan kalium tanaman anda pada peringkat ini",
        "infeasible": "Tiada campuran sehingga {max} produk yang membekalkan nitrogen, fosforus dan kalium dalam "
        "lingkungan ±{tol}%. Pilihan terdekat: {products} ({gaps}).",
        "gap": "{nutrient} {sign}{pct}%",
        "lime": "pH tanah {ph} di bawah {min}. Tabur kapur (cth. kapur magnesium) 1–2 minggu sebelum menanam, "
        "dan bukan bersama baja kimia.",
        "alkaline": "pH tanah {ph} melebihi {max}. Jangan tabur kapur; minta pejabat DOA membuat ujian tanah dan nasihat.",
        "ph_ok": "pH tanah {ph} berada dalam julat yang disyorkan ({min}–{max}).",
        "ph_unknown_range": "Julat pH yang disyorkan untuk {crop} belum ditetapkan (TODO: sumber DOA).",
        "deficiency": "Imbasan terkini plot ini menunjukkan kekurangan nutrien – ujian tanah disyorkan.",
        "previous": "Anda melaporkan baja sebelum ini: {previous}. Jika baru ditabur, kurangkan jumlah dan sahkan "
        "dengan ujian tanah.",
    },
}


class FertiliserError(ValueError):
    pass


# ---------- seed / load ----------

def seed_fertiliser():
    """Insert products and requirements from config if missing. Existing rows are kept (they may be edited)."""
    for p in fertiliser_products():
        if not FertiliserProduct.query.filter_by(name=p["name"]).one_or_none():
            db.session.add(FertiliserProduct(
                name=p["name"], n=p["n"], p2o5=p["p2o5"], k2o=p["k2o"], mgo=p.get("mgo", 0),
                price_rm_per_kg=p.get("price_rm_per_kg"),
            ))
    for crop, c in crop_requirements()["crops"].items():
        for stage, req in c["stages"].items():
            if not CropRequirement.query.filter_by(crop=crop, stage=stage).one_or_none():
                ox = to_oxide(req, c.get("form", "oxide"))
                db.session.add(CropRequirement(
                    crop=crop, stage=stage, is_placeholder=bool(c.get("placeholder", True)), source=c.get("source"), **ox,
                ))
    db.session.commit()


def load_products():
    rows = FertiliserProduct.query.filter_by(active=True).order_by(FertiliserProduct.id).all()
    if rows:
        return [r.to_dict() for r in rows]
    return [dict(p) for p in fertiliser_products()]


def load_requirement(crop, stage):
    row = CropRequirement.query.filter_by(crop=crop, stage=stage).one_or_none()
    if row:
        return row.to_dict()
    c = crop_requirements()["crops"][crop]
    return {**to_oxide(c["stages"][stage], c.get("form", "oxide")), "is_placeholder": c.get("placeholder", True),
            "source": c.get("source")}


def stage_requirements(crop):
    return {s: load_requirement(crop, s) for s in STAGES}


# ---------- optimiser ----------

def _price(p):
    return p["price_rm_per_kg"] if p.get("price_rm_per_kg") is not None else 1.0


def _matrix(combo, nutrients):
    return np.array([[p[n] / 100.0 for p in combo] for n in nutrients])


def _solve_combo(combo, req, tol):
    """Cheapest amounts (kg/ha) for this product combo with each required nutrient within ±tol. None if infeasible."""
    nutrients = [n for n in NUTRIENTS if req[n] > 0]
    a = _matrix(combo, nutrients)
    r = np.array([req[n] for n in nutrients])
    res = linprog(
        c=[_price(p) for p in combo],
        A_ub=np.vstack([a, -a]),
        b_ub=np.concatenate([(1 + tol) * r, -(1 - tol) * r]),
        bounds=[(0, None)] * len(combo),
        method="highs",
    )
    return res.x if res.status == 0 else None


def _closest_combo(combo, req):
    """Minimise the largest relative deviation t over required nutrients. Returns (t, amounts)."""
    nutrients = [n for n in NUTRIENTS if req[n] > 0]
    a = _matrix(combo, nutrients)
    r = np.array([req[n] for n in nutrients])
    k = len(combo)
    # variables: x_1..x_k, t ; minimise t
    a_ub = np.vstack([np.hstack([a, -r[:, None]]), np.hstack([-a, -r[:, None]])])
    b_ub = np.concatenate([r, -r])
    res = linprog(c=[0] * k + [1], A_ub=a_ub, b_ub=b_ub, bounds=[(0, None)] * (k + 1), method="highs")
    return (res.x[-1], res.x[:k]) if res.status == 0 else (math.inf, None)


def _pack(combo, x):
    items = [(p, float(v)) for p, v in zip(combo, x) if v > 1e-6]
    return items


def supplied(items):
    return {n: sum(p[n] / 100.0 * kg for p, kg in items) for n in NUTRIENTS}


def optimise(products, req, tol=0.10, max_products=2):
    """Return {"feasible", "items": [(product, kg_per_ha)], "cost_per_ha", "max_deviation"}."""
    if not any(req[n] > 0 for n in NUTRIENTS):
        raise FertiliserError("requirement is zero for every nutrient")
    best = None
    for k in range(1, max_products + 1):
        for combo in combinations(products, k):
            x = _solve_combo(combo, req, tol)
            if x is None:
                continue
            items = _pack(combo, x)
            cost = sum(_price(p) * kg for p, kg in items)
            key = (round(cost, 6), len(items), round(sum(kg for _, kg in items), 6))
            if best is None or key < best[0]:
                best = (key, items, cost)
    if best:
        return {"feasible": True, "items": best[1], "cost_per_ha": best[2], "max_deviation": None}

    closest = None
    for k in range(1, max_products + 1):
        for combo in combinations(products, k):
            t, x = _closest_combo(combo, req)
            if x is not None and (closest is None or t < closest[0] - 1e-9):
                closest = (t, _pack(combo, x))
    items = closest[1] if closest else []
    return {"feasible": False, "items": items, "cost_per_ha": sum(_price(p) * kg for p, kg in items), "max_deviation": closest[0] if closest else None}


# ---------- recommendation ----------

def bags(kg, sizes):
    """Nearest bag size that covers the amount; multiples of the largest bag for big amounts."""
    sizes = sorted(sizes)
    for s in sizes:
        if kg <= s:
            return {"bag_kg": s, "count": 1}
    return {"bag_kg": sizes[-1], "count": math.ceil(kg / sizes[-1])}


def _fmt(x):
    return f"{x:.1f}" if x < 10 else f"{x:.0f}"


def _stage_emphasis(crop, stage):
    """Nutrient whose share of this stage's requirement is highest relative to the crop's other stages."""
    reqs = stage_requirements(crop)
    best, ratio = None, 1.0
    for n in NUTRIENTS:
        mean = sum(r[n] for r in reqs.values()) / len(reqs)
        if mean > 0 and reqs[stage][n] / mean > max(ratio, 1.15):
            best, ratio = n, reqs[stage][n] / mean
    return best


def ph_advice(crop, ph, lang):
    if ph is None:
        return None
    rng = crop_requirements()["crops"][crop].get("ph") or {}
    lo, hi = rng.get("min"), rng.get("max")
    t = TEXT[lang]
    if lo is None or hi is None:
        return {"status": "unknown_range", "text": t["ph_unknown_range"].format(crop=CROP_NAMES[lang][crop])}
    if ph < lo:
        return {"status": "low", "text": t["lime"].format(ph=ph, min=lo)}
    if ph > hi:
        return {"status": "high", "text": t["alkaline"].format(ph=ph, max=hi)}
    return {"status": "ok", "text": t["ph_ok"].format(ph=ph, min=lo, max=hi)}


def recommend(crop, stage, area_m2, num_plants=None, ph=None, soil=None, previous=None, deficiency_hint=False):
    if crop not in ("chilli", "tomato"):
        raise FertiliserError("crop must be chilli or tomato")
    if stage not in STAGES:
        raise FertiliserError(f"stage must be one of {', '.join(STAGES)}")
    if not area_m2 or area_m2 <= 0:
        raise FertiliserError("plot size (m²) is required")
    soil = {k: v for k, v in (soil or {}).items() if v}
    for k, v in soil.items():
        if k not in NUTRIENTS or v not in LEVELS:
            raise FertiliserError("soil levels must be low, medium or high for n, p2o5, k2o")

    cfg = thresholds()["fertiliser"]
    factors = crop_requirements()["soil_level_factor"]
    base = load_requirement(crop, stage)
    req = {n: base[n] * factors[soil.get(n, "medium")] for n in NUTRIENTS}
    products = load_products()
    result = optimise(products, req, cfg["tolerance"], cfg["max_products"])

    ha = area_m2 / 10000.0
    items = []
    for p, kg_ha in result["items"]:
        kg_plot = kg_ha * ha
        items.append({
            "name": p["name"], "kg_per_ha": round(kg_ha, 1), "kg_plot": round(kg_plot, 2),
            "g_per_plant": round(kg_plot * 1000 / num_plants, 1) if num_plants else None,
            "bag": bags(kg_plot, cfg["bag_sizes_kg"]),
        })
    got = supplied(result["items"])
    prices_known = all(p.get("price_rm_per_kg") is not None for p, _ in result["items"])
    deviation = {n: (got[n] - req[n]) / req[n] if req[n] > 0 else None for n in NUTRIENTS}

    emphasis = _stage_emphasis(crop, stage)
    text = {}
    for lang in ("en", "ms"):
        t = TEXT[lang]
        names = NUTRIENT_NAMES[lang]
        prod = " + ".join(t["product"].format(name=i["name"], kg=_fmt(i["kg_plot"])) for i in items)
        if result["feasible"]:
            reasons = [t["soil_low"].format(nutrient=names[n]) for n in NUTRIENTS if soil.get(n) == "low"]
            if emphasis:
                reasons.append(t["stage_need"].format(stage=STAGE_NAMES[lang][stage].lower(), nutrient=names[emphasis]))
            if not reasons:
                reasons.append(t["balanced"])
            summary = t["headline"].format(crop=CROP_NAMES[lang][crop], stage=STAGE_NAMES[lang][stage], products=prod)
            summary += " " + t["why"].format(reasons=(" and " if lang == "en" else " dan ").join(reasons))
        else:
            gaps = ", ".join(
                t["gap"].format(nutrient=names[n], sign="+" if d >= 0 else "−", pct=round(abs(d) * 100))
                for n, d in deviation.items() if d is not None and abs(d) > cfg["tolerance"]
            )
            summary = t["infeasible"].format(max=cfg["max_products"], tol=round(cfg["tolerance"] * 100), products=prod, gaps=gaps)
        notes = []
        pa = ph_advice(crop, ph, lang)
        if pa:
            notes.append(pa["text"])
        if deficiency_hint:
            notes.append(t["deficiency"])
        if previous:
            notes.append(t["previous"].format(previous=previous))
        text[lang] = {"summary": summary, "notes": notes}

    return {
        "crop": crop, "stage": stage, "area_m2": area_m2, "num_plants": num_plants,
        "feasible": result["feasible"],
        "products": items,
        "required_kg_per_ha": {n: round(v, 1) for n, v in req.items()},
        "supplied_kg_per_ha": {n: round(v, 1) for n, v in got.items()},
        "deviation": {n: (round(v, 3) if v is not None else None) for n, v in deviation.items()},
        "cost_rm_plot": round(result["cost_per_ha"] * ha, 2) if prices_known else None,
        "ph": ph_advice(crop, ph, "en")["status"] if ph is not None else None,
        "placeholder_requirements": bool(base.get("is_placeholder")),
        "placeholder_prices": not prices_known,
        "requirement_source": base.get("source"),
        "text": text,
    }
