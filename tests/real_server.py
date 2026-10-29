"""Test-only application factory: real routes/storage with offline providers."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from fakes import FakeProvider, fake_weather

app = create_app(provider=FakeProvider(), weather_resolver=fake_weather)
