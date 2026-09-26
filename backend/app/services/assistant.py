"""Assistant that explains a diagnosis and its action plan in BM or English.

Uses any OpenAI-compatible chat-completions endpoint (LLM_ENDPOINT + LLM_API_KEY + LLM_MODEL), so a Huawei Cloud
Pangu/ModelArts deployment or another provider can be plugged in. Without a key, or if the call fails, answers
come from rule-based templates built from the same diagnosis and plan.
"""
import logging

import requests
from flask import current_app

from ..models import Scan
from .profiles import display_name, get_profile

log = logging.getLogger(__name__)

SPREAD = {
    "weather": {"en": "It spreads in wet, humid weather through rain splash and leaf wetness.",
                "ms": "Ia merebak semasa cuaca basah dan lembap melalui percikan hujan dan daun basah."},
    "vector": {"en": "It is carried by insects (such as whiteflies or thrips), so control them to stop the spread.",
               "ms": "Ia dibawa oleh serangga (seperti lalat putih atau thrip), jadi kawal serangga untuk hentikan merebak."},
    "contact": {"en": "It spreads by touch – hands, tools and infected seedlings.",
                "ms": "Ia merebak melalui sentuhan – tangan, alatan dan anak benih yang dijangkiti."},
    "none": {"en": "It does not spread from plant to plant.", "ms": "Ia tidak merebak dari pokok ke pokok."},
}
TEXT = {
    "summary": {"en": "The scan suggests {name} (confidence {conf}%, about {sev}% of the leaf affected).",
                "ms": "Imbasan menunjukkan {name} (keyakinan {conf}%, kira-kira {sev}% daun terjejas)."},
    "steps": {"en": "What to do:", "ms": "Apa yang perlu dibuat:"},
    "unsure": {"en": "The model is not sure about this photo, so an expert will check it. Please retake a clear photo of one leaf in daylight.",
               "ms": "Model tidak pasti tentang gambar ini, jadi pakar akan menyemaknya. Sila ambil semula gambar jelas sehelai daun pada waktu siang."},
    "confirmed": {"en": "An expert has checked this scan and confirmed the label.",
                  "ms": "Pakar telah menyemak imbasan ini dan mengesahkan labelnya."},
    "fertiliser": {"en": "Use the fertiliser planner below the scan for amounts; it uses your plot size and growth stage.",
                   "ms": "Gunakan perancang baja di bawah imbasan untuk jumlahnya; ia menggunakan saiz plot dan peringkat tumbesaran anda."},
    "healthy": {"en": "The leaf looks healthy. Keep scanning weekly so any problem is caught early.",
                "ms": "Daun kelihatan sihat. Teruskan mengimbas setiap minggu supaya masalah dapat dikesan awal."},
    "template_note": {"en": "(Answer from built-in rules.)", "ms": "(Jawapan daripada peraturan terbina.)"},
}
KEYWORDS = {
    "spray": ("spray", "sembur", "racun", "fungicide", "fungisid", "rain", "hujan", "when", "bila"),
    "spread": ("spread", "merebak", "jangkit", "contagious", "neighbour", "jiran"),
    "confidence": ("sure", "confident", "yakin", "pasti", "correct", "betul", "accurate"),
    "fertiliser": ("fertiliser", "fertilizer", "baja", "npk"),
}


def _topic(question):
    q = question.lower()
    for topic, words in KEYWORDS.items():
        if any(w in q for w in words):
            return topic
    return "summary"


def template_answer(scan: Scan, plan, question, lang, low_conf):
    label = scan.effective_label
    name = display_name(scan.crop, label, lang)
    summary = TEXT["summary"][lang].format(name=name, conf=round(scan.confidence * 100), sev=round(scan.severity * 100))
    steps = plan[lang]
    topic = _topic(question)
    if low_conf and not scan.confirmed_label:
        body = TEXT["unsure"][lang]
    elif label == "healthy":
        body = TEXT["healthy"][lang]
    elif topic == "spread":
        profile = get_profile(scan.crop, label) or {}
        body = SPREAD.get(profile.get("spread_mode", "none"), SPREAD["none"])[lang]
    elif topic == "spray":
        body = " ".join(s for s in steps if any(w in s.lower() for w in KEYWORDS["spray"])) or steps[0]
    elif topic == "fertiliser":
        body = TEXT["fertiliser"][lang]
    elif topic == "confidence":
        body = TEXT["confirmed"][lang] if scan.confirmed_label else summary
    else:
        body = f"{TEXT['steps'][lang]} " + " ".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
    return f"{summary} {body}" if topic != "confidence" else body


class LLMProvider:
    def chat(self, messages):
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, endpoint, api_key, model, timeout=20):
        self.endpoint, self.api_key, self.model, self.timeout = endpoint, api_key, model, timeout

    def chat(self, messages):
        res = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "temperature": 0.2},
            timeout=self.timeout,
        )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()


def get_provider():
    cfg = current_app.config
    if "llm_provider" in current_app.extensions:
        return current_app.extensions["llm_provider"]
    if not (cfg["LLM_ENDPOINT"] and cfg["LLM_API_KEY"]):
        return None
    return OpenAICompatibleProvider(cfg["LLM_ENDPOINT"], cfg["LLM_API_KEY"], cfg["LLM_MODEL"])


def answer(scan: Scan, plan, question, lang, low_conf):
    fallback = template_answer(scan, plan, question, lang, low_conf)
    provider = get_provider()
    if provider is None:
        return {"answer": fallback, "source": "template"}
    language = "Bahasa Melayu" if lang == "ms" else "English"
    context = (
        f"Crop: {scan.crop}. Diagnosis: {display_name(scan.crop, scan.effective_label, 'en')} "
        f"(confidence {scan.confidence:.0%}, expert-confirmed: {bool(scan.confirmed_label)}, needs review: {low_conf}). "
        f"Leaf area affected: {scan.severity:.0%}. Action plan: " + " | ".join(plan["en"])
    )
    messages = [
        {"role": "system", "content": (
            f"You are an agricultural extension assistant for Malaysian smallholders. Answer in {language}, in at most "
            "4 short sentences, using only the diagnosis and action plan given. Do not invent pesticide doses; "
            "tell the farmer to follow the product label and contact the DOA office if unsure.")},
        {"role": "user", "content": f"{context}\n\nQuestion: {question or 'Explain the diagnosis and what to do.'}"},
    ]
    try:
        return {"answer": provider.chat(messages), "source": "llm"}
    except Exception:  # noqa: BLE001 – any provider failure falls back to the rule-based answer
        log.warning("LLM call failed; using template answer", exc_info=True)
        return {"answer": fallback, "source": "template"}
