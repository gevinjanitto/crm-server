import asyncio, re
from datetime import date as Date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from core import db, uid, now, project_for, log_event, authorize
from auth import current_user
from receipt_doc import MAX_ITEMS, doc_images
from invoice_doc import render_docx, render_pdf, layout
from receipts import ReceiptItem, ImageBox, compute, next_number, doc_data, assign_number, remove_images, receipt_defaults_base
from doc_files import drop, load, save_image, image_response, lenient, preview_dims

router = APIRouter()

class BankAccountInput(BaseModel):
    bank_name: str = Field(min_length=1, max_length=100)
    branch: str = Field('', max_length=100)
    account_number: str = Field(min_length=1, max_length=60)
    account_holder: str = Field(min_length=1, max_length=100)

class InvoiceInput(BaseModel):
    number: str = Field('', max_length=60)
    date: Date
    to_name: str = Field(min_length=1, max_length=200)
    to_title: str = Field('', max_length=200)
    to_address: str = Field('', max_length=400)
    items: list[ReceiptItem] = Field(min_length=1, max_length=MAX_ITEMS)
    ppn_enabled: bool = True
    ppn_rate: float = Field(11, ge=0, le=50)
    pph_enabled: bool = True
    pph_rate: float = Field(2, ge=0, lt=50)
    bank_account_id: str = Field('', max_length=60)
    bank_name: str = Field('', max_length=100)
    bank_branch: str = Field('', max_length=100)
    account_number: str = Field('', max_length=60)
    account_holder: str = Field('', max_length=100)
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

# ---------- Master rekening ----------
@router.get('/bank-accounts')
async def list_bank_accounts(u=Depends(current_user)):
    await authorize(u, 'billing.read')
    return await db.bank_accounts.find({}, {'_id': 0}).sort('created_at', 1).to_list(500)

@router.post('/bank-accounts')
async def create_bank_account(data: BankAccountInput, u=Depends(current_user)):
    await authorize(u, 'billing.write')
    row = {**data.model_dump(), 'id': uid(), 'created_by': u['name'], 'created_at': now()}
    await db.bank_accounts.insert_one(row.copy())
    return row

@router.patch('/bank-accounts/{bid}')
async def update_bank_account(bid: str, data: BankAccountInput, u=Depends(current_user)):
    await authorize(u, 'billing.write')
    b = await db.bank_accounts.find_one({'id': bid}, {'_id': 0})
    if not b: raise HTTPException(404, 'Rekening tidak ditemukan.')
    await db.bank_accounts.update_one({'id': bid}, {'$set': {**data.model_dump(), 'updated_at': now()}})
    return {**b, **data.model_dump()}

@router.delete('/bank-accounts/{bid}')
async def delete_bank_account(bid: str, u=Depends(current_user)):
    await authorize(u, 'billing.write')
    res = await db.bank_accounts.delete_one({'id': bid})
    if not res.deleted_count: raise HTTPException(404, 'Rekening tidak ditemukan.')
    return {'message': 'Rekening dihapus.'}

# ---------- Invoice ----------
async def invoice_for(u, pid, iid, action):
    await project_for(u, pid, action)
    r = await db.invoices.find_one({'id': iid, 'project_id': pid}, {'_id': 0})
    if not r: raise HTTPException(404, 'Invoice tidak ditemukan.')
    return r

async def prepare(data, current=None):
    row = data.model_dump(mode='json', exclude={'remove_logo', 'remove_signature'})
    row['to_name'] = row['to_name'].strip()
    if not row['to_name']: raise HTTPException(400, 'Nama penerima (Kepada) wajib diisi.')
    return await assign_number(row, data.date, current, 'invoices', 'invoice')

def invoice_text_defaults():
    return {'number': '', 'date': '', 'to_name': '', 'to_title': '', 'to_address': '', 'bank_account_id': '', 'bank_name': '',
            'bank_branch': '', 'account_number': '', 'account_holder': '', **receipt_defaults_base()}

@router.get('/projects/{pid}/invoices')
async def list_invoices(pid: str, u=Depends(current_user)):
    await project_for(u, pid, 'billing.read')
    return await db.invoices.find({'project_id': pid}, {'_id': 0}).sort('created_at', -1).to_list(500)

@router.get('/projects/{pid}/invoices/new')
async def invoice_defaults(pid: str, u=Depends(current_user)):
    p = await project_for(u, pid, 'billing.read')
    today = Date.today()
    _, number = await next_number(today, 'invoices')
    c = await db.clients.find_one({'id': p.get('client_id')}, {'_id': 0}) if p.get('client_id') else None
    bank = await db.bank_accounts.find_one({}, {'_id': 0})
    out = {**invoice_text_defaults(), 'number': number, 'date': today.isoformat(),
           'to_name': (c or {}).get('company') or (c or {}).get('name') or p.get('client_name') or '',
           'to_address': (c or {}).get('address') or '',
           'items': [{'description': f"Biaya Pengembangan Aplikasi {p.get('name', '')}".strip(), 'qty': 1, 'price': p.get('value') or 0}]}
    if bank: out.update(bank_account_id=bank['id'], bank_name=bank['bank_name'], bank_branch=bank.get('branch', ''),
                        account_number=bank['account_number'], account_holder=bank['account_holder'])
    return out

@router.post('/projects/{pid}/invoices/preview')
async def preview_invoice(pid: str, body: dict, u=Depends(current_user)):
    await project_for(u, pid, 'billing.read')
    r = lenient(body, invoice_text_defaults())
    r.update(compute(r))
    return {'elements': layout(doc_data(r), preview_dims(body, bool(body.get('has_logo'))))}

@router.post('/projects/{pid}/invoices')
async def create_invoice(pid: str, data: InvoiceInput, u=Depends(current_user)):
    await project_for(u, pid, 'billing.write')
    row = {**await prepare(data), 'id': uid(), 'project_id': pid, 'logo_path': '', 'sign_path': '', 'created_by': u['name'], 'created_at': now()}
    await db.invoices.insert_one(row.copy())
    await log_event(pid, u, f"Invoice dibuat: {row['number']}")
    return row

@router.patch('/projects/{pid}/invoices/{iid}')
async def update_invoice(pid: str, iid: str, data: InvoiceInput, u=Depends(current_user)):
    r = await invoice_for(u, pid, iid, 'billing.write')
    update = {**await prepare(data, r), 'updated_at': now(), 'updated_by': u['name']}
    await remove_images('invoices', r, update, data)
    await db.invoices.update_one({'id': iid}, {'$set': update})
    return {**r, **update}

@router.delete('/projects/{pid}/invoices/{iid}')
async def delete_invoice(pid: str, iid: str, u=Depends(current_user)):
    r = await invoice_for(u, pid, iid, 'billing.write')
    await drop(r.get('logo_path')); await drop(r.get('sign_path'))
    await db.invoices.delete_one({'id': iid})
    await log_event(pid, u, f"Invoice dihapus: {r['number']}")
    return {'message': 'Invoice dihapus.'}

@router.post('/projects/{pid}/invoices/{iid}/logo')
async def upload_invoice_logo(pid: str, iid: str, file: UploadFile = File(...), u=Depends(current_user)):
    r = await invoice_for(u, pid, iid, 'billing.write')
    return await save_image('invoices', r, 'logo_path', file, 'invoices', 'Logo')

@router.post('/projects/{pid}/invoices/{iid}/signature')
async def upload_invoice_signature(pid: str, iid: str, file: UploadFile = File(...), u=Depends(current_user)):
    r = await invoice_for(u, pid, iid, 'billing.write')
    return await save_image('invoices', r, 'sign_path', file, 'invoices/ttd', 'TTD')

@router.get('/projects/{pid}/invoices/{iid}/logo')
async def get_invoice_logo(pid: str, iid: str, u=Depends(current_user)):
    return await image_response((await invoice_for(u, pid, iid, 'billing.read')).get('logo_path'), 'Logo belum diunggah.')

@router.get('/projects/{pid}/invoices/{iid}/signature')
async def get_invoice_signature(pid: str, iid: str, u=Depends(current_user)):
    return await image_response((await invoice_for(u, pid, iid, 'billing.read')).get('sign_path'), 'TTD belum diunggah.')

@router.get('/projects/{pid}/invoices/{iid}/{fmt}')
async def download_invoice(pid: str, iid: str, fmt: str, u=Depends(current_user)):
    if fmt not in ('docx', 'pdf'): raise HTTPException(404, 'Format tidak dikenal.')
    r = await invoice_for(u, pid, iid, 'billing.read')
    images = doc_images(await load(r.get('logo_path')), await load(r.get('sign_path')), r.get('show_signature'))
    data = await asyncio.to_thread(render_docx if fmt == 'docx' else render_pdf, doc_data(r), images)
    media = 'application/pdf' if fmt == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    name = 'Invoice-' + re.sub(r'[^A-Za-z0-9_-]+', '-', r['number']).strip('-') + f'.{fmt}'
    return Response(data, media_type=media, headers={'Content-Disposition': f'attachment; filename="{name}"'})
