import pytest

from app.services import nutrients
from app.services.fertiliser import bags, optimise, recommend, seed_fertiliser, supplied

PRODUCTS = [
    {"name": "Urea", "n": 46, "p2o5": 0, "k2o": 0, "price_rm_per_kg": 2.0},
    {"name": "NPK 15:15:15", "n": 15, "p2o5": 15, "k2o": 15, "price_rm_per_kg": 3.0},
    {"name": "NPK 13:13:21", "n": 13, "p2o5": 13, "k2o": 21, "price_rm_per_kg": 3.5},
    {"name": "DAP", "n": 18, "p2o5": 46, "k2o": 0, "price_rm_per_kg": 3.0},
    {"name": "MOP", "n": 0, "p2o5": 0, "k2o": 60, "price_rm_per_kg": 2.5},
]


def test_oxide_elemental_round_trip():
    assert nutrients.p2o5_to_p(100) == pytest.approx(43.6)
    assert nutrients.k2o_to_k(100) == pytest.approx(83.0)
    assert nutrients.p_to_p2o5(nutrients.p2o5_to_p(37.5)) == pytest.approx(37.5)
    assert nutrients.k_to_k2o(nutrients.k2o_to_k(60)) == pytest.approx(60)
    assert nutrients.to_oxide({"n": 10, "p": 43.6, "k": 83}, "elemental") == pytest.approx({"n": 10, "p2o5": 100, "k2o": 100})


@pytest.mark.parametrize("req", [
    {"n": 30, "p2o5": 30, "k2o": 30},
    {"n": 60, "p2o5": 30, "k2o": 30},
    {"n": 30, "p2o5": 30, "k2o": 60},
    {"n": 100, "p2o5": 0, "k2o": 0},
])
def test_optimiser_max_two_products_within_tolerance(req):
    out = optimise(PRODUCTS, req, tol=0.10, max_products=2)
    assert out["feasible"]
    assert 1 <= len(out["items"]) <= 2
    got = supplied(out["items"])
    for n, r in req.items():
        if r > 0:
            assert 0.9 * r - 1e-6 <= got[n] <= 1.1 * r + 1e-6


def test_optimiser_picks_cheapest():
    # Pure nitrogen: urea (RM2/kg, 46% N) is cheaper per kg N than any NPK.
    out = optimise(PRODUCTS, {"n": 46, "p2o5": 0, "k2o": 0})
    assert [p["name"] for p, _ in out["items"]] == ["Urea"]
    assert out["items"][0][1] == pytest.approx(90, rel=0.01)  # lower bound: 0.9 * 46 / 0.46


def test_optimiser_explains_infeasible():
    # Only one product with a fixed 1:1:1 ratio cannot meet 100:10:10.
    out = optimise([PRODUCTS[1]], {"n": 100, "p2o5": 10, "k2o": 10}, tol=0.10, max_products=2)
    assert out["feasible"] is False and out["max_deviation"] > 0.10 and out["items"]


def test_bags():
    assert bags(0.6, [1, 5, 25, 50]) == {"bag_kg": 1, "count": 1}
    assert bags(7, [1, 5, 25, 50]) == {"bag_kg": 25, "count": 1}
    assert bags(120, [1, 5, 25, 50]) == {"bag_kg": 50, "count": 3}


def test_recommend_uses_placeholders_and_flags_them(app):
    seed_fertiliser()
    out = recommend("chilli", "fruiting", area_m2=400, num_plants=200)
    assert out["feasible"] and len(out["products"]) <= 2
    assert out["placeholder_requirements"] and out["placeholder_prices"] and out["cost_rm_plot"] is None
    assert out["text"]["en"]["summary"].startswith("Chilli – Fruiting stage. Recommended:")
    assert "potassium" in out["text"]["en"]["summary"]
    assert out["products"][0]["g_per_plant"] is not None


def test_low_ph_gives_liming_advice(app):
    out = recommend("chilli", "vegetative", area_m2=400, ph=4.8)
    assert out["ph"] == "low"
    assert any("Apply lime" in n for n in out["text"]["en"]["notes"])
    assert any("Tabur kapur" in n for n in out["text"]["ms"]["notes"])
    high = recommend("chilli", "vegetative", area_m2=400, ph=7.5)
    assert high["ph"] == "high" and high["products"] == out["products"]  # pH never changes product choice


def test_tomato_ph_range_todo(app):
    out = recommend("tomato", "flowering", area_m2=400, ph=6.0)
    assert out["ph"] == "unknown_range"


def test_soil_low_mentioned(app):
    out = recommend("chilli", "seedling", area_m2=400, soil={"k2o": "low"})
    assert out["required_kg_per_ha"]["k2o"] > out["required_kg_per_ha"]["n"]
    if out["feasible"]:
        assert "your potassium is low" in out["text"]["en"]["summary"]


def test_recommend_route_with_plot_and_deficiency_hint(app, client):
    from app.extensions import db
    from app.models import Scan
    from app.services.scans import create_plot

    seed_fertiliser()
    plot = create_plot("Plot A", "chilli", 1.85, 103.33, area_m2=400, num_plants=200)
    db.session.add(Scan(plot_id=plot.id, crop="chilli", diagnosis="nutrient_deficiency", confidence=0.9, top3=[],
                        lat=1.85, lon=103.33, grid_cell=plot.grid_cell, region="JHR"))
    db.session.commit()
    res = client.post("/api/fertiliser/recommend", json={"plot_id": plot.id, "stage": "flowering", "ph": "5"})
    assert res.status_code == 200
    body = res.get_json()
    assert any("soil test" in n for n in body["text"]["en"]["notes"])
    assert client.post("/api/fertiliser/recommend", json={"crop": "chilli", "stage": "bogus", "area_m2": 1}).status_code == 400
    assert len(client.get("/api/fertiliser/products").get_json()) == 7


def test_mixed_prices_fall_back_to_uniform_cost():
    mixed = [dict(p) for p in PRODUCTS]
    mixed[0]["price_rm_per_kg"] = None
    out = optimise(mixed, {"n": 46, "p2o5": 0, "k2o": 0})
    assert out["priced"] is False
    assert optimise(PRODUCTS, {"n": 46, "p2o5": 0, "k2o": 0})["priced"] is True


def test_inactive_products_stay_disabled(app):
    from app.extensions import db
    from app.models import FertiliserProduct
    from app.services.fertiliser import load_products

    seed_fertiliser()
    FertiliserProduct.query.update({"active": False})
    db.session.commit()
    assert load_products() == []
    with pytest.raises(ValueError):
        recommend("chilli", "fruiting", area_m2=400)


@pytest.mark.parametrize("body", [
    [1, 2],
    {"crop": "chilli", "stage": "fruiting", "area_m2": 400, "soil": "low"},
    {"crop": "chilli", "stage": "fruiting", "area_m2": 400, "num_plants": -5},
    {"crop": "chilli", "stage": "fruiting", "area_m2": 400, "num_plants": 2.5},
    {"crop": "chilli", "stage": "fruiting", "area_m2": 1e300},
    {"plot_id": "abc", "stage": "fruiting"},
])
def test_recommend_route_rejects_bad_input(app, client, body):
    seed_fertiliser()
    assert client.post("/api/fertiliser/recommend", json=body).status_code == 400
