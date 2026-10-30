"""Styling service orchestration, private storage, and background job lifecycle."""
import asyncio
import hashlib
import json
from pathlib import Path
import sqlite3

from starlette.concurrency import run_in_threadpool
import critique
import db
import media
from provider import OpenRouter, ProviderError
from weather import resolve_weather


class MissingResource(Exception):
    pass


class StylingService:
    def __init__(self, database, storage, provider=None, weather_resolver=None):
        self.database = database
        self.storage = Path(storage)
        self.provider = provider or OpenRouter()
        self.weather_resolver = weather_resolver or resolve_weather
        self.tasks = set()
        self.slots = asyncio.Semaphore(3)

    async def call_db(self, function, *args):
        return await run_in_threadpool(function, self.database, *args)

    def require_provider(self):
        if not self.provider.configured():
            raise ProviderError('The styling service is not configured right now. Please try again later.')

    def wardrobe_view(self, row):
        return {key: row[key] for key in ('id', 'category', 'label', 'created_at')} | {
            'image_data_url': media.read_image(row['upload_path'])}

    async def upload(self, user_id, data, category, label):
        metadata = await run_in_threadpool(media.inspect_image, data)
        digest = hashlib.sha256(data).hexdigest()
        if await self.call_db(db.duplicate_upload, user_id, digest):
            raise ValueError('You already uploaded this item.')
        self.require_provider()
        preflight = await critique.check_upload(self.provider, media.data_url(data, metadata['mime']))
        if preflight['contains_person'] or not preflight['clothing_only']:
            return {'item': None, 'rejected': True, 'code': 'PERSON_DETECTED' if preflight['contains_person'] else 'NOT_CLOTHING',
                    'reason': 'Please upload clothing only — a flat lay or a piece on a hanger. Photos of people are not allowed.'}
        path = await run_in_threadpool(media.store_image, self.storage / 'uploads', data, metadata['extension'])
        try:
            row = await self.call_db(db.add_wardrobe_item, user_id, category, label, path, metadata,
                                     len(data), digest, preflight)
        except BaseException as exc:
            Path(path).unlink(missing_ok=True)
            if isinstance(exc, sqlite3.IntegrityError):
                raise ValueError('You already uploaded this item.') from None
            raise
        return {'item': await run_in_threadpool(self.wardrobe_view, row), 'rejected': False}

    async def wardrobe(self, user_id):
        rows = await self.call_db(db.list_wardrobe_items, user_id)
        return await run_in_threadpool(lambda: [self.wardrobe_view(r) for r in rows])

    async def delete_item(self, user_id, item_id):
        row = await self.call_db(db.get_wardrobe_item, user_id, item_id)
        if not row:
            raise MissingResource()
        if not await self.call_db(db.delete_wardrobe_item, user_id, item_id):
            raise MissingResource()
        await run_in_threadpool(Path(row['upload_path']).unlink, missing_ok=True)

    async def references(self, user_id, item_ids):
        result = []
        for item_id in dict.fromkeys(item_ids):
            row = await self.call_db(db.get_wardrobe_item, user_id, item_id)
            if not row:
                raise MissingResource()
            result.append(await run_in_threadpool(media.read_image, row['upload_path']))
        return result

    async def get_job(self, user_id, job_id):
        job = await self.call_db(db.get_job, user_id, job_id)
        if not job:
            raise MissingResource()
        return job

    async def submit(self, user_id, brief, kind='generate', inherited_weather=None, source_images=None):
        refs = await self.references(user_id, brief.get('selected_item_ids', []))
        if len(refs) + len(source_images or []) > 14:
            raise ValueError('This remix has too many image references. Select fewer wardrobe items or source outfits.')
        self.require_provider()
        job_id = await self.call_db(db.create_job, user_id, kind, brief, inherited_weather)
        task = asyncio.create_task(self.run_job(user_id, job_id, brief, refs, kind, inherited_weather, source_images))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return {'job_id': job_id, 'status': 'queued'}

    async def remix(self, user_id, body):
        source = await self.get_job(user_id, body['source_job_id'])
        if source['status'] != 'complete':
            raise ValueError('Wait for the original outfits to finish before remixing.')
        available = [piece for option in source['options'] for piece in option['pieces']]
        # Resolve complete objects against owned source output; never trust invented garments.
        selected = []
        for candidate in body['selected_pieces']:
            match = next((p for p in available if p == candidate), None)
            if match is None:
                raise ValueError('Choose pieces from this completed outfit request.')
            if match not in selected:
                selected.append(match)
        brief = {**source['brief'], 'preserve_pieces': selected, 'revision_instructions': body['instructions'],
                 'event_date': body['event_date'], 'event_time': body['event_time']}
        if body.get('city'):
            brief.update(city=body['city'], lat=None, lon=None)
        unchanged = all(brief.get(k) == source['brief'].get(k) for k in ('event_date', 'event_time', 'city', 'lat', 'lon'))
        source_options = [o for o in source['options'] if any(p in selected for p in o['pieces'])]
        source_images = await run_in_threadpool(lambda: [media.read_image(o['image_path']) for o in source_options])
        # Source images guide generation; only actual wardrobe uploads count toward fidelity scores.
        return await self.submit(user_id, brief, 'remix', source['weather'] if unchanged else None, source_images)

    async def run_job(self, user_id, job_id, brief, refs, kind, inherited_weather, source_images=None):
        paths = []
        try:
            async with self.slots:
                await self.call_db(db.update_job, user_id, job_id, 'running')
                weather = inherited_weather
                if weather is None:
                    weather = await self.weather_resolver(**{k: brief.get(k) for k in ('event_date', 'event_time', 'city', 'lat', 'lon')})
                await self.call_db(db.update_job, user_id, job_id, 'running', None, weather)
                async def option(index):
                    try:
                        result = await critique.run_option_with_retry(self.provider, brief, weather, refs, index,
                                                                       brief.get('critique_model'),
                                                                       generation_references=[*refs, *(source_images or [])])
                        raw, metadata = result.pop('_raw_bytes'), result.pop('_metadata')
                        path = await run_in_threadpool(media.store_image, self.storage / 'renders', raw, metadata['extension'])
                        paths.append(path)
                        result.pop('image_data_url')
                        return {**result, 'image_path': path}
                    except Exception:
                        return None
                results = await asyncio.gather(*(option(i) for i in range(1 if kind == 'remix' else 3)))
                options = [o for o in results if o is not None]
                if not options:
                    raise ProviderError('The image service could not draw these outfits. Please try again.')
                await self.call_db(db.update_job, user_id, job_id, 'complete', options, weather)
        except asyncio.CancelledError:
            await self.call_db(db.update_job, user_id, job_id, 'failed', None, None,
                               'The server stopped before this request finished. Please try again.')
            for path in paths:
                Path(path).unlink(missing_ok=True)
            raise
        except Exception:
            # Store only controlled wording; upstream exceptions can contain credentials.
            await self.call_db(db.update_job, user_id, job_id, 'failed', None, None,
                               'The outfits could not be generated. Please try again.')
            for path in paths:
                Path(path).unlink(missing_ok=True)

    async def close(self):
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def option_view(self, option):
        try:
            image = media.read_image(option['image_path'])
        except (OSError, ValueError):
            image = ''  # Keep critique text visible when the stored image is unavailable.
        return {k: v for k, v in option.items() if k != 'image_path'} | {'image_data_url': image}

    async def poll(self, user_id, job_id):
        job = await self.get_job(user_id, job_id)
        options = await run_in_threadpool(lambda: [self.option_view(o) for o in job['options']])
        return {'job_id': job_id, 'status': job['status'], 'options': options,
                'weather': job['weather'], 'error': job['error']}

    def look_view(self, row):
        option = json.loads(row['option_json'])
        brief = json.loads(row['brief_json'])
        return {'id': row['id'], 'job_id': row['job_id'], 'option_index': row['option_index'],
                'occasion': row['occasion'], 'event_date': row['event_date'], 'event_time': brief['event_time'],
                'created_at': row['created_at'], 'brief': brief, 'weather': json.loads(row['weather_json']),
                **self.option_view(option)}

    async def save(self, user_id, job_id, option_index):
        job = await self.get_job(user_id, job_id)
        option = next((o for o in job['options'] if o['index'] == option_index), None)
        if job['status'] != 'complete' or option is None:
            raise MissingResource()
        look_id = await self.call_db(db.save_look, user_id, job, option)
        looks = await self.looks(user_id)
        return next(look for look in looks if look['id'] == look_id)

    async def looks(self, user_id, occasion=None, from_date=None, to_date=None):
        rows = await self.call_db(db.list_looks, user_id, occasion, from_date, to_date)
        return await run_in_threadpool(lambda: [self.look_view(row) for row in rows])
