"""~5 km grid cells over Peninsular Malaysia and region lookup."""
import math

EARTH_RADIUS_KM = 6371.0


def cell_id(lat, lon, cell_deg):
    return f"{math.floor(lat / cell_deg)}_{math.floor(lon / cell_deg)}"


def cell_center(cid, cell_deg):
    i, j = (int(x) for x in cid.split("_"))
    return ((i + 0.5) * cell_deg, (j + 0.5) * cell_deg)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_region(lat, lon, regions):
    return min(regions, key=lambda r: haversine_km(lat, lon, r["lat"], r["lon"]))["code"]
