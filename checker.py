"""The Checker: in plain code, no model, no key, no SDK.

Compares the critic's checklist with the brief's projected requirements and
reports what the comparison can prove. The Checker does not look at the
image; it attributes no cause. A report names the requirement and what the
critic said, never that the image failed or that the critic was wrong.

This module is imported by ``tests.test_checker`` and by
``critique.finalize_reply`` when the server wires up the checklist check.
It must not import ``openrouter``; the offline-safety fixture in
``tests/conftest.py`` asserts that.
"""
import json
import re


def check(requirements, critique):
    """Compare a critic's checklist with the brief's requirements.

    ``requirements`` is the list of items the brief asked for. ``critique``
    is the parsed JSON document from the critic; its ``checks`` field is a
    list of ``{"requirement", "met", "evidence"}`` items, or it is missing
    or malformed. ``critique`` may also be ``None`` if the reply was not
    a JSON object.

    Returns a verdict: ``ok`` is ``True`` iff every requirement was answered,
    only those requirements were answered, and every answer was ``True``.
    ``problems`` is a list of human-readable summaries. ``unmet``,
    ``missing``, and ``extra`` are lists of requirement text, exactly as
    the brief or the critic wrote it.
    """
    if not isinstance(critique, dict) or not isinstance(critique.get("checks"), list):
        return {
            "ok": False,
            "problems": ["critique was not the JSON checklist that was asked for"],
            "unmet": [],
            "missing": list(requirements),
            "extra": [],
        }

    answered = {}
    for c in critique["checks"]:
        if isinstance(c, dict) and isinstance(c.get("requirement"), str):
            answered[_norm(c["requirement"])] = c

    wanted = {_norm(r): r for r in requirements}

    missing = [r for k, r in wanted.items() if k not in answered]
    extra = [
        c["requirement"] for k, c in answered.items() if k not in wanted
    ]
    unmet = [
        r for k, r in wanted.items()
        if k in answered and answered[k].get("met") is not True
    ]

    problems = []
    if missing:
        problems.append(f"critic did not answer {len(missing)} requirement(s)")
    if extra:
        problems.append(f"critic answered {len(extra)} item(s) that were not asked")
    if unmet:
        problems.append(f"{len(unmet)} requirement(s) reported unmet")

    return {
        "ok": not problems,
        "problems": problems,
        "unmet": unmet,
        "missing": missing,
        "extra": extra,
    }


def extract_json(text):
    """The JSON object inside a reply, or ``None``. Models wrap JSON in fences or prose.

    The regex is greedy and ``re.DOTALL``, so it captures from the first ``{``
    to the last ``}``. If that span is not valid JSON, or is not an object,
    the reply is treated as a failed critique: returns ``None``. Never raises.
    """
    if text is None:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _norm(s):
    """Fold case, punctuation, and whitespace so two ways of writing the same
    requirement match. Stops short of folding letters together — "navy" and
    "navi" must still differ.
    """
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
