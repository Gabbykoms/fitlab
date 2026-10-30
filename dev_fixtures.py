"""Fake, spec-shaped data for dev_server.py.

Everything here is deterministic and offline: no keys, no network. Shapes
follow spec.md §3.1 (outfit option), §3.3 (WeatherSummary) and §7 (critique).
"""

from __future__ import annotations

import base64
import random
from datetime import date

WEIGHTS = {"occasion": 30, "aesthetic": 25, "styling": 20, "weather": 15, "upload_fidelity": 10}
RETRY_THRESHOLD = 70
MAX_ATTEMPTS = 3
FORECAST_WINDOW_DAYS = 16
GENERATION_MODEL = "google/gemini-3.1-flash-image"
CRITIQUE_MODEL = "xiaomi/mimo-v2.6-flash"

PALETTES = [
    {"top": "#E8E4DA", "bottom": "#2F3A4A", "outer": "#6B5B4B", "shoes": "#3A2E26"},
    {"top": "#C9D6DF", "bottom": "#4A4A48", "outer": "#1F2A36", "shoes": "#111111"},
    {"top": "#F2F0EB", "bottom": "#8A7F6E", "outer": "#425B52", "shoes": "#5A4636"},
]

PIECE_SETS = [
    [("oatmeal crew-neck knit", "top", "oatmeal"), ("navy pleated trousers", "bottom", "navy"),
     ("brown suede jacket", "outerwear", "brown"), ("dark brown loafers", "shoes", "dark brown")],
    [("pale blue oxford shirt", "top", "pale blue"), ("charcoal wool trousers", "bottom", "charcoal"),
     ("navy overcoat", "outerwear", "navy"), ("black derby shoes", "shoes", "black")],
    [("white linen-blend shirt", "top", "white"), ("taupe chinos", "bottom", "taupe"),
     ("forest green chore coat", "outerwear", "forest green"), ("brown chelsea boots", "shoes", "brown")],
]


def round_half_up(value: float) -> int:
    return int(value + 0.5)


def compute_overall(scores: dict) -> int:
    assessed = {k: v for k, v in scores.items() if v is not None}
    total = sum(WEIGHTS[k] * v for k, v in assessed.items())
    return round_half_up(total / sum(WEIGHTS[k] for k in assessed))


def retry_reason(overall: int, mismatches: list) -> str:
    serious = [m for m in mismatches if m["severity"] in ("major", "critical")]
    if overall < RETRY_THRESHOLD:
        return f"overall {overall} is below the {RETRY_THRESHOLD} threshold"
    if serious:
        return f"one {serious[0]['severity']} mismatch: {serious[0]['code']}"
    return ""


def mannequin_svg(index: int) -> str:
    """A flat mannequin silhouette as a same-origin data URL (no real person)."""
    p = PALETTES[index % len(PALETTES)]
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 400'>
<rect width='300' height='400' fill='#FBFBF8'/>
<g stroke='#E6E6E0' stroke-width='1'>{''.join(f"<line x1='{x}' y1='0' x2='{x}' y2='400'/>" for x in range(0, 300, 20))}</g>
<ellipse cx='150' cy='52' rx='22' ry='26' fill='#D8D4CC'/>
<rect x='142' y='76' width='16' height='14' fill='#D8D4CC'/>
<path d='M98 92 Q150 80 202 92 L214 210 L86 210 Z' fill='{p['outer']}'/>
<path d='M122 92 Q150 86 178 92 L182 200 L118 200 Z' fill='{p['top']}'/>
<path d='M104 210 L196 210 L190 350 L156 350 L150 240 L144 350 L110 350 Z' fill='{p['bottom']}'/>
<rect x='104' y='350' width='42' height='14' rx='6' fill='{p['shoes']}'/>
<rect x='154' y='350' width='42' height='14' rx='6' fill='{p['shoes']}'/>
<rect x='145' y='364' width='10' height='22' fill='#BDB8AE'/>
<rect x='110' y='386' width='80' height='6' fill='#BDB8AE'/>
</svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def make_pieces(index: int, preserved: list | None = None) -> list:
    pieces = [
        {"id": f"o{index}p{i + 1}", "name": name, "category": cat, "color": color,
         "pattern": None, "source": "generated"}
        for i, (name, cat, color) in enumerate(PIECE_SETS[index % len(PIECE_SETS)])
    ]
    for j, piece in enumerate(preserved or []):
        pieces = [*pieces, {**piece, "id": f"o{index}k{j + 1}", "source": "preserved"}]
    return pieces


def make_critique(attempt: int, scores: dict, mismatches: list, summary: str) -> dict:
    overall = compute_overall(scores)
    reason = retry_reason(overall, mismatches)
    return {
        "schema_version": "1.0",
        "attempt": attempt,
        "model": CRITIQUE_MODEL,
        "scores": scores,
        "overall": overall,
        "summary": summary,
        "matches": ["Silhouette reads as smart rather than business formal.",
                    "The palette stays neutral and consistent across pieces."],
        "mismatches": mismatches,
        "uncertainty": ["The image cannot establish the warmth of the outer layer; fabric weight is not visible."],
        "weather_assessed": scores["weather"] is not None,
        "upload_fidelity_assessed": scores["upload_fidelity"] is not None,
        "retry_recommended": bool(reason),
        "retry_reason": reason,
    }


def failed_critique(attempt: int) -> dict:
    return {"status": "failed", "error": "invalid_response", "model": CRITIQUE_MODEL,
            "attempt": attempt, "raw_excerpt": None}


def _scores(rng: random.Random, weather_ok: bool, has_refs: bool, low: bool) -> dict:
    base = 55 if low else 78
    return {
        "occasion": rng.randint(base, base + 15),
        "aesthetic": rng.randint(base - 5, base + 12),
        "styling": rng.randint(base, base + 16),
        "weather": rng.randint(base, base + 14) if weather_ok else None,
        "upload_fidelity": rng.randint(base - 4, base + 10) if has_refs else None,
    }


MAJOR_MISMATCH = {"code": "AESTHETIC_MISMATCH", "severity": "major", "affected_pieces": ["o{i}p3"],
                  "explanation": "The jacket reads more rugged than the requested clean, relaxed style."}
MINOR_MISMATCH = {"code": "AESTHETIC_MISMATCH", "severity": "minor", "affected_pieces": ["o{i}p4"],
                  "explanation": "The shoes are slightly heavier than the clean style suggests."}


def _mismatch(template: dict, index: int) -> dict:
    return {**template, "affected_pieces": [p.format(i=index) for p in template["affected_pieces"]]}


def make_option(index: int, scenario: str, weather_ok: bool, has_refs: bool,
                preserved: list | None = None) -> dict:
    """Build one option including its critique history.

    scenario: "normal" (option B needs one retry), "unresolved" (option A exhausts
    its retries), or "nocritique" (option C's critique fails).
    """
    rng = random.Random(index * 7 + len(scenario))
    history = []
    if scenario == "nocritique" and index == 2:
        history = [failed_critique(1)]
    elif scenario == "unresolved" and index == 0:
        history = [make_critique(n, _scores(rng, weather_ok, has_refs, low=True),
                                 [_mismatch(MAJOR_MISMATCH, index)],
                                 "The look drifts from the requested aesthetic.")
                   for n in range(1, MAX_ATTEMPTS + 1)]
    elif index == 1:
        history = [make_critique(1, _scores(rng, weather_ok, has_refs, low=True),
                                 [_mismatch(MAJOR_MISMATCH, index)],
                                 "The outer layer departs from the brief."),
                   make_critique(2, _scores(rng, weather_ok, has_refs, low=False),
                                 [_mismatch(MINOR_MISMATCH, index)],
                                 "The regenerated look suits the occasion and the requested style.")]
    else:
        history = [make_critique(1, _scores(rng, weather_ok, has_refs, low=False), [],
                                 "The look suits the occasion and keeps a clean, relaxed line.")]
    final = history[-1]
    unresolved = final.get("mismatches", []) if final.get("retry_recommended") else []
    return {
        "index": index,
        "image_data_url": mannequin_svg(index),
        "pieces": make_pieces(index, preserved),
        "attempts": len(history),
        "critique": final,
        "critique_history": history,
        "unresolved": unresolved,
        "generation_model": GENERATION_MODEL,
        "critique_model": CRITIQUE_MODEL,
    }


def make_weather(event_date: str, event_time: str, city: str | None,
                 lat: float | None, lon: float | None) -> dict:
    name = city or (f"Your current location ({lat:.3f}, {lon:.3f})" if lat is not None and lon is not None
                    else "Hartford, Connecticut, United States")
    unavailable = {
        "available": False, "location_name": name, "latitude": lat, "longitude": lon,
        "timezone": None, "event_local_datetime": f"{event_date}T{event_time}",
        "temperature_f": None, "feels_like_f": None, "precipitation_probability": None,
        "precipitation_mm": None, "wind_speed_mph": None, "weather_code": None,
        "condition_label": None, "layering_advice": None,
    }
    if city and city.strip().lower() == "nowhere":
        return {**unavailable, "unavailable_reason": "LOCATION_NOT_FOUND"}
    days_out = (date.fromisoformat(event_date) - date.today()).days
    if days_out > FORECAST_WINDOW_DAYS:
        return {**unavailable, "unavailable_reason": "OUT_OF_FORECAST_RANGE"}
    return {
        **unavailable, "available": True, "latitude": lat if lat is not None else 41.76371,
        "longitude": lon if lon is not None else -72.68509, "timezone": "America/New_York",
        "temperature_f": 52.6, "feels_like_f": 51.0, "precipitation_probability": 20,
        "precipitation_mm": 0.0, "wind_speed_mph": 6.8, "weather_code": 3,
        "condition_label": "Overcast", "layering_advice": "light layering; a mid-weight jacket",
        "unavailable_reason": None,
    }
