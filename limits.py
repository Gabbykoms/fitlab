"""Bound multipart request bodies before Starlette parses/spools uploads."""
from starlette.responses import JSONResponse
from media import MAX_UPLOAD_BYTES


class UploadBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'].rstrip('/') != '/api/wardrobe/upload':
            return await self.app(scope, receive, send)
        # Allow only small multipart overhead beyond a single 10 MB file. The
        # endpoint separately enforces the exact file size after parsing.
        limit = MAX_UPLOAD_BYTES + 64 * 1024
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = 0
        async def reject():
            await JSONResponse({'detail': 'That file is larger than 10 MB.'}, status_code=413)(scope, receive, send)
        if declared > limit:
            return await reject()
        messages, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > limit:
                return await reject()
            messages.append(message)
            if not message.get('more_body', False):
                break
        iterator = iter(messages)
        async def replay():
            return next(iterator, {'type': 'http.request', 'body': b'', 'more_body': False})
        await self.app(scope, replay, send)
