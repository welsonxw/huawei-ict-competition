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


def _in_ring(lat, lon, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def region_at(lat, lon, geojson):
    """Region code whose polygon contains the point (GeoJSON [lon, lat] rings), or None."""
    for f in geojson["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            if _in_ring(lat, lon, poly[0]) and not any(_in_ring(lat, lon, hole) for hole in poly[1:]):
                return f["properties"]["code"]
    return None
