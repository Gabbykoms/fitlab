"""Test-only application factory: real routes/storage with offline providers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fakes import FakeProvider, fake_weather

from app import create_app

app = create_app(provider=FakeProvider(), weather_resolver=fake_weather)
