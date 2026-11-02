"""OpenRouter transport. Never propagate provider text or credentials in errors."""
import logging
import os
import httpx

DEFAULT_IMAGE_MODEL = 'google/gemini-3.1-flash-image'
DEFAULT_CRITIQUE_MODEL = 'xiaomi/mimo-v2.6-flash'
NOT_CONFIGURED = 'The styling service is not configured right now. Please try again later.'
# 401 bad key, 402 credits too low for the request's worst-case cost, 403 key spending limit reached.
ACCOUNT_STATUSES = (401, 402, 403)
log = logging.getLogger('fitlab.provider')


class ProviderError(Exception):
    pass


class ProviderUnavailable(ProviderError):
    """The account or key cannot be used; retrying will not help until an operator fixes it."""


class OpenRouter:
    supports_image_seed = False  # Default dedicated-image endpoint does not advertise seed support.
    def __init__(self, client=None):
        self.client = client
        self.image_model = os.environ.get('FITLAB_IMAGE_MODEL', DEFAULT_IMAGE_MODEL)
        self.critique_model = os.environ.get('FITLAB_CRITIQUE_MODEL', DEFAULT_CRITIQUE_MODEL)

    def configured(self):
        return bool(os.environ.get('OPENROUTER_API_KEY'))

    async def call(self, endpoint, body):
        key = os.environ.get('OPENROUTER_API_KEY')
        if not key:
            raise ProviderUnavailable(NOT_CONFIGURED)
        async def send(client):
            try:
                response = await client.post('https://openrouter.ai/api/v1/' + endpoint,
                    headers={'Authorization': f'Bearer {key}'}, json=body, timeout=120)
            except httpx.HTTPError as exc:
                log.warning('OpenRouter %s request failed: %s', endpoint, type(exc).__name__)
                raise ProviderError('The styling service did not respond properly. Please try again.') from None
            # Log the status only: response bodies can echo request details and must never be logged.
            if response.status_code in ACCOUNT_STATUSES:
                log.error('OpenRouter %s refused with HTTP %s; check the key, its limit and account credits',
                          endpoint, response.status_code)
                raise ProviderUnavailable(NOT_CONFIGURED)
            if response.status_code == 429:
                log.warning('OpenRouter %s rate limited (HTTP 429)', endpoint)
                raise ProviderError('The image service is busy right now. Please try again in a minute.')
            try:
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict) or 'error' in result:
                    raise ValueError()
                return result
            except (httpx.HTTPError, ValueError):
                log.warning('OpenRouter %s returned an unusable response (HTTP %s)', endpoint, response.status_code)
                raise ProviderError('The styling service did not respond properly. Please try again.') from None
        if self.client is not None:
            return await send(self.client)
        async with httpx.AsyncClient() as client:
            return await send(client)

    async def vision(self, prompt, images, model=None):
        model = model or self.critique_model
        content = [{'type': 'text', 'text': prompt}]
        content += [{'type': 'image_url', 'image_url': {'url': image}} for image in images]
        body = {'model': model, 'messages': [{'role': 'user', 'content': content}],
                'max_tokens': 2500}
        if model.startswith('xiaomi/'):
            body['reasoning'] = {'enabled': False}
        result = await self.call('chat/completions', body)
        try:
            text = result['choices'][0]['message']['content']
            if not isinstance(text, str):
                raise ValueError()
            return text, usage_of(result)
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError('The review service returned an invalid response.') from None

    async def image(self, prompt, references, seed):
        result = await self.call('images', {
            'model': self.image_model, 'prompt': prompt, 'n': 1,
            'input_references': [{'type': 'image_url', 'image_url': {'url': image}} for image in references],
        })
        try:
            item = result['data'][0]
            image = f"data:{item.get('media_type', 'image/png')};base64,{item['b64_json']}"
            return image, usage_of(result)
        except (KeyError, IndexError, TypeError):
            raise ProviderError('The image service returned no image. Please try again.') from None


def usage_of(result):
    usage = result.get('usage') or {}
    # A missing reported cost is unknown, never silently recorded as free.
    return {'prompt_tokens': usage.get('prompt_tokens', 0),
            'completion_tokens': usage.get('completion_tokens', 0), 'cost_usd': usage.get('cost')}
