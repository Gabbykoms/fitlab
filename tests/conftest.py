"""Make repository modules importable with direct pytest invocation.

Adds the offline-safety fixture: every test starts with the OpenRouter API
key stripped from the environment and fails loudly if the openrouter SDK
has been loaded. Production modules keep ``from openrouter`` (and other
provider imports) inside the function that bills, so importing them does
not load the SDK; a test that imports them at module scope fails here
with the test's nodeid in the message, so the mistake is loud, not silent.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _offline_safety(request, monkeypatch):
    """Strip the key and check the SDK is not loaded."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    if "openrouter" in sys.modules:
        pytest.fail(
            f"The openrouter SDK is loaded during {request.node.nodeid!r}. "
            "The offline suite must not import it. Move the import inside "
            "the function that bills."
        )
