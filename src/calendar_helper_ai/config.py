"""Runtime configuration and public upload limits."""
import os
import secrets
from importlib.metadata import version

APP_VERSION = version('calendar-helper-ai')
MAX_IMAGE_SIZE = 4 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/tiff'}


def environment_config():
    """Read runtime settings when creating an app, rather than during imports."""
    return {
        'SECRET_KEY': os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32),
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
        'MAX_CONTENT_LENGTH': 21 * 1024 * 1024,
        'DEBUG_LOGGING': os.environ.get('DEBUG_LOGGING', 'false').lower() == 'true',
        'OPENAI_HTTP_CLIENT_LEVEL': os.environ.get('OPENAI_HTTP_CLIENT_LEVEL', 'ERROR').upper(),
        'OPENAI_API_LEVEL': os.environ.get('OPENAI_API_LEVEL', 'ERROR').upper(),
    }
