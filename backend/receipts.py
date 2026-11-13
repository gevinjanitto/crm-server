import asyncio, re
from datetime import date as Date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from core import db, uid, now, project_for, log_event
from auth import current_user
from receipt_doc import render_docx, render_pdf, terbilang_rupiah, MAX_ITEMS, layout, doc_images
from doc_files import ASSETS, drop, load, save_image, image_response, lenient, preview_dims

router = APIRouter()

class ReceiptItem(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    qty: float = Field(gt=0, le=100000)
    price: float = Field(ge=0, le=1e13)

class ImageBox(BaseModel):
    dx: float = Field(0, ge=-30, le=30)
    dy: float = Field(0, ge=-30, le=30)
    dw: float = Field(0, ge=-30, le=30)
    dh: float = Field(0, ge=-30, le=30)

class ReceiptInput(BaseModel):
    number: str = Field('', max_length=60)
    date: Date
    received_from: str = Field(min_length=1, max_length=200)
    items: list[ReceiptItem] = Field(min_length=1, max_length=MAX_ITEMS)
    ppn_enabled: bool = True
    ppn_rate: float = Field(11, ge=0, le=50)
    pph_enabled: bool = True
    pph_rate: float = Field(2, ge=0, lt=50)
    company_name: str = Field('CV MAI HARTA', min_length=1, max_length=100)
    signer_name: str = Field('Ida Bagus Gede Brahmantara', min_length=1, max_length=100)
    signer_title: str = Field('Direktur', max_length=100)
    show_signature: bool = False
    logo_scale: float = Field(100, ge=30, le=250)
    client_logo_scale: float = Field(100, ge=30, le=250)
    sign_scale: float = Field(100, ge=30, le=250)
    image_boxes: dict[str, ImageBox] = Field(default_factory=dict)
    remove_logo: Optional[bool] = False
    remove_signature: Optional[bool] = False

def _round(x): return int(x + 0.5)
def _pct(r): return f'{r:g}%'

def compute(data):
    sub = sum(_round(i['qty'] * i['price']) for i in data['items'])
    ppn = _round(sub * data['ppn_rate'] / 100) if data['ppn_enabled'] else 0
    pph = _round(sub * data['pph_rate'] / (100 - data['pph_rate'])) if data['pph_enabled'] else 0
    total = sub + ppn + pph
    return {'subtotal': sub, 'ppn': ppn, 'pph': pph, 'total': total, 'terbilang': terbilang_rupiah(total)}

async def next_number(d, coll='receipts'):
    rows = await db[coll].find({'year': d.year}, {'_id': 0, 'seq': 1}).to_list(100000)
    seq = max([r.get('seq') or 0 for r in rows] + [0]) + 1
    return seq, f'{seq:03d}/INV/MH/{d.month:02d}/{d.year}'

def tax_rows(r):
    taxes = []
    if r['ppn_enabled']: taxes.append((f"PPN {_pct(r['ppn_rate'])}", r['ppn']))
    if r['pph_enabled']: taxes.append((f"PPH 23 {_pct(r['pph_rate'])}", r['pph']))
    return taxes

def doc_data(r):
    d = Date.fromisoformat(r['date'])
    return {**r, 'tax_rows': tax_rows(r), 'date_label': d.strftime('%d/%m/%Y')}

async def receipt_for(u, pid, rid, action):
    await project_for(u, pid, action)
    r = await db.receipts.find_one({'id': rid, 'project_id': pid}, {'_id': 0})
    if not r: raise HTTPException(404, 'Kwitansi tidak ditemukan.')
    return r

async def assign_number(row, d, current, coll, label):
    number = row['number'].strip()
    if not number:
        if current and current.get('number'): number = current['number']
        else: row['seq'], number = await next_number(d, coll)
    else:
        m = re.match(r'^(\d+)/', number)
        row['seq'] = int(m.group(1)) if m else (current or {}).get('seq', 0)
    dup = await db[coll].find_one({'number': number}, {'_id': 0, 'id': 1})
    if dup and (not current or dup['id'] != current['id']): raise HTTPException(409, f'Nomor {label} sudah dipakai.')
    row.update(number=number, year=d.year, **compute(row))
    return row

async def prepare(data, current=None):
    row = data.model_dump(mode='json', exclude={'remove_logo', 'remove_signature'})
    row['received_from'] = row['received_from'].strip()
    if not row['received_from']: raise HTTPException(400, 'Nama "Diterima dari" wajib diisi.')
    return await assign_number(row, data.date, current, 'receipts', 'kwitansi')

async def remove_images(coll, r, update, data):
    for flag, field in (('remove_logo', 'logo_path'), ('remove_signature', 'sign_path')):
        if getattr(data, flag) and r.get(field):
            await drop(r[field]); update[field] = ''

@router.get('/doc-assets/{name}')
async def doc_asset(name: str, u=Depends(current_user)):
    if name not in ASSETS: raise HTTPException(404, 'Aset tidak ditemukan.')
    return Response(ASSETS[name].read_bytes(), media_type='image/png')

@router.get('/projects/{pid}/receipts')
async def list_receipts(pid: str, u=Depends(current_user)):
    await project_for(u, pid, 'billing.read')
    return await db.receipts.find({'project_id': pid}, {'_id': 0}).sort('created_at', -1).to_list(500)

def receipt_defaults_base():
    return {'ppn_enabled': True, 'ppn_rate': 11, 'pph_enabled': True, 'pph_rate': 2, 'company_name': 'CV MAI HARTA',
            'signer_name': 'Ida Bagus Gede Brahmantara', 'signer_title': 'Direktur', 'show_signature': False,
            'logo_scale': 100, 'client_logo_scale': 100, 'sign_scale': 100, 'image_boxes': {}}

@router.get('/projects/{pid}/receipts/new')
async def receipt_defaults(pid: str, u=Depends(current_user)):
    p = await project_for(u, pid, 'billing.read')
    today = Date.today()
    _, number = await next_number(today)
    c = await db.clients.find_one({'id': p.get('client_id')}, {'_id': 0}) if p.get('client_id') else None
    return {'number': number, 'date': today.isoformat(), 'received_from': (c or {}).get('company') or (c or {}).get('name') or p.get('client_name') or '',
            'items': [{'description': f"Biaya Pengembangan Aplikasi {p.get('name', '')}".strip(), 'qty': 1, 'price': p.get('value') or 0}],
            **receipt_defaults_base()}

@router.post('/projects/{pid}/receipts/preview')
async def preview_receipt(pid: str, body: dict, u=Depends(current_user)):
    await project_for(u, pid, 'billing.read')
    r = lenient(body, {'number': '', 'date': '', 'received_from': '', **receipt_defaults_base()})
    r.update(compute(r))
    return {'elements': layout(doc_data(r), preview_dims(body, bool(body.get('has_logo'))))}

@router.post('/projects/{pid}/receipts')
async def create_receipt(pid: str, data: ReceiptInput, u=Depends(current_user)):
    await project_for(u, pid, 'billing.write')
    row = {**await prepare(data), 'id': uid(), 'project_id': pid, 'logo_path': '', 'sign_path': '', 'created_by': u['name'], 'created_at': now()}
    await db.receipts.insert_one(row.copy())
    await log_event(pid, u, f"Kwitansi dibuat: {row['number']}")
    return row

@router.patch('/projects/{pid}/receipts/{rid}')
async def update_receipt(pid: str, rid: str, data: ReceiptInput, u=Depends(current_user)):
    r = await receipt_for(u, pid, rid, 'billing.write')
    update = {**await prepare(data, r), 'updated_at': now(), 'updated_by': u['name']}
    await remove_images('receipts', r, update, data)
    await db.receipts.update_one({'id': rid}, {'$set': update})
    return {**r, **update}

@router.delete('/projects/{pid}/receipts/{rid}')
async def delete_receipt(pid: str, rid: str, u=Depends(current_user)):
    r = await receipt_for(u, pid, rid, 'billing.write')
    await drop(r.get('logo_path')); await drop(r.get('sign_path'))
    await db.receipts.delete_one({'id': rid})
    await log_event(pid, u, f"Kwitansi dihapus: {r['number']}")
    return {'message': 'Kwitansi dihapus.'}

@router.post('/projects/{pid}/receipts/{rid}/logo')
async def upload_logo(pid: str, rid: str, file: UploadFile = File(...), u=Depends(current_user)):
    r = await receipt_for(u, pid, rid, 'billing.write')
    return await save_image('receipts', r, 'logo_path', file, 'receipts', 'Logo')

@router.post('/projects/{pid}/receipts/{rid}/signature')
async def upload_signature(pid: str, rid: str, file: UploadFile = File(...), u=Depends(current_user)):
    r = await receipt_for(u, pid, rid, 'billing.write')
    return await save_image('receipts', r, 'sign_path', file, 'receipts/ttd', 'TTD')

@router.get('/projects/{pid}/receipts/{rid}/logo')
async def get_logo(pid: str, rid: str, u=Depends(current_user)):
    return await image_response((await receipt_for(u, pid, rid, 'billing.read')).get('logo_path'), 'Logo belum diunggah.')

@router.get('/projects/{pid}/receipts/{rid}/signature')
async def get_signature(pid: str, rid: str, u=Depends(current_user)):
    return await image_response((await receipt_for(u, pid, rid, 'billing.read')).get('sign_path'), 'TTD belum diunggah.')

async def stored_images(r):
    return doc_images(await load(r.get('logo_path')), await load(r.get('sign_path')), r.get('show_signature'))

@router.get('/projects/{pid}/receipts/{rid}/{fmt}')
async def download_receipt(pid: str, rid: str, fmt: str, u=Depends(current_user)):
    if fmt not in ('docx', 'pdf'): raise HTTPException(404, 'Format tidak dikenal.')
    r = await receipt_for(u, pid, rid, 'billing.read')
    images = await stored_images(r)
    data = await asyncio.to_thread(render_docx if fmt == 'docx' else render_pdf, doc_data(r), images)
    media = 'application/pdf' if fmt == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    name = 'Kwitansi-' + re.sub(r'[^A-Za-z0-9_-]+', '-', r['number']).strip('-') + f'.{fmt}'
    return Response(data, media_type=media, headers={'Content-Disposition': f'attachment; filename="{name}"'})
