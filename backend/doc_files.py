import asyncio, io
from datetime import date as Date
from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image
from core import db, uid
from storage import put_object, get_object, delete_object
from receipt_doc import MAX_ITEMS, DEFAULT_SIGN, BRAND_LOGO

ASSETS = {'brand': BRAND_LOGO, 'ttd-default': DEFAULT_SIGN}

async def drop(path):
    if not path: return
    try: await asyncio.to_thread(delete_object, path)
    except Exception: pass

async def load(path):
    if not path: return None
    try: return await asyncio.to_thread(get_object, path)
    except Exception: return None

async def save_image(coll, doc, field, file: UploadFile, prefix, label):
    data = await file.read(3 * 1024 * 1024 + 1)
    if not data or len(data) > 3 * 1024 * 1024: raise HTTPException(400, f'{label} harus berukuran maksimal 3 MB.')
    try:
        img = Image.open(io.BytesIO(data)); img.load()
        buf = io.BytesIO(); img.convert('RGBA').save(buf, 'PNG'); data = buf.getvalue()
    except Exception: raise HTTPException(400, f'File {label.lower()} harus berupa gambar PNG, JPG, atau WEBP.')
    try: res = await asyncio.to_thread(put_object, f'crm-maiharta/{prefix}/{doc["id"]}-{uid()[:8]}.png', data, 'image/png')
    except Exception: raise HTTPException(503, f'Penyimpanan {label.lower()} belum dapat dihubungi.')
    await drop(doc.get(field))
    await db[coll].update_one({'id': doc['id']}, {'$set': {field: res['path']}})
    return {**doc, field: res['path']}

async def image_response(path, missing):
    data = await load(path)
    if not data: raise HTTPException(404, missing)
    return Response(data, media_type='image/png')

def _num(v, d=0.0):
    try: return float(v)
    except (TypeError, ValueError): return d

def lenient(body, defaults):
    r = {**defaults, **{k: v for k, v in (body or {}).items() if v is not None}}
    for k in ('ppn_rate', 'pph_rate'): r[k] = min(max(_num(r.get(k)), 0), 49)
    for k in ('logo_scale', 'client_logo_scale', 'sign_scale'): r[k] = _num(r.get(k), 100) or 100
    items = [{'description': str(i.get('description') or ''), 'qty': _num(i.get('qty')), 'price': _num(i.get('price'))}
             for i in (r.get('items') or []) if isinstance(i, dict)][:MAX_ITEMS]
    r['items'] = items or [{'description': '', 'qty': 1, 'price': 0}]
    try: Date.fromisoformat(str(r.get('date')))
    except ValueError: r['date'] = Date.today().isoformat()
    for k, v in defaults.items():
        if isinstance(v, str): r[k] = str(r.get(k) or '')
    return r

def preview_dims(body, has_client):
    def ratio(k):
        v = _num((body or {}).get(k), 1) or 1
        return (max(0.1, min(10, v)), 1)
    return {'brand': (1, 1), 'client': ratio('client_ratio') if has_client else None, 'sign': ratio('sign_ratio')}
