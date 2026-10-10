"""Configuration checks return reasons only, never secret values."""
import os
from urllib.parse import urlparse


def enabled(key):
    return os.environ.get(key, '').strip().lower() == 'true'


def https_url(value):
    try:
        parsed = urlparse(value)
        return bool(parsed.scheme == 'https' and parsed.hostname and not parsed.username
                    and not parsed.password and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def app_url():
    value = os.environ.get('APP_URL', '').strip().rstrip('/')
    if not https_url(value):
        raise ValueError('APP_URL harus berupa URL HTTPS frontend yang valid.')
    return value


def missing(keys):
    return [key for key in keys if not os.environ.get(key, '').strip()]