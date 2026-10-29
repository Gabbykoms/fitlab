"""Validated image bytes and private filesystem storage."""
import base64
from io import BytesIO
from pathlib import Path
import secrets
import warnings
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_RENDER_BYTES = 25 * 1024 * 1024
CATEGORIES = {'top', 'bottom', 'outerwear', 'shoes', 'accessory', 'full_outfit'}
FORMATS = {'PNG': ('image/png', '.png'), 'JPEG': ('image/jpeg', '.jpg'),
           'WEBP': ('image/webp', '.webp'), 'GIF': ('image/gif', '.gif')}


def inspect_image(data, limit=MAX_UPLOAD_BYTES):
    if not data or len(data) > limit:
        raise ValueError('That image is empty or exceeds the size limit.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as im:
                if im.format not in FORMATS:
                    raise ValueError('Please upload a PNG, JPEG, WebP or GIF.')
                fmt, size = im.format, im.size
                if size[0] * size[1] > 25_000_000:
                    raise ValueError('That image has too many pixels. Please resize it.')
                im.verify()
            with Image.open(BytesIO(data)) as im:
                im.load()
        mime, extension = FORMATS[fmt]
        return {'mime': mime, 'extension': extension, 'width': size[0], 'height': size[1]}
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('That file could not be decoded as a supported image.') from None


def data_url(data, mime):
    return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')


def decode_url(url):
    if not isinstance(url, str) or not url.startswith('data:image/') or ';base64,' not in url:
        raise ValueError('The image service returned an unsupported image.')
    encoded = url.split(';base64,', 1)[1]
    if len(encoded) > MAX_RENDER_BYTES * 4 // 3 + 4:
        raise ValueError('The generated image exceeds the size limit.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise ValueError('The image service returned an invalid image.') from None
    return raw, inspect_image(raw, MAX_RENDER_BYTES)


def store_image(root, data, extension):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (secrets.token_hex(16) + extension)
    try:
        with path.open('xb') as stream:
            stream.write(data)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return str(path.resolve())


def read_image(path):
    raw = Path(path).read_bytes()
    metadata = inspect_image(raw, MAX_RENDER_BYTES)
    return data_url(raw, metadata['mime'])
