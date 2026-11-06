import os
import logging
from pathlib import Path
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.utils

LOCAL_DIR = Path(os.environ.get('UPLOAD_DIR') or Path(__file__).parent / 'uploads')

def _configured():
    return all(os.environ.get(k) for k in ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET'])

def _configure():
    cloudinary.config(cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'], api_key=os.environ['CLOUDINARY_API_KEY'], api_secret=os.environ['CLOUDINARY_API_SECRET'], secure=True)

def put_object(path, data, content_type):
    if not _configured():
        logging.getLogger(__name__).info('Menyimpan file di disk server: %s', LOCAL_DIR)
        target = LOCAL_DIR / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {'path': 'local:' + path, 'url': ''}
    _configure()
    r = cloudinary.uploader.upload(data, public_id=path, resource_type='raw', type='authenticated', overwrite=False, use_filename=False, unique_filename=False)
    return {'path': r['public_id'], 'url': r['secure_url']}

def get_object(path):
    if path.startswith('local:'): return (LOCAL_DIR / path[6:]).read_bytes()
    _configure()
    url, _ = cloudinary.utils.cloudinary_url(path, resource_type='raw', type='authenticated', sign_url=True)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def delete_object(path):
    if path.startswith('local:'):
        (LOCAL_DIR / path[6:]).unlink(missing_ok=True); return
    _configure()
    cloudinary.uploader.destroy(path, resource_type='raw', type='authenticated', invalidate=True)
