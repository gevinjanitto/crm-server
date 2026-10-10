import asyncio, re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Response
from core import db,uid,now,authorize,project_scope,project_for,validate_assignee,log_activity,sync_task_members,TICKET_STATUSES,MANAGERS
from auth import current_user
from schemas import Record,TicketInput,TicketUpdate,CommentInput,TicketSummary
from kanban import create_task,sync_task_status
from notify import notify,notify_assignment,manager_ids,client_ids
from storage import put_object,get_object
router=APIRouter()
ATTACH_EXT=['.jpg','.jpeg','.png','.gif','.pdf','.zip','.csv','.txt','.log','.tar','.gz']
ATTACH_MAX=5*1024*1024
ATTACH_LIMIT=5
SAFE_TAGS={'b','strong','i','em','u','code','pre','a','ul','ol','li','blockquote','p','br','div','span'}

class _Sanitizer(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=False); self.out=[]
    def handle_starttag(self,tag,attrs):
        if tag not in SAFE_TAGS: return
        if tag=='a':
            href=dict(attrs).get('href','') or ''
            if not re.match(r'^(https?://|mailto:)',href): href='#'
            self.out.append(f'<a href="{href}" target="_blank" rel="noopener noreferrer">'); return
        self.out.append(f'<{tag}>')
    def handle_endtag(self,tag):
        if tag in SAFE_TAGS and tag!='br': self.out.append(f'</{tag}>')
    def handle_startendtag(self,tag,attrs):
        if tag=='br': self.out.append('<br>')
    def handle_data(self,d): self.out.append(d.replace('<','&lt;').replace('>','&gt;'))
    def handle_entityref(self,n): self.out.append(f'&{n};')
    def handle_charref(self,n): self.out.append(f'&#{n};')
def sanitize_html(s):
    p=_Sanitizer(); p.feed(s or ''); p.close(); return ''.join(p.out)
def strip_html(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',(s or '').replace('<br>','\n').replace('</p>','\n').replace('</li>','\n'))).strip()

async def visible_tickets(u):
    ids=await db.projects.distinct('id',project_scope(u))
    q={'project_id':{'$in':ids}}
    if u['role']=='Developer': q['assigned_to']=u['id']
    return q
async def ticket_for(u,tid,action):
    t=await db.tickets.find_one({'$and':[await visible_tickets(u),{'id':tid}]},{'_id':0})
    if not t: raise HTTPException(404,'Tiket tidak ditemukan.')
    await authorize(u,action,t)
    return t
def ticket_public(t,u):
    if u['role']=='Developer': t={k:v for k,v in t.items() if k!='estimate'}
    return t
async def ticket_audience(t,p):
    return [t.get('created_by',''),t.get('assigned_to','')]+await manager_ids()+await client_ids(p.get('client_id'))

@router.get('/tickets',response_model=list[Record])
async def tickets(u=Depends(current_user)):
    await authorize(u,'ticket.read')
    rows=await db.tickets.find(await visible_tickets(u),{'_id':0}).sort('created_at',-1).to_list(2000)
    return [ticket_public(r,u) for r in rows]

async def project_ticket_query(u, pid):
    # Retain the same role, project ownership and developer assignment rules
    # as the global ticket list, including on the badge/count endpoint.
    await project_for(u, pid)
    await authorize(u, 'ticket.read')
    return {'$and': [await visible_tickets(u), {'project_id': pid}]}

@router.get('/projects/{pid}/tickets', response_model=list[Record])
async def project_tickets(pid: str, u=Depends(current_user)):
    query = await project_ticket_query(u, pid)
    rows = await db.tickets.find(query, {'_id': 0}).sort('created_at', -1).to_list(2000)
    return [ticket_public(row, u) for row in rows]

@router.get('/projects/{pid}/tickets/summary', response_model=TicketSummary)
async def project_ticket_summary(pid: str, u=Depends(current_user)):
    query = await project_ticket_query(u, pid)
    total, new, active = await asyncio.gather(
        db.tickets.count_documents(query),
        db.tickets.count_documents({'$and': [query, {'status': 'Baru'}]}),
        db.tickets.count_documents({'$and': [query, {'status': {'$nin': ['Selesai', 'Ditutup', 'Ditolak']}}]}),
    )
    return {'total': total, 'new': new, 'active': active}

@router.post('/tickets',response_model=Record)
async def create_ticket(data:TicketInput,u=Depends(current_user)):
    await authorize(u,'ticket.create')
    p=await project_for(u,data.project_id)
    if p.get('tickets_closed'): raise HTTPException(400,'Penerimaan tiket untuk project ini sudah ditutup.')
    body=data.model_dump()
    body['description_html']=sanitize_html(body.get('description_html') or '')
    if body['description_html'] and len(strip_html(body['description_html']))>=5: body['description']=strip_html(body['description_html'])[:5000]
    t={**body,'id':uid(),'code':'TKT-'+uid()[:6].upper(),'project_name':p['name'],'status':'Baru','assigned_to':'','estimate':0,'triaged':False,'approved':False,'attachments':[],'created_by':u['id'],'created_by_name':u['name'],'created_at':now(),'updated_at':now()}
    task=await create_task(t['project_id'],u,title=f"[{t['code']}] {t['title']}",description=t['description'],priority=t['priority'],source='ticket',source_id=t['id'],tags=['Tiket',t['category']])
    t['task_id']=task['id']
    await db.tickets.insert_one(t.copy())
    await log_activity(u,'buat','tiket',t['id'],t['title'],t['project_id'])
    audience=await manager_ids() if u['role']=='Client' else await manager_ids()+await client_ids(p.get('client_id'))
    await notify(audience,f"Tiket baru {t['code']}: {t['title']}",f"{u['name']} membuka tiket {t['priority'].lower()} pada project {p['name']}.",'tiket','/tickets',p['id'],'tiket',t['id'],u,cc=t.get('cc_emails'))
    return t
@router.get('/tickets/{tid}',response_model=Record)
async def get_ticket(tid:str,u=Depends(current_user)): return ticket_public(await ticket_for(u,tid,'ticket.read'),u)

@router.post('/tickets/{tid}/attachments',response_model=Record)
async def upload_attachments(tid:str,files:list[UploadFile]=File(...),u=Depends(current_user)):
    t=await ticket_for(u,tid,'ticket.read')
    if u['role']=='Developer': raise HTTPException(403,'Developer tidak dapat menambah lampiran tiket.')
    existing=t.get('attachments') or []
    if len(existing)+len(files)>ATTACH_LIMIT: raise HTTPException(400,f'Maksimal {ATTACH_LIMIT} berkas per tiket.')
    added=[]
    for f in files:
        ext=Path(f.filename or '').suffix.lower()
        if ext not in ATTACH_EXT: raise HTTPException(400,f"Format {ext or 'berkas'} tidak didukung.")
        data=await f.read(ATTACH_MAX+1)
        if not data or len(data)>ATTACH_MAX: raise HTTPException(400,'Setiap berkas maksimal 5 MB.')
        aid=uid()
        try: stored=await asyncio.to_thread(put_object,f"crm-maiharta/tickets/{tid}/{aid}{ext}",data,f.content_type or 'application/octet-stream')
        except Exception: raise HTTPException(503,'Penyimpanan berkas belum dapat dihubungi.')
        added.append({'id':aid,'name':Path(f.filename).name,'size':len(data),'content_type':f.content_type or 'application/octet-stream','storage_path':stored['path'],'uploaded_by':u['name'],'created_at':now()})
    await db.tickets.update_one({'id':tid},{'$set':{'attachments':existing+added,'updated_at':now()}})
    await log_activity(u,'unggah','tiket',tid,t['title'],t['project_id'],{'lampiran':[a['name'] for a in added]})
    return {**t,'attachments':[{k:v for k,v in a.items() if k!='storage_path'} for a in existing+added]}

@router.get('/tickets/{tid}/attachments/{aid}/download')
async def download_attachment(tid:str,aid:str,u=Depends(current_user)):
    t=await ticket_for(u,tid,'ticket.read')
    a=next((x for x in t.get('attachments') or [] if x['id']==aid),None)
    if not a: raise HTTPException(404,'Lampiran tidak ditemukan.')
    try: content=await asyncio.to_thread(get_object,a['storage_path'])
    except Exception: raise HTTPException(503,'Lampiran belum dapat diunduh.')
    return Response(content,media_type=a['content_type'],headers={'Content-Disposition':f"attachment; filename*=UTF-8''{quote(a['name'])}",'X-Content-Type-Options':'nosniff'})

@router.patch('/tickets/{tid}',response_model=Record)
async def update_ticket(tid:str,data:TicketUpdate,u=Depends(current_user)):
    t=await ticket_for(u,tid,'ticket.progress')
    if data.status not in TICKET_STATUSES: raise HTTPException(400,'Status tiket tidak valid.')
    update=data.model_dump(exclude_none=True)
    if u['role']=='Client':
        if set(update)-{'status'} or t['status']!='Menunggu Persetujuan' or data.status not in ['Diterima','Ditolak']: raise HTTPException(403,'Client hanya dapat menyetujui atau menolak estimasi tiket.')
        update['approved']=data.status=='Diterima'
    elif u['role']=='Developer':
        if set(update)-{'status'} or not t.get('triaged') or (t['status'],data.status) not in [('Diterima','Dikerjakan'),('Dikerjakan','Selesai')]: raise HTTPException(403,'Tiket harus ditriase dan diterima sebelum dikerjakan.')
    else:
        await authorize(u,'ticket.triage',t)
        transitions={'Baru':['Ditinjau','Ditolak'],'Ditinjau':['Menunggu Klarifikasi','Diterima','Ditolak','Menunggu Estimasi Biaya'],'Menunggu Klarifikasi':['Ditinjau','Ditolak'],'Menunggu Estimasi Biaya':['Menunggu Persetujuan','Ditolak'],'Menunggu Persetujuan':['Diterima','Ditolak'],'Diterima':['Dikerjakan'],'Dikerjakan':['Selesai'],'Selesai':['Ditutup'],'Ditolak':['Ditutup'],'Ditutup':[]}
        if data.status!=t['status'] and data.status not in transitions[t['status']]: raise HTTPException(400,'Status tiket harus mengikuti alur triase.')
        update['triaged']=True
        if data.assigned_to:
            p=await project_for(u,t['project_id'])
            await validate_assignee(data.assigned_to,p)
        if t['status']=='Menunggu Persetujuan' and data.status=='Diterima': update['approved']=True
    category=update.get('category',t['category'])
    if t.get('approved') and category!=t['category']: update['approved']=False
    if category in ['Change Request','Out of Scope'] and data.status in ['Diterima','Dikerjakan','Selesai','Menunggu Persetujuan']:
        if update.get('estimate',t.get('estimate',0))<=0: raise HTTPException(400,'Change request dan out of scope wajib memiliki estimasi biaya.')
        if data.status in ['Diterima','Dikerjakan','Selesai'] and not update.get('approved',t.get('approved')): raise HTTPException(400,'Estimasi harus disetujui sebelum pekerjaan dimulai.')
    if data.status=='Dikerjakan' and not update.get('assigned_to',t.get('assigned_to')): raise HTTPException(400,'Tentukan PIC sebelum pekerjaan dimulai.')
    update['updated_at']=now()
    assignee=update.get('assigned_to',t.get('assigned_to',''))
    new_assignee=bool(assignee) and assignee!=t.get('assigned_to','')
    if data.status=='Diterima' and not t.get('task_id'):
        task=await create_task(t['project_id'],u,title=f"[{t['code']}] {t['title']}",description=t['description'],assigned_to=assignee,priority=t['priority'],source='ticket',source_id=tid)
        update['task_id']=task['id']
    elif 'assigned_to' in update and assignee != t.get('assigned_to', ''):
        await db.tasks.update_many({'source':'ticket','source_id':tid},{'$set':{'assigned_to':assignee,'assignee_ids':[assignee] if assignee else [],'updated_at':now()}})
        await sync_task_members(t['project_id'])
        if assignee: await notify_assignment(assignee,'tiket',t['title'],t['project_id'],actor=u)
    if data.status in ['Dikerjakan','Selesai'] and data.status!=t['status']: await sync_task_status('ticket',tid,data.status)
    if data.status=='Ditutup' and data.status!=t['status']: await sync_task_status('ticket',tid,'Selesai')
    if data.status=='Ditolak' and data.status!=t['status']: await db.tasks.delete_many({'source':'ticket','source_id':tid})
    await db.tickets.update_one({'id':tid},{'$set':update})
    await log_activity(u,'ubah status','tiket',tid,t['title'],t['project_id'],{'dari':t['status'],'ke':data.status})
    await db.ticket_comments.insert_one({'id':uid(),'ticket_id':tid,'message':f"Status diperbarui: {data.status}",'internal':False,'author_name':u['name'],'author_role':u['role'],'created_at':now(),'system':True})
    p=await db.projects.find_one({'id':t['project_id']},{'_id':0,'client_id':1,'name':1}) or {}
    changes=[]
    if data.status!=t['status']: changes.append(f"status {t['status']} → {data.status}")
    if new_assignee: changes.append('PIC ditetapkan')
    if update.get('estimate') and update['estimate']!=t.get('estimate'): changes.append(f"estimasi biaya Rp {update['estimate']:,.0f}")
    if changes: await notify(await ticket_audience({**t,**update},p),f"Tiket {t['code']} diperbarui: {data.status}",f"{u['name']} memperbarui tiket \"{t['title']}\" ({', '.join(changes)}).",'tiket','/tickets',t['project_id'],'tiket',tid,u,cc=t.get('cc_emails'))
    return ticket_public({**t,**update},u)

@router.get('/tickets/{tid}/comments',response_model=list[Record])
async def comments(tid:str,u=Depends(current_user)):
    await ticket_for(u,tid,'ticket.read')
    q={'ticket_id':tid}
    if u['role']=='Client': q['internal']=False
    return await db.ticket_comments.find(q,{'_id':0}).sort('created_at',1).to_list(1000)
@router.post('/tickets/{tid}/comments',response_model=Record)
async def add_comment(tid:str,data:CommentInput,u=Depends(current_user)):
    t=await ticket_for(u,tid,'ticket.read')
    if data.internal and u['role']=='Client': raise HTTPException(403,'Client tidak dapat membuat catatan internal.')
    c={**data.model_dump(),'id':uid(),'ticket_id':tid,'author_name':u['name'],'author_role':u['role'],'created_at':now(),'system':False}
    await db.ticket_comments.insert_one(c.copy())
    p=await db.projects.find_one({'id':t['project_id']},{'_id':0,'client_id':1}) or {}
    audience=[t.get('assigned_to','')]+await manager_ids() if data.internal else await ticket_audience(t,p)
    await notify(audience,f"Pesan baru di tiket {t['code']}",f"{u['name']}: {data.message[:160]}{'…' if len(data.message)>160 else ''}",'tiket','/tickets',t['project_id'],'tiket',tid,u,cc=None if data.internal else t.get('cc_emails'))
    return c
