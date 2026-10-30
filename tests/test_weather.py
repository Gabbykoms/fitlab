from fakes import run_async
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
import pytest
from weather import resolve_weather, FIELDS


def request_weather(handler, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await resolve_weather(client=client, **kwargs)
    return run_async(run)


def event():
    return {'event_date': (datetime.now(ZoneInfo('America/New_York')).date() + timedelta(days=1)).isoformat(),
            'event_time': '18:30'}


def forecast(params):
    return {'timezone': 'America/New_York', 'hourly': {
        'time': [params['event_date'] + 'T18:00'],
        **{field: [value] for field, value in zip(FIELDS.values(), [52, 50, 60, 1, 10, 3])}}}


def test_city_override_hour_selection_and_units():
    calls = []
    params = event()
    def handler(request):
        calls.append(request)
        if 'geocoding' in request.url.host:
            return httpx.Response(200, json={'results': [{'name': 'Hartford', 'admin1': 'Connecticut',
                'country': 'United States', 'latitude': 41.7, 'longitude': -72.6}]})
        assert request.url.params['latitude'] == '41.7'
        assert request.url.params['temperature_unit'] == 'fahrenheit'
        assert request.url.params['timezone'] == 'auto'
        return httpx.Response(200, json=forecast(params))
    result = request_weather(handler, **params, city='Hartford', lat=0, lon=0)
    assert result['available'] is True
    assert result['event_local_datetime'].endswith('18:30')
    assert result['condition_label'] == 'Overcast'
    assert result['temperature_f'] == 52 and 'rain' in result['layering_advice']
    assert len(calls) == 2


def test_missing_location_makes_no_call():
    result = request_weather(lambda r: pytest.fail('unexpected request'), **event())
    assert result['unavailable_reason'] == 'LOCATION_NOT_FOUND'


@pytest.mark.parametrize('mode,reason', [('network', 'NETWORK_ERROR'), ('malformed', 'PROVIDER_ERROR'),
                                       ('http', 'PROVIDER_ERROR'), ('missing', 'LOCATION_NOT_FOUND')])
def test_weather_failure_is_explicit(mode, reason):
    def handler(request):
        if mode == 'network':
            raise httpx.ConnectError('offline', request=request)
        return httpx.Response(500 if mode == 'http' else 200,
                              json={} if mode in ('missing', 'http') else {'results': [None]})
    result = request_weather(handler, **event(), city='Hartford')
    assert result['available'] is False
    assert result['temperature_f'] is None
    assert result['unavailable_reason'] == reason


def test_far_future_and_missing_hour():
    params = event()
    result = request_weather(lambda r: httpx.Response(200, json=forecast(params)),
                             **{**params, 'event_date': '2099-01-01'}, lat=42, lon=-72)
    assert result['unavailable_reason'] == 'OUT_OF_FORECAST_RANGE'
    result = request_weather(lambda r: httpx.Response(200, json=forecast(params)),
                             **{**params, 'event_time': '19:00'}, lat=42, lon=-72)
    assert result['unavailable_reason'] == 'INVALID_EVENT_TIME'
