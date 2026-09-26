"""Rule-based action plan (EN / BM). Never names pesticide brands or doses."""
from .weather import summarise

CROP_NAMES = {"chilli": {"en": "chilli", "ms": "cili"}, "tomato": {"en": "tomato", "ms": "tomato"}}

T = {
    "healthy": {
        "en": "No disease found on this leaf. Keep checking {plot} every few days.",
        "ms": "Tiada penyakit dikesan pada daun ini. Terus periksa {plot} setiap beberapa hari.",
    },
    "retake": {
        "en": "Not sure – please retake the photo in daylight, with one leaf filling the frame.",
        "ms": "Kurang pasti – sila ambil semula gambar di bawah cahaya siang, satu daun memenuhi bingkai.",
    },
    "expert": {
        "en": "Your photo has been sent to an expert for review. Do not spray until the diagnosis is confirmed.",
        "ms": "Gambar anda telah dihantar kepada pakar untuk semakan. Jangan sembur sehingga diagnosis disahkan.",
    },
    "only_plot": {
        "en": "Treat {plot} only – other plots do not need treatment yet.",
        "ms": "Rawat {plot} sahaja – plot lain belum perlu dirawat.",
    },
    "remove_leaves": {
        "en": "Remove badly affected leaves and fruit from {plot}; bag them and take them off the farm. Do not compost.",
        "ms": "Buang daun dan buah yang teruk dijangkiti di {plot}; masukkan ke dalam beg dan bawa keluar dari ladang. Jangan jadikan kompos.",
    },
    "spray": {
        "en": "Spray a fungicide registered for {crop}; follow the label dose.",
        "ms": "Sembur racun kulat yang berdaftar untuk {crop}; ikut dos pada label.",
    },
    "spray_bacterial": {
        "en": "Use a bactericide registered for {crop}; follow the label dose.",
        "ms": "Gunakan racun bakteria yang berdaftar untuk {crop}; ikut dos pada label.",
    },
    "rain_wait": {
        "en": "Rain expected {when} – wait until leaves are dry before spraying.",
        "ms": "Hujan dijangka {when} – tunggu sehingga daun kering sebelum menyembur.",
    },
    "dry_spray": {
        "en": "No rain expected in the next 48 hours – a good window to spray, early morning or late afternoon.",
        "ms": "Tiada hujan dijangka dalam 48 jam akan datang – masa sesuai untuk menyembur, awal pagi atau lewat petang.",
    },
    "humid": {
        "en": "Leaves will stay wet for about {hours} hours in the next 2 days – improve air flow by pruning and avoid overhead watering.",
        "ms": "Daun akan kekal basah kira-kira {hours} jam dalam 2 hari akan datang – tingkatkan pengudaraan dengan mencantas dan elakkan siraman dari atas.",
    },
    "no_forecast": {
        "en": "Weather forecast unavailable – spray only when leaves are dry and no rain is expected for a few hours.",
        "ms": "Ramalan cuaca tidak tersedia – sembur hanya apabila daun kering dan tiada hujan dijangka dalam beberapa jam.",
    },
    "vector_check": {
        "en": "Check the underside of leaves in {plot} for whiteflies. Use yellow sticky traps.",
        "ms": "Periksa bahagian bawah daun di {plot} untuk lalat putih. Gunakan perangkap pelekat kuning.",
    },
    "vector_remove": {
        "en": "Pull out plants with severe curling and destroy them – they cannot recover and will spread the virus.",
        "ms": "Cabut dan musnahkan pokok yang kerekot teruk – ia tidak boleh pulih dan akan menyebarkan virus.",
    },
    "vector_spray": {
        "en": "If whiteflies are many, use an insecticide registered for whitefly on {crop}; follow the label dose.",
        "ms": "Jika lalat putih banyak, gunakan racun serangga yang berdaftar untuk lalat putih pada {crop}; ikut dos pada label.",
    },
    "vector_dry": {
        "en": "Dry weather ahead – whiteflies build up quickly. Check traps every 2–3 days.",
        "ms": "Cuaca kering dijangka – lalat putih membiak dengan cepat. Periksa perangkap setiap 2–3 hari.",
    },
    "hygiene_remove": {
        "en": "Remove infected plants from {plot}. Wash hands and tools with soap before touching healthy plants.",
        "ms": "Buang pokok yang dijangkiti dari {plot}. Basuh tangan dan alatan dengan sabun sebelum menyentuh pokok sihat.",
    },
    "hygiene_tobacco": {
        "en": "Do not smoke or handle tobacco near the plants – it can carry mosaic virus.",
        "ms": "Jangan merokok atau memegang tembakau berhampiran pokok – ia boleh membawa virus mozek.",
    },
    "hygiene_seed": {
        "en": "Use certified seed next season.",
        "ms": "Gunakan benih yang disahkan untuk musim hadapan.",
    },
    "nutrition": {
        "en": "Leaves show signs of nutrient deficiency. Use the fertiliser planner below and do a soil test if you can.",
        "ms": "Daun menunjukkan tanda kekurangan nutrien. Gunakan perancang baja di bawah dan buat ujian tanah jika boleh.",
    },
    "monitor": {
        "en": "Scan {plot} again in 3–5 days to check whether it is spreading.",
        "ms": "Imbas {plot} semula dalam 3–5 hari untuk melihat sama ada ia merebak.",
    },
}

WHEN = {
    "en": {"soon": "in the next few hours", "today": "later today", "tomorrow": "tomorrow", "later": "in 2 days"},
    "ms": {"soon": "dalam beberapa jam lagi", "today": "lewat hari ini", "tomorrow": "esok", "later": "dalam 2 hari"},
}


def build_steps(disease, advice_type, wx, low_confidence=False, bacterial=False):
    """Return a list of (template key, vars) for the plan."""
    steps = []
    if low_confidence:
        return [("retake", {}), ("expert", {})]
    if disease == "healthy":
        return [("healthy", {}), ("monitor", {})]

    if advice_type == "spray_timing":
        steps.append(("only_plot", {}))
        steps.append(("remove_leaves", {}))
        steps.append(("spray_bacterial" if bacterial else "spray", {}))
        if wx is None:
            steps.append(("no_forecast", {}))
        elif wx["rain_hours"] > 0:
            steps.append(("rain_wait", {"when": wx["rain_when"]}))
        else:
            steps.append(("dry_spray", {}))
        if wx and wx["wet_hours"] >= 6:
            steps.append(("humid", {"hours": wx["wet_hours"]}))
    elif advice_type == "vector_control":
        steps.append(("vector_check", {}))
        steps.append(("vector_remove", {}))
        steps.append(("vector_spray", {}))
        if wx and wx["rain_hours"] == 0:
            steps.append(("vector_dry", {}))
    elif advice_type == "hygiene":
        steps.extend([("hygiene_remove", {}), ("hygiene_tobacco", {}), ("hygiene_seed", {})])
    elif advice_type == "nutrition":
        steps.append(("nutrition", {}))
    steps.append(("monitor", {}))
    return steps[:5]


def render(steps, lang, crop, plot_name):
    out = []
    for key, vars_ in steps:
        v = dict(vars_)
        if "when" in v:
            v["when"] = WHEN[lang][v["when"]]
        out.append(T[key][lang].format(crop=CROP_NAMES[crop][lang], plot=plot_name, **v))
    return out


def action_plan(disease, crop, profile, plot_name, forecast, weather_cfg, low_confidence=False, now=None):
    advice_type = profile.get("advice_type", "spray_timing") if profile else "spray_timing"
    wx = summarise(forecast, weather_cfg["action_plan_hours"], weather_cfg["rain_mm_threshold"], weather_cfg["leaf_wetness_rh"], now)
    steps = build_steps(disease, advice_type, wx, low_confidence=low_confidence, bacterial=disease == "bacterial_spot")
    return {
        "steps": [k for k, _ in steps],
        "weather": wx,
        "en": render(steps, "en", crop, plot_name),
        "ms": render(steps, "ms", crop, plot_name),
    }
