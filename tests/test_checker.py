"""The Checker's offline tests. Hand-built critiques only — no model, no key.

The Checker compares the critic's checklist with the brief's requirements and
reports what it can prove: which requirements were answered, which were unmet,
which the critic did not answer, and which the critic invented. It does not
look at the image and never says why.
"""
import json
from pathlib import Path

import pytest

from checker import check

REPO = Path(__file__).resolve().parents[1]


def test_all_met_is_ok():
    requirements = ["the dress is blue", "the dress is floor-length"]
    critique = {
        "checks": [
            {"requirement": "the dress is blue", "met": True, "evidence": "the dress is blue"},
            {"requirement": "the dress is floor-length", "met": True, "evidence": "ankle-length"},
        ]
    }
    result = check(requirements, critique)
    assert result["ok"] is True
    assert result["unmet"] == []
    assert result["missing"] == []
    assert result["extra"] == []
    assert result["problems"] == []


def test_one_unmet_is_named():
    requirements = ["the blazer is navy", "the shirt is white"]
    critique = {
        "checks": [
            {"requirement": "the blazer is navy", "met": True, "evidence": "navy"},
            {"requirement": "the shirt is white", "met": False, "evidence": "pale blue"},
        ]
    }
    result = check(requirements, critique)
    assert result["ok"] is False
    assert "the shirt is white" in result["unmet"]
    assert "the blazer is navy" not in result["unmet"]
    assert "the shirt is white" not in result["missing"]


def test_missing_requirement_is_named():
    requirements = ["the shoes are black", "the bag is leather"]
    critique = {
        "checks": [
            {"requirement": "the shoes are black", "met": True, "evidence": "black"},
        ]
    }
    result = check(requirements, critique)
    assert result["ok"] is False
    assert "the bag is leather" in result["missing"]
    assert "the bag is leather" not in result["unmet"]
    assert "the bag is leather" not in result["extra"]


def test_invented_requirement_is_named():
    requirements = ["the tie is silk"]
    critique = {
        "checks": [
            {"requirement": "the tie is silk", "met": True, "evidence": "silk"},
            {"requirement": "the cufflinks are silver", "met": True, "evidence": "silver"},
        ]
    }
    result = check(requirements, critique)
    assert result["ok"] is False
    assert "the cufflinks are silver" in result["extra"]
    assert "the cufflinks are silver" not in result["unmet"]
    assert "the cufflinks are silver" not in result["missing"]


def test_verdict_attributes_no_cause():
    """The verdict names what the critic said; it never says why."""
    requirements = ["the shoes are black"]
    critique = {
        "checks": [
            {"requirement": "the shoes are black", "met": False, "evidence": "they are brown"},
        ]
    }
    result = check(requirements, critique)
    text = " ".join(result["problems"]).lower()
    # No claim about the image or the critic being wrong.
    assert "image failed" not in text
    assert "critic was wrong" not in text
    assert "model misread" not in text
    assert "image is wrong" not in text


def test_evidence_manifest_is_well_formed():
    """evidence/image-set/manifest.json has five entries, four requirements each."""
    manifest_path = REPO / "evidence" / "image-set" / "manifest.json"
    if not manifest_path.exists():
        pytest.fail(
            f"Missing evidence manifest at {manifest_path}. "
            "Copy ../cpsc415-week05/week06/images/manifest.json there by hand."
        )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(data, list), "manifest must be a JSON array"
    assert len(data) == 5, f"manifest must have 5 entries (image-01..image-05); got {len(data)}"
    for entry in data:
        reqs = entry.get("requirements")
        assert isinstance(reqs, list), f"{entry.get('name')!r}: requirements must be a list"
        assert len(reqs) == 4, f"{entry.get('name')!r}: expected 4 requirements; got {len(reqs)}"
        for req in reqs:
            assert isinstance(req, str) and req, "each requirement must be a non-empty string"
