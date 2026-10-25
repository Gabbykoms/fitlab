"""Critique module: parse, validate, score, and decide the retry.

This module implements the normative contract in ``spec.md`` Section 7.
The model proposes; the server disposes. Specifically:

* ``parse_reply`` turns a raw model reply into a JSON object, including
  the case where the JSON is wrapped in prose, a reasoning trace, or a
  fenced code block (CRT-3).
* ``validate_payload`` checks every required field and its type against
  the Section 7 schema. A violation is a failure, never a coercion
  (CRT-4).
* ``compute_overall`` applies the weighting rule from Section 7.4. The
  overall score is always computed here, never read from the model
  (CRT-5).
* ``compute_retry`` applies the retry trigger from Section 7.6 exactly:
  ``overall < 70`` or any ``major``/``critical`` mismatch.

No model calls live here yet. This module is pure: it never touches the
network, never reads a key, and never writes to disk.
"""

import json
import re

SCHEMA_VERSION = "1.0"

# Section 7.4 — weights, as integers summing to 100.
WEIGHTS = {
    "occasion": 30,
    "aesthetic": 25,
    "styling": 20,
    "weather": 15,
    "upload_fidelity": 10,
}

# The three dimensions that are always assessed, weather and upload
# fidelity only when the corresponding inputs exist.
ALWAYS_ASSESSED = ("occasion", "aesthetic", "styling")

# Section 7.2 — required keys of ``scores``.
SCORE_KEYS = ("occasion", "aesthetic", "styling", "weather", "upload_fidelity")

# Section 7.5 — the mismatch code enum.
MISMATCH_CODES = frozenset(
    {
        "WRONG_OCCASION",
        "WRONG_FORMALITY",
        "AESTHETIC_MISMATCH",
        "STYLING_PREFERENCE_MISMATCH",
        "WEATHER_UNSUITABLE",
        "UPLOAD_FIDELITY_BREACH",
        "MISSING_EXPECTED_PIECE",
        "EXTRA_UNEXPECTED_PIECE",
        "ILLEGIBLE_IMAGE",
    }
)

# Section 7.5 — the severity enum, and which severities trigger a retry.
SEVERITIES = frozenset({"minor", "major", "critical"})
RETRYING_SEVERITIES = frozenset({"major", "critical"})

# Section 7.6 — a retry fires on a score strictly below this threshold.
RETRY_THRESHOLD = 70

# Section 7.2 — size limits.
MAX_LIST_ENTRIES = 8
MAX_AFFECTED_PIECES = 6
MAX_SUMMARY_CHARS = 600
MIN_SUMMARY_CHARS = 1
MAX_TEXT_CHARS = 300
MAX_EXPLANATION_CHARS = 500
MIN_EXPLANATION_CHARS = 1

# Section 7.8 — the error vocabulary of the failure document.
ERROR_INVALID_RESPONSE = "invalid_response"


class CritiqueParseError(Exception):
    """Raised when a model reply cannot be parsed into a JSON object."""


def _loads_object(text):
    """``json.loads`` ``text`` and require the result to be an object.

    Returns the object, or ``None`` when the text is not a JSON object.
    """
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _strip_fence(text):
    """Remove a fenced code-block wrapper, keeping the fenced body.

    Handles both ```` ```json ```` and a bare ```` ``` ```` fence, and a
    fence that is never closed. Returns the text unchanged when there is
    no fence.
    """
    match = re.search(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)(?:```|\Z)", text, re.DOTALL)
    if not match:
        return text
    return match.group(2)


def _strip_reasoning(text):
    """Drop a leading reasoning trace from in front of the JSON.

    Reasoning models emit prose before the document. The document starts
    at the first ``{``; anything before it is reasoning and is dropped.
    """
    start = text.find("{")
    if start == -1:
        return text
    return text[start:]


def _outermost_object(text):
    """Extract the outermost ``{...}`` substring, respecting strings.

    Brace counting ignores braces inside JSON string literals so that a
    ``"{"`` inside an explanation does not end the document early.
    Returns ``None`` when there is no balanced object.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def parse_reply(raw_text):
    """Parse a model reply into a JSON object.

    Tries ``json.loads`` first. On failure it applies exactly two
    repairs, in order (CRT-3):

    (a) strip a leading reasoning trace and any fenced code-block
        wrapper;
    (b) extract the outermost ``{...}`` substring.

    Raises ``CritiqueParseError`` if neither yields a JSON object.
    """
    if not isinstance(raw_text, str):
        raise CritiqueParseError("model reply was not text")

    direct = _loads_object(raw_text)
    if direct is not None:
        return direct

    # Repair (a): strip the reasoning trace and the code fence.
    repaired = _strip_fence(_strip_reasoning(raw_text))
    via_a = _loads_object(repaired)
    if via_a is not None:
        return via_a

    # Repair (b): pull the outermost object out of the surrounding prose.
    candidate = _outermost_object(repaired)
    if candidate is not None:
        via_b = _loads_object(candidate)
        if via_b is not None:
            return via_b

    # The fence may have hidden prose rather than the document itself.
    candidate = _outermost_object(raw_text)
    if candidate is not None:
        via_b = _loads_object(candidate)
        if via_b is not None:
            return via_b

    raise CritiqueParseError("model reply did not contain a JSON object")


# --------------------------------------------------------------------------
# Validation (CRT-4) — every required field, every type, every constraint
# --------------------------------------------------------------------------


def _is_int(value):
    """True when ``value`` is a Python ``int`` but not a ``bool``.

    ``True`` and ``False`` are subclasses of ``int`` in Python, but a
    Section 7 score is never a boolean.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def _check_str_list(field, value, max_chars, errors):
    """Validate a list of short text entries, appending any errors."""
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    if len(value) > MAX_LIST_ENTRIES:
        errors.append(f"{field} has more than {MAX_LIST_ENTRIES} entries")
        return
    for index, entry in enumerate(value):
        if not isinstance(entry, str):
            errors.append(f"{field}[{index}] must be a string")
            continue
        if not (1 <= len(entry) <= max_chars):
            errors.append(
                f"{field}[{index}] must be {1}-{max_chars} characters"
            )


def _check_score(field, value, errors):
    """Validate a single dimension score (int, 0-100 inclusive)."""
    if not _is_int(value):
        errors.append(f"scores.{field} must be an integer between 0 and 100")
        return
    if not 0 <= value <= 100:
        errors.append(f"scores.{field} must be an integer between 0 and 100")


def _check_optional_score(field, value, assessed, errors):
    """Validate a dimension score that is ``None`` unless it was assessed."""
    if not assessed:
        if value is not None:
            errors.append(
                f"scores.{field} must be null when {field} was not assessed"
            )
        return
    _check_score(field, value, errors)


def _check_mismatch_list(mismatches, errors):
    """Validate the ``mismatches`` array element by element."""
    if not isinstance(mismatches, list):
        errors.append("mismatches must be a list")
        return
    if len(mismatches) > MAX_LIST_ENTRIES:
        errors.append(f"mismatches has more than {MAX_LIST_ENTRIES} entries")
        return
    for index, item in enumerate(mismatches):
        prefix = f"mismatches[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for required in ("code", "severity", "affected_pieces", "explanation"):
            if required not in item:
                errors.append(f"{prefix} is missing {required!r}")
        if "code" in item and item["code"] not in MISMATCH_CODES:
            errors.append(f"{prefix}.code {item['code']!r} is not a known mismatch code")
        if "severity" in item and item["severity"] not in SEVERITIES:
            errors.append(
                f"{prefix}.severity {item['severity']!r} is not one of minor, major, critical"
            )
        pieces = item.get("affected_pieces")
        if isinstance(pieces, list) and len(pieces) > MAX_AFFECTED_PIECES:
            errors.append(
                f"{prefix}.affected_pieces has more than {MAX_AFFECTED_PIECES} entries"
            )
        explanation = item.get("explanation")
        if isinstance(explanation, str) and not (
            MIN_EXPLANATION_CHARS <= len(explanation) <= MAX_EXPLANATION_CHARS
        ):
            errors.append(
                f"{prefix}.explanation must be {MIN_EXPLANATION_CHARS}-{MAX_EXPLANATION_CHARS} characters"
            )


def validate_payload(doc, *, weather_available, references_supplied):
    """Validate a parsed critique against the Section 7 schema.

    Returns a list of error messages; an empty list means the document
    passes every check. The function never raises on a schema violation:
    the caller decides what to do with the failure.
    """
    errors = []
    if not isinstance(doc, dict):
        return ["document must be an object"]

    if doc.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")

    attempt = doc.get("attempt")
    if not _is_int(attempt) or attempt < 1:
        errors.append("attempt must be an integer of at least 1")

    model = doc.get("model")
    if not isinstance(model, str) or not model:
        errors.append("model must be a non-empty string")

    scores = doc.get("scores")
    if not isinstance(scores, dict):
        errors.append("scores must be an object")
        scores = {}

    # CRT-6 / CRT-7 — the server decides whether a dimension was assessed.
    weather_assessed = bool(weather_available)
    fidelity_assessed = bool(references_supplied)

    # The doc must mirror the server-side decision.
    doc_weather_assessed = doc.get("weather_assessed")
    doc_fidelity_assessed = doc.get("upload_fidelity_assessed")

    if doc_weather_assessed != weather_assessed:
        errors.append(
            "weather_assessed does not match the server's assessment "
            f"(expected {weather_assessed})"
        )
    if doc_fidelity_assessed != fidelity_assessed:
        errors.append(
            "upload_fidelity_assessed does not match the server's assessment "
            f"(expected {fidelity_assessed})"
        )

    # Required keys, always.
    for key in ALWAYS_ASSESSED:
        if key not in scores:
            errors.append(f"scores.{key} is required")
        else:
            _check_score(key, scores[key], errors)

    # Keys whose presence is required (Section 7.2) and whose value is
    # null when the dimension was not assessed.
    if "weather" not in scores:
        errors.append("scores.weather is required")
    else:
        _check_optional_score("weather", scores["weather"], weather_assessed, errors)

    if "upload_fidelity" not in scores:
        errors.append("scores.upload_fidelity is required")
    else:
        _check_optional_score(
            "upload_fidelity",
            scores["upload_fidelity"],
            fidelity_assessed,
            errors,
        )

    # overall — Section 7.4 + CRT-5.
    overall = doc.get("overall")
    overall_valid = True
    if not _is_int(overall) or not 0 <= overall <= 100:
        errors.append("overall must be an integer between 0 and 100")
        overall_valid = False
    if overall_valid and isinstance(scores, dict):
        # CRT-5: the server's value is authoritative, with a tolerance of 1.
        try:
            server_overall = compute_overall(
                scores,
                weather_available=weather_available,
                references_supplied=references_supplied,
            )
            if abs(overall - server_overall) > 1:
                errors.append(
                    "overall does not match the server's weighted computation "
                    f"(model returned {overall}, server computed {server_overall})"
                )
        except ValueError:
            # No assessed dimensions — caught by the schema check above.
            pass

    # summary.
    summary = doc.get("summary")
    if not isinstance(summary, str):
        errors.append("summary must be a string")
    elif not (MIN_SUMMARY_CHARS <= len(summary) <= MAX_SUMMARY_CHARS):
        errors.append(
            f"summary must be {MIN_SUMMARY_CHARS}-{MAX_SUMMARY_CHARS} characters"
        )

    # matches / uncertainty — list of short text.
    _check_str_list("matches", doc.get("matches"), MAX_TEXT_CHARS, errors)
    _check_str_list("uncertainty", doc.get("uncertainty"), MAX_TEXT_CHARS, errors)

    # mismatches — structured.
    _check_mismatch_list(doc.get("mismatches"), errors)

    # retry_recommended / retry_reason — boolean plus a non-empty reason
    # when the model asks for one, empty when it does not.
    retry_recommended = doc.get("retry_recommended")
    retry_reason = doc.get("retry_reason")
    if not isinstance(retry_recommended, bool):
        errors.append("retry_recommended must be a boolean")
    if not isinstance(retry_reason, str):
        errors.append("retry_reason must be a string")
        retry_reason = None
    if isinstance(retry_recommended, bool) and isinstance(retry_reason, str):
        if retry_recommended and not retry_reason:
            errors.append("retry_reason must be a non-empty string when retry_recommended is true")
        if not retry_recommended and retry_reason:
            errors.append("retry_reason must be empty when retry_recommended is false")

    return errors


# --------------------------------------------------------------------------
# §7.4 / CRT-5 — the overall score, computed server-side
# --------------------------------------------------------------------------


def _assessed_dimensions(scores, *, weather_available, references_supplied):
    """Yield ``(name, value)`` for every dimension the server will score."""
    for name in ALWAYS_ASSESSED:
        if name in scores and _is_int(scores[name]):
            yield name, scores[name]
    if weather_available and "weather" in scores and _is_int(scores["weather"]):
        yield "weather", scores["weather"]
    if references_supplied and "upload_fidelity" in scores and _is_int(scores["upload_fidelity"]):
        yield "upload_fidelity", scores["upload_fidelity"]


def _round_half_up(value):
    """Round to the nearest integer, with ``.5`` going up.

    Python's built-in ``round`` uses banker's rounding (``.5`` to even),
    which would not match the Section 7.4 worked examples.
    """
    floor = int(value)
    if value - floor >= 0.5:
        return floor + 1
    return floor


def compute_overall(scores, *, weather_available, references_supplied):
    """Apply the Section 7.4 weighting rule.

    The denominator is the sum of the weights of the assessed dimensions
    only — never 100. Raises ``ValueError`` when there is nothing to
    score (which Section 7.2 makes impossible, but we guard anyway).
    """
    numerator = 0
    denominator = 0
    for name, value in _assessed_dimensions(
        scores, weather_available=weather_available, references_supplied=references_supplied
    ):
        numerator += WEIGHTS[name] * value
        denominator += WEIGHTS[name]

    if denominator == 0:
        raise ValueError("no assessed dimensions")

    return _round_half_up(numerator / denominator)


# --------------------------------------------------------------------------
# §7.6 / §7.7 / CRT-11 — the retry trigger
# --------------------------------------------------------------------------


def _triggering_mismatch(mismatches):
    """Return the first major/critical mismatch, or ``None``."""
    for item in mismatches:
        severity = item.get("severity") if isinstance(item, dict) else None
        if severity in RETRYING_SEVERITIES:
            return item
    return None


def compute_retry(overall, mismatches):
    """Apply the retry rule from Section 7.6 exactly.

    Returns ``(retry_recommended, retry_reason)``. The score branch is
    named first when both branches fire; ``retry_reason`` is ``""`` when
    no retry is recommended.
    """
    score_below = overall < RETRY_THRESHOLD
    trigger = _triggering_mismatch(mismatches)

    if not (score_below or trigger):
        return False, ""

    if score_below:
        return True, f"overall {overall} is below the {RETRY_THRESHOLD} threshold"

    severity = trigger["severity"]
    code = trigger.get("code", "UNKNOWN")
    return True, f"one {severity} mismatch: {code}"


# --------------------------------------------------------------------------
# finalize_reply — parse, validate, compute, and overwrite
# --------------------------------------------------------------------------


def _normalize_payload(doc, *, weather_available, references_supplied):
    """Apply CRT-6 and CRT-7: null out dimensions the server could not score."""
    out = dict(doc)
    scores = dict(out.get("scores") or {})
    if not weather_available:
        scores["weather"] = None
    if not references_supplied:
        scores["upload_fidelity"] = None
    out["scores"] = scores
    out["weather_assessed"] = bool(weather_available)
    out["upload_fidelity_assessed"] = bool(references_supplied)
    return out


def finalize_reply(raw_text, *, weather_available, references_supplied):
    """Parse, validate, compute, and produce the server-authoritative payload.

    On success returns ``{"status": "ok", "payload": <section 7 doc>}``.
    On failure returns ``{"status": "failed", "error": "invalid_response"}``.
    The raw model text is never returned (Section 7.8).
    """
    try:
        doc = parse_reply(raw_text)
    except CritiqueParseError:
        return {"status": "failed", "error": ERROR_INVALID_RESPONSE}

    errors = validate_payload(
        doc, weather_available=weather_available, references_supplied=references_supplied
    )
    if errors:
        return {"status": "failed", "error": ERROR_INVALID_RESPONSE}

    normalized = _normalize_payload(
        doc, weather_available=weather_available, references_supplied=references_supplied
    )

    # CRT-5: the server always overwrites ``overall``.
    server_overall = compute_overall(
        normalized["scores"],
        weather_available=weather_available,
        references_supplied=references_supplied,
    )
    normalized["overall"] = server_overall

    # Section 7.6: the server's retry value is authoritative in both directions.
    retry_recommended, retry_reason = compute_retry(
        server_overall, normalized.get("mismatches") or []
    )
    normalized["retry_recommended"] = retry_recommended
    normalized["retry_reason"] = retry_reason

    return {"status": "ok", "payload": normalized}
