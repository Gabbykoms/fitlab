"""Tests for the critique validator and scorer (spec.md Section 7).

No API key and no network access: every test drives the pure parsing,
validation, weighting, and retry-trigger functions in ``critique.py``.

The worked examples in spec.md Section 7 are the source of the expected
values here:
  * 7.1  the canonical document
  * 7.4  three ``overall`` computations
  * 7.7  six retry-trigger outcomes
"""

import json

import pytest

from critique import (
    CritiqueParseError,
    compute_overall,
    compute_retry,
    finalize_reply,
    parse_reply,
    validate_payload,
)


# --------------------------------------------------------------------------
# §7.1 — the canonical document
# --------------------------------------------------------------------------

CANONICAL = {
    "schema_version": "1.0",
    "attempt": 1,
    "model": "xiaomi/mimo-v2.6-flash",
    "scores": {
        "occasion": 85,
        "aesthetic": 78,
        "styling": 90,
        "weather": None,
        "upload_fidelity": None,
    },
    "overall": 84,
    "summary": (
        "The look reads as smart-casual and suits the dinner. "
        "The palette is neutral and the layering suits the temperature."
    ),
    "matches": [
        "Silhouette reads as smart rather than business formal, matching the requested aesthetic.",
        "Trousers and knitwear are in a consistent neutral palette.",
    ],
    "mismatches": [
        {
            "code": "AESTHETIC_MISMATCH",
            "severity": "minor",
            "affected_pieces": ["p1"],
            "explanation": (
                "The heavy lugged boots read more rugged than the requested clean, relaxed style."
            ),
        }
    ],
    "uncertainty": [
        "The image cannot establish the warmth of the outer layer; fabric weight is not visible."
    ],
    "weather_assessed": False,
    "upload_fidelity_assessed": False,
    "retry_recommended": False,
    "retry_reason": "",
}


@pytest.fixture
def doc():
    """A fresh, valid copy of the canonical document."""
    return json.loads(json.dumps(CANONICAL))


NO_WEATHER_NO_REFS = {"weather_available": False, "references_supplied": False}


# --------------------------------------------------------------------------
# Parsing (CRT-3) — clean JSON, JSON inside prose, and unparseable text
# --------------------------------------------------------------------------

def test_parse_clean_json():
    raw = json.dumps(CANONICAL)
    assert parse_reply(raw) == CANONICAL


def test_parse_strips_reasoning_trace_and_code_fence():
    """Repair (a): drop a leading reasoning trace and a fenced code-block wrapper."""
    body = json.dumps(CANONICAL, indent=2)
    raw = (
        "Let me check each dimension against the rubric.\n"
        "The boots are heavier than a clean relaxed style would suggest.\n"
        "```json\n"
        f"{body}\n"
        "```\n"
    )
    assert parse_reply(raw) == CANONICAL


def test_parse_extracts_outermost_object_from_prose():
    """Repair (b): pull the outermost {...} substring out of surrounding prose."""
    raw = (
        "Sure! Here is the critique you asked for:\n"
        f"{json.dumps(CANONICAL)}\n"
        "Let me know if you want a different occasion weighting."
    )
    assert parse_reply(raw) == CANONICAL


def test_parse_unparseable_text_raises():
    with pytest.raises(CritiqueParseError):
        parse_reply("I could not determine the weather from the image.")


def test_parse_truncated_json_raises():
    with pytest.raises(CritiqueParseError):
        parse_reply('{"schema_version": "1.0", "attempt": 1,')


def test_parse_non_object_json_raises():
    with pytest.raises(CritiqueParseError):
        parse_reply("[1, 2, 3]")


# --------------------------------------------------------------------------
# Validation (CRT-4) — every field, every type
# --------------------------------------------------------------------------

def test_canonical_document_has_no_errors(doc):
    assert validate_payload(doc, **NO_WEATHER_NO_REFS) == []


def test_schema_version_must_be_1_0(doc):
    doc["schema_version"] = "0.9"
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("schema_version" in e for e in errors)


def test_attempt_must_be_an_integer(doc):
    doc["attempt"] = "1"
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("attempt" in e for e in errors)


def test_attempt_must_be_at_least_one(doc):
    doc["attempt"] = 0
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("attempt" in e for e in errors)


def test_scores_must_contain_exactly_the_five_keys(doc):
    del doc["scores"]["upload_fidelity"]
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("upload_fidelity" in e for e in errors)


def test_score_above_100_is_a_failure(doc):
    doc["scores"]["occasion"] = 101
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("occasion" in e for e in errors)


def test_negative_score_is_a_failure(doc):
    doc["scores"]["aesthetic"] = -1
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("aesthetic" in e for e in errors)


def test_fractional_score_is_a_failure(doc):
    doc["scores"]["styling"] = 90.5
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("styling" in e for e in errors)


def test_boolean_score_is_not_an_integer(doc):
    doc["scores"]["occasion"] = True
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("occasion" in e for e in errors)


def test_missing_required_field_is_a_failure(doc):
    del doc["summary"]
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("summary" in e for e in errors)


def test_empty_summary_is_a_failure(doc):
    doc["summary"] = ""
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("summary" in e for e in errors)


def test_overlong_summary_is_a_failure(doc):
    doc["summary"] = "x" * 601
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("summary" in e for e in errors)


def test_more_than_eight_matches_is_a_failure(doc):
    doc["matches"] = ["x" * 10] * 9
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("matches" in e for e in errors)


def test_more_than_eight_uncertainties_is_a_failure(doc):
    doc["uncertainty"] = ["x" * 10] * 9
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("uncertainty" in e for e in errors)


def test_unknown_severity_is_a_failure(doc):
    doc["mismatches"][0]["severity"] = "moderate"
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("severity" in e for e in errors)


def test_unknown_mismatch_code_is_a_failure(doc):
    doc["mismatches"][0]["code"] = "WRONG_VIBE"
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("code" in e for e in errors)


def test_mismatch_missing_a_field_is_a_failure(doc):
    del doc["mismatches"][0]["explanation"]
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("explanation" in e for e in errors)


def test_mismatch_explanation_may_not_be_empty(doc):
    doc["mismatches"][0]["explanation"] = ""
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("explanation" in e for e in errors)


def test_mismatch_explanation_length_is_capped(doc):
    doc["mismatches"][0]["explanation"] = "x" * 501
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("explanation" in e for e in errors)


def test_too_many_affected_pieces_is_a_failure(doc):
    doc["mismatches"][0]["affected_pieces"] = [f"p{i}" for i in range(7)]
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("affected_pieces" in e for e in errors)


def test_weather_score_must_be_null_when_no_forecast(doc):
    """CRT-6: the server enforces the null score regardless of what the model returns."""
    doc["weather_assessed"] = True
    doc["scores"]["weather"] = 75
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("weather" in e for e in errors)


def test_weather_must_be_scored_when_a_forecast_exists(doc):
    doc["weather_assessed"] = False
    doc["scores"]["weather"] = None
    errors = validate_payload(doc, weather_available=True, references_supplied=False)
    assert any("weather" in e for e in errors)


def test_upload_fidelity_must_be_null_without_references(doc):
    """CRT-7: no reference image means the dimension was not assessed."""
    doc["upload_fidelity_assessed"] = True
    doc["scores"]["upload_fidelity"] = 80
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("upload_fidelity" in e for e in errors)


def test_upload_fidelity_must_be_scored_when_references_exist(doc):
    doc["upload_fidelity_assessed"] = False
    doc["scores"]["upload_fidelity"] = None
    errors = validate_payload(doc, weather_available=False, references_supplied=True)
    assert any("upload_fidelity" in e for e in errors)


def test_retry_reason_may_be_empty_when_not_retrying(doc):
    doc["retry_recommended"] = False
    doc["retry_reason"] = ""
    assert validate_payload(doc, **NO_WEATHER_NO_REFS) == []


def test_retry_reason_is_required_when_the_model_asks_for_a_retry(doc):
    doc["retry_recommended"] = True
    doc["retry_reason"] = ""
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("retry_reason" in e for e in errors)


def test_retry_reason_must_be_empty_when_the_model_does_not_ask(doc):
    doc["retry_recommended"] = False
    doc["retry_reason"] = "there was a problem"
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("retry_reason" in e for e in errors)


# --------------------------------------------------------------------------
# §7.4 / CRT-5 — the weighted overall, computed server-side
# --------------------------------------------------------------------------

def test_overall_from_three_assessed_dimensions():
    """occasion 85, aesthetic 78, styling 90 -> 84 over a denominator of 75."""
    scores = {
        "occasion": 85,
        "aesthetic": 78,
        "styling": 90,
        "weather": None,
        "upload_fidelity": None,
    }
    assert compute_overall(scores, **NO_WEATHER_NO_REFS) == 84


def test_overall_with_weather_included():
    """occasion 85, aesthetic 78, styling 90, weather 52 -> 79 over a denominator of 90."""
    scores = {
        "occasion": 85,
        "aesthetic": 78,
        "styling": 90,
        "weather": 52,
        "upload_fidelity": None,
    }
    assert compute_overall(scores, weather_available=True, references_supplied=False) == 79


def test_overall_with_every_dimension_assessed():
    """All five at 80 -> 80 over a denominator of 100."""
    scores = {
        "occasion": 80,
        "aesthetic": 80,
        "styling": 80,
        "weather": 80,
        "upload_fidelity": 80,
    }
    assert compute_overall(scores, weather_available=True, references_supplied=True) == 80


def test_overall_rounds_half_up():
    """A .5 remainder rounds up, not to even and not down."""
    # 30*70 + 25*71 + 20*70 = 2100 + 1775 + 1400 = 5275; / 75 = 70.333...
    scores = {
        "occasion": 70,
        "aesthetic": 71,
        "styling": 70,
        "weather": None,
        "upload_fidelity": None,
    }
    assert compute_overall(scores, **NO_WEATHER_NO_REFS) == 70


def test_overall_excludes_unassessed_dimensions_from_the_denominator():
    """A null weather score removes 15 from the denominator, not 100 from the score."""
    scores = {
        "occasion": 100,
        "aesthetic": 100,
        "styling": 100,
        "weather": 0,
        "upload_fidelity": None,
    }
    assert compute_overall(scores, **NO_WEATHER_NO_REFS) == 100


def test_overall_disagreement_of_one_is_tolerated(doc):
    """CRT-5: a difference of exactly 1 is tolerated and overwritten."""
    doc["overall"] = 85
    assert validate_payload(doc, **NO_WEATHER_NO_REFS) == []


def test_overall_disagreement_of_two_is_a_failure(doc):
    """CRT-5: a difference of more than 1 is a validation failure."""
    doc["overall"] = 82
    errors = validate_payload(doc, **NO_WEATHER_NO_REFS)
    assert any("overall" in e for e in errors)


# --------------------------------------------------------------------------
# §7.7 / CRT-11 — the retry trigger
# --------------------------------------------------------------------------

MINOR = {"code": "AESTHETIC_MISMATCH", "severity": "minor",
         "affected_pieces": ["p1"], "explanation": "x" * 10}
MAJOR = {"code": "UPLOAD_FIDELITY_BREACH", "severity": "major",
         "affected_pieces": [], "explanation": "x" * 10}
CRITICAL = {"code": "WRONG_OCCASION", "severity": "critical",
            "affected_pieces": [], "explanation": "x" * 10}


def test_no_retry_at_92_with_a_minor_mismatch():
    retry, reason = compute_retry(92, [MINOR])
    assert retry is False
    assert reason == ""


def test_no_retry_at_exactly_70_with_a_minor_mismatch():
    """70 is not below 70, and minor does not trigger."""
    retry, reason = compute_retry(70, [MINOR])
    assert retry is False
    assert reason == ""


def test_retry_at_69_with_a_minor_mismatch():
    retry, reason = compute_retry(69, [MINOR])
    assert retry is True
    assert "below the 70 threshold" in reason


def test_retry_at_92_with_a_major_mismatch():
    retry, reason = compute_retry(92, [MAJOR])
    assert retry is True
    assert "UPLOAD_FIDELITY_BREACH" in reason


def test_retry_at_64_with_a_critical_mismatch_names_the_score_branch_first():
    """Both branches fire; the score branch is named first."""
    retry, reason = compute_retry(64, [CRITICAL])
    assert retry is True
    assert reason.startswith("overall 64 is below the 70 threshold")


def test_no_retry_at_88_with_no_mismatches_and_null_weather():
    """Missing weather alone never triggers a retry."""
    retry, reason = compute_retry(88, [])
    assert retry is False
    assert reason == ""


def test_minor_mismatch_alone_does_not_trigger_at_a_low_score_either():
    """The two branches are independent; a minor mismatch never contributes."""
    retry, reason = compute_retry(95, [MINOR])
    assert retry is False
    assert reason == ""


# --------------------------------------------------------------------------
# finalize_reply — parse, validate, compute, and enforce the server's values
# --------------------------------------------------------------------------

def test_finalize_returns_ok_for_a_valid_document(doc):
    result = finalize_reply(json.dumps(doc), **NO_WEATHER_NO_REFS)
    assert result["status"] == "ok"
    assert result["payload"]["overall"] == 84


def test_finalize_fails_on_unparseable_text():
    result = finalize_reply("not json", **NO_WEATHER_NO_REFS)
    assert result["status"] == "failed"
    assert result["error"] == "invalid_response"


def test_finalize_fails_on_a_schema_violation(doc):
    doc["scores"]["occasion"] = 150
    result = finalize_reply(json.dumps(doc), **NO_WEATHER_NO_REFS)
    assert result["status"] == "failed"
    assert result["error"] == "invalid_response"


def test_finalize_overwrites_the_models_overall(doc):
    doc["overall"] = 84
    result = finalize_reply(json.dumps(doc), **NO_WEATHER_NO_REFS)
    assert result["payload"]["overall"] == 84


def test_finalize_overrides_a_false_retry_the_server_disagrees_with(doc):
    """The server's value is authoritative in both directions (Section 7.6)."""
    doc["retry_recommended"] = True
    doc["retry_reason"] = "the model was over-eager"
    result = finalize_reply(json.dumps(doc), **NO_WEATHER_NO_REFS)
    assert result["payload"]["retry_recommended"] is False
    assert result["payload"]["retry_reason"] == ""


def test_finalize_overrides_a_missing_retry_the_server_requires(doc):
    doc["mismatches"] = [MAJOR]
    doc["overall"] = 84
    doc["retry_recommended"] = False
    doc["retry_reason"] = ""
    result = finalize_reply(json.dumps(doc), **NO_WEATHER_NO_REFS)
    assert result["payload"]["retry_recommended"] is True
    assert "UPLOAD_FIDELITY_BREACH" in result["payload"]["retry_reason"]


def test_finalize_never_leaks_the_raw_reply(doc):
    """Section 7.8: the raw model text is logged server-side only."""
    doc["schema_version"] = "9.9"
    result = finalize_reply(json.dumps(doc), **NO_WEATHER_NO_REFS)
    assert result["status"] == "failed"
    assert result.get("raw_excerpt") is None


def test_finalize_fills_the_missing_weather_and_upload_fidelity_dimensions(doc):
    """CRT-6 and CRT-7: the server sets null for a dimension it could not assess."""
    doc["scores"]["weather"] = None
    doc["weather_assessed"] = False
    doc["scores"]["upload_fidelity"] = None
    doc["upload_fidelity_assessed"] = False
    result = finalize_reply(json.dumps(doc), **NO_WEATHER_NO_REFS)
    assert result["status"] == "ok"
    assert result["payload"]["scores"]["weather"] is None
    assert result["payload"]["scores"]["upload_fidelity"] is None
    assert result["payload"]["overall"] == 84
