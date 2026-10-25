"""Critique module — STUB.

The real implementation lands in the next commit. This stub exists so that
``tests/test_critique.py`` collects and every test fails against a known
shape of the public API rather than at import time.

Public API (normative source: spec.md Section 7):

    parse_reply(raw_text) -> dict
    validate_payload(doc, *, weather_available, references_supplied) -> list[str]
    compute_overall(scores, *, weather_available, references_supplied) -> int
    compute_retry(overall, mismatches) -> tuple[bool, str]
    finalize_reply(raw_text, *, weather_available, references_supplied) -> dict
"""

SCHEMA_VERSION = "1.0"

WEIGHTS = {
    "occasion": 30,
    "aesthetic": 25,
    "styling": 20,
    "weather": 15,
    "upload_fidelity": 10,
}


class CritiqueParseError(Exception):
    """Raised when a model reply cannot be parsed into a JSON object."""


def parse_reply(raw_text: str) -> dict:
    raise NotImplementedError


def validate_payload(
    doc: dict, *, weather_available: bool, references_supplied: bool
) -> list[str]:
    raise NotImplementedError


def compute_overall(
    scores: dict, *, weather_available: bool, references_supplied: bool
) -> int:
    raise NotImplementedError


def compute_retry(overall: int, mismatches: list) -> tuple:
    raise NotImplementedError


def finalize_reply(
    raw_text: str, *, weather_available: bool, references_supplied: bool
) -> dict:
    raise NotImplementedError
