"""HTTP request contracts shared by generation and weather routes."""
from datetime import date, time, datetime, timezone, timedelta
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class Event(BaseModel):
    event_date: date
    event_time: str = Field(pattern=r'^\d{2}:\d{2}$')
    city: str | None = Field(default=None, max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    lon: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)

    @field_validator('event_time')
    @classmethod
    def valid_time(cls, value):
        time.fromisoformat(value)
        return value

    @field_validator('city')
    @classmethod
    def clean_city(cls, value):
        return value.strip() or None if value else None

    @model_validator(mode='after')
    def coordinates(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError('Provide both latitude and longitude.')
        # The location's timezone is resolved by weather.py; permit yesterday
        # in UTC so a valid local date west of UTC is not rejected prematurely.
        if self.event_date < datetime.now(timezone.utc).date() - timedelta(days=1):
            raise ValueError('The event date cannot be in the past.')
        return self


class GenerateBody(Event):
    occasion: str = Field(min_length=1, max_length=200)
    aesthetic: str = Field(min_length=1, max_length=200)
    styling_preference: Literal['masculine', 'feminine', 'unisex']
    selected_item_ids: list[int] = Field(default_factory=list, max_length=12)
    notes: str | None = Field(default=None, max_length=1000)
    critique_model: str | None = Field(default=None, max_length=100)

    @field_validator('occasion', 'aesthetic')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('This field must not be blank.')
        return value.strip()


class RemixBody(BaseModel):
    source_job_id: str = Field(min_length=1, max_length=100)
    selected_pieces: list[dict] = Field(min_length=1, max_length=12)
    instructions: str = Field(default='', max_length=1000)
    event_date: date
    event_time: str = Field(pattern=r'^\d{2}:\d{2}$')
    city: str | None = Field(default=None, max_length=120)

    @model_validator(mode='after')
    def event(self):
        Event(event_date=self.event_date, event_time=self.event_time, city=self.city)
        return self


class SaveBody(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    option_index: int = Field(ge=0, le=2)
