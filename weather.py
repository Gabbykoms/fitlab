"""Event-local Open-Meteo forecasts with explicit unavailable results."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import math
import httpx

FIELDS = {'temperature_f': 'temperature_2m', 'feels_like_f': 'apparent_temperature',
          'precipitation_probability': 'precipitation_probability', 'precipitation_mm': 'precipitation',
          'wind_speed_mph': 'wind_speed_10m', 'weather_code': 'weather_code'}


def unavailable(event_date, event_time, city=None, lat=None, lon=None, reason='LOCATION_NOT_FOUND'):
    return dict(available=False, location_name=city, latitude=lat, longitude=lon, timezone=None,
                event_local_datetime=f'{event_date}T{event_time}',
                **{key: None for key in FIELDS}, condition_label=None, layering_advice=None,
                unavailable_reason=reason)


def condition(code):
    if code == 0: return 'Clear'
    if code in (1, 2): return 'Partly cloudy'
    if code == 3: return 'Overcast'
    if code in (45, 48): return 'Fog'
    if code in (51, 53, 55): return 'Drizzle'
    if code in (56, 57, 66, 67): return 'Freezing rain'
    if code in (61, 63, 65, 80, 81, 82): return 'Rain'
    if code in (71, 73, 75, 77, 85, 86): return 'Snow'
    if code in (95, 96, 99): return 'Thunderstorm'
    return 'Unknown conditions'


async def resolve_weather(event_date, event_time, city=None, lat=None, lon=None, client=None):
    result = unavailable(event_date, event_time, city, lat, lon)
    try:
        event = datetime.fromisoformat(f'{event_date}T{event_time}')
    except ValueError:
        return {**result, 'unavailable_reason': 'INVALID_EVENT_TIME'}
    async def resolve(http):
        nonlocal lat, lon, result
        if city:
            response = await http.get('https://geocoding-api.open-meteo.com/v1/search',
                                      params={'name': city, 'count': 1, 'language': 'en'}, timeout=10)
            response.raise_for_status()
            places = response.json().get('results', [])
            if not places:
                return result
            place = places[0]
            lat, lon = place['latitude'], place['longitude']
            result['location_name'] = ', '.join(dict.fromkeys(
                p for p in [place.get('name'), place.get('admin1'), place.get('country')] if p))
        if lat is None or lon is None:
            return result
        result.update(latitude=lat, longitude=lon)
        if not city:
            result['location_name'] = f'Your current location ({lat:.3f}, {lon:.3f})'
        response = await http.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 16,
            'hourly': ','.join(FIELDS.values()), 'temperature_unit': 'fahrenheit',
            'wind_speed_unit': 'mph', 'precipitation_unit': 'mm'}, timeout=10)
        response.raise_for_status()
        forecast = response.json()
        result['timezone'] = forecast['timezone']
        zone = ZoneInfo(forecast['timezone'])
        days = (event.date() - datetime.now(zone).date()).days
        if days < 0 or days >= 16:
            return {**result, 'unavailable_reason': 'OUT_OF_FORECAST_RANGE'}
        # Detect nonexistent wall-clock times across a spring DST transition.
        aware = event.replace(tzinfo=zone)
        if datetime.fromtimestamp(aware.timestamp(), zone).replace(tzinfo=None) != event:
            return {**result, 'unavailable_reason': 'INVALID_EVENT_TIME'}
        hour = event.replace(minute=0, second=0).isoformat(timespec='minutes')
        hourly = forecast['hourly']
        if hour not in hourly['time']:
            return {**result, 'unavailable_reason': 'INVALID_EVENT_TIME'}
        index = hourly['time'].index(hour)
        values = {key: hourly[field][index] for key, field in FIELDS.items()}
        if any(type(value) not in (float, int) or not math.isfinite(value) for value in values.values()):
            raise ValueError()
        temperature = values['feels_like_f']
        advice = 'heavy layers and a coat' if temperature < 45 else 'light layering; a mid-weight jacket' if temperature < 65 else 'light, breathable layers'
        if values['precipitation_probability'] >= 40:
            advice += '; consider rain protection'
        return {**result, **values, 'available': True, 'condition_label': condition(values['weather_code']),
                'layering_advice': advice, 'unavailable_reason': None}
    try:
        if client is not None:
            return await resolve(client)
        async with httpx.AsyncClient() as http:
            return await resolve(http)
    except httpx.RequestError:
        return {**result, 'unavailable_reason': 'NETWORK_ERROR'}
    except (httpx.HTTPStatusError, ValueError, KeyError, TypeError, IndexError):
        return {**result, 'unavailable_reason': 'PROVIDER_ERROR'}
