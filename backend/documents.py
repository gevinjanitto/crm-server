import asyncio, logging
from pathlib import Path
from fastapi import HTTPException
from core import db, uid, now, log_activity
from storage import put_object
from pydantic import HttpUrl, TypeAdapter, ValidationError
from urllib.parse import urlsplit

DOC_TYPES = ['Kontrak','Requirement','Rincian Fitur','Timeline','UI/UX Design','Penawaran Harga','Invoice','Akses Server','BAST','Dokumentasi Penggunaan','Lampiran Project','Lampiran Task']
ALLOWED_EXT = ['.pdf','.docx','.xlsx','.txt','.csv','.png','.jpg','.jpeg','.webp']

async def store_document(pid, u, file, kind, visibility='Internal', task_id=None, name='', url=''):
    if kind not in DOC_TYPES or visibility not in ['Internal','Client']: raise HTTPException(400,'Kategori atau visibilitas tidak valid.')
    if kind=='Akses Server' and visibility=='Client': raise HTTPException(400,'Dokumen akses server wajib internal.')
    name, url = name.strip(), url.strip()
    if len(name) > 200: raise HTTPException(400, 'Nama dokumen maksimal 200 karakter.')
    if bool(file) == bool(url): raise HTTPException(400, 'Pilih tepat satu: file atau link dokumen.')
    if url:
        if not name: raise HTTPException(400, 'Nama dokumen wajib diisi.')
        try:
            url = str(TypeAdapter(HttpUrl).validate_python(url))
            if urlsplit(url).username or urlsplit(url).password: raise ValueError()
        except (ValidationError, ValueError): raise HTTPException(400, 'Link harus berupa URL HTTP/HTTPS tanpa kredensial.')
        doc = {'id': uid(), 'project_id': pid, 'name': name, 'url': url, 'document_type': 'link', 'kind': kind, 'visibility': visibility, 'size': 0, 'created_at': now(), 'uploaded_by': u['name'], 'is_deleted': False}
        if task_id: doc['task_id'] = task_id
        await db.project_documents.insert_one(doc.copy())
        await log_activity(u, 'tambah link', 'dokumen', doc['id'], name, pid, {'kategori': kind})
        return doc
    ext=Path(file.filename or '').suffix.lower()
    if ext not in ALLOWED_EXT: raise HTTPException(400,'Format tidak didukung. Gunakan PDF, DOCX, XLSX, TXT, CSV, atau gambar.')
    data=await file.read(10*1024*1024+1)
    if not data or len(data)>10*1024*1024: raise HTTPException(400,'File harus berukuran 1 byte hingga 10 MB.')
    doc_id=uid()
    try: result=await asyncio.to_thread(put_object,f'crm-maiharta/uploads/{u["id"]}/{doc_id}{ext}',data,file.content_type or 'application/octet-stream')
    except Exception as e:
        logging.getLogger(__name__).warning('Cloudinary upload gagal: %s', e)
        raise HTTPException(503,'Penyimpanan dokumen (Cloudinary) belum dapat dihubungi. Periksa konfigurasi CLOUDINARY_* di server.')
    doc={'id':doc_id,'project_id':pid,'name':Path(file.filename).name,'kind':kind,'visibility':visibility,'size':len(data),'storage_path':result['path'],'content_type':file.content_type or 'application/octet-stream','created_at':now(),'uploaded_by':u['name'],'is_deleted':False}
    doc.update(name=name or doc['name'], filename=Path(file.filename).name, document_type='file')
    if task_id: doc['task_id']=task_id
    await db.project_documents.insert_one(doc.copy())
    await log_activity(u, 'unggah', 'dokumen', doc_id, doc['name'], pid, {'kategori': kind})
    doc.pop('storage_path')
    return doc
