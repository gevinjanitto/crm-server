import asyncio
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from core import db, uid, now, authorize, project_scope, project_for, project_public, log_event, validate_assignee, recalc_progress, log_activity, trash_item, sync_task_members, MANAGERS, FINANCE, STATUSES, MAINTENANCE_STATUSES, WORK_STATUSES
from auth import current_user
from schemas import Record, ProjectInput, StatusInput, FeatureInput, ProgressInput, CostInput, WorkInput, WorkUpdate, DeployInput, TicketProjectOption
from storage import get_object
from documents import store_document, DOC_TYPES
REQUIRED_DEV_DOCS=['Penawaran Harga','Kontrak']
DEV_STATUSES=['Development','Uploaded to Dev Server','Testing','Revisi']
from kanban import create_task, sync_task_status
from notify import notify, manager_ids, client_ids, finance_ids, project_people
from ticket_maintenance import ticket_maintenance_rows
from task_rules import assignee_ids
from starlette.responses import RedirectResponse

router = APIRouter()

@router.get('/projects', response_model=list[Record])
async def projects(u=Depends(current_user)):
    await authorize(u,'project.list')
    rows = await db.projects.find(project_scope(u),{'_id':0}).sort('created_at',-1).to_list(2000)
    return [project_public(p,u) for p in rows]

@router.get('/ticket-projects', response_model=list[TicketProjectOption])
async def ticket_project_options(u=Depends(current_user)):
    # Only the minimal, owned, open-for-ticket projects needed by the Client form.
    await authorize(u, 'ticket.create')
    query = {'$and': [project_scope(u), {'tickets_closed': {'$ne': True}}]}
    return await db.projects.find(query, {'_id': 0, 'id': 1, 'code': 1, 'name': 1}).sort('name', 1).to_list(2000)

@router.post('/projects', response_model=Record)
async def create_project(data: ProjectInput,u=Depends(current_user)):
    await authorize(u,'project.write')
    c=await db.clients.find_one({'id':data.client_id},{'_id':0})
    if not c: raise HTTPException(400,'Client tidak ditemukan.')
    for dev in data.assigned_to: await validate_assignee(dev)
    number=await db.counters.find_one_and_update({'id':'project'},{'$inc':{'value':1}},upsert=True,return_document=True,projection={'_id':0})
    p={**data.model_dump(mode='json'),'id':uid(),'code':f"MH-{number['value']:03d}",'client_name':c['name'],'status':STATUSES[0],'progress':0,'development_cost':0,'server_cost':0,'created_at':now(),'updated_at':now(),'created_by':u['id'],'production_at':None,'tickets_closed':False}
    await db.projects.insert_one(p.copy())
    await log_event(p['id'],u,'Project dibuat',to_status=STATUSES[0])
    await log_activity(u,'buat','project',p['id'],p['name'],p['id'])
    link=f"/projects/{p['id']}"
    await notify(data.assigned_to,f"Anda ditambahkan ke project {p['name']}",f"{u['name']} menugaskan Anda sebagai developer pada project {p['code']} — {p['name']}.",'project',link,p['id'],'project',p['id'],u)
    await notify(await client_ids(c['id']),f"Project baru: {p['name']}",f"Tim MaiHarta membuka project {p['code']} untuk {c['name']}. Pantau progresnya di sini.",'project',link,p['id'],'project',p['id'],u)
    await notify(await manager_ids()+await finance_ids(),f"Project baru dibuat: {p['name']}",f"{u['name']} membuat project {p['code']} untuk client {c['name']}.",'project',link,p['id'],'project',p['id'],u,email=False)
    return project_public(p,u)

@router.get('/projects/{pid}',response_model=Record)
async def get_project(pid:str,u=Depends(current_user)):
    return project_public(await project_for(u,pid),u)

@router.patch('/projects/{pid}',response_model=Record)
async def edit_project(pid:str,data:ProjectInput,u=Depends(current_user)):
    old=await project_for(u,pid,'project.write')
    c=await db.clients.find_one({'id':data.client_id},{'_id':0})
    if not c: raise HTTPException(400,'Client tidak ditemukan.')
    for dev in data.assigned_to: await validate_assignee(dev)
    await db.projects.update_one({'id':pid},{'$set':{**data.model_dump(mode='json'),'client_name':c['name'],'updated_at':now()}})
    await sync_task_members(pid)
    await log_event(pid,u,'Informasi project diperbarui')
    await log_activity(u,'ubah','project',pid,data.name,pid)
    added=[d for d in data.assigned_to if d not in (old.get('assigned_to') or [])]
    removed=[d for d in (old.get('assigned_to') or []) if d not in data.assigned_to]
    await notify(added,f"Anda ditambahkan ke project {data.name}",f"{u['name']} menugaskan Anda sebagai developer pada project {old['code']} — {data.name}.",'project',f'/projects/{pid}',pid,'project',pid,u)
    await notify(removed,f"Anda dikeluarkan dari project {data.name}",f"{u['name']} menghapus penugasan Anda pada project {old['code']}.",'project','/projects',pid,'project',pid,u)
    return project_public(await project_for(u,pid),u)

@router.delete('/projects/{pid}')
async def delete_project(pid:str,u=Depends(current_user)):
    p=await project_for(u,pid,'project.write')
    if p['status']!='Project Masuk': raise HTTPException(400,'Hanya project baru yang dapat dihapus.')
    related=[]
    for collection in ['project_features','project_documents','project_status_logs','revisions','maintenances','deployments','tickets','tasks','expenses','task_comments']:
        docs=await db[collection].find({'project_id':pid},{'_id':0}).to_list(5000)
        related.append({'collection':collection,'docs':docs})
    await trash_item(u,'projects',p,'project',p['name'],related)
    return {'message':'Project dipindahkan ke arsip.'}

@router.post('/projects/{pid}/status',response_model=Record)
async def change_status(pid:str,data:StatusInput,u=Depends(current_user)):
    p=await project_for(u,pid,'project.status')
    if data.status not in STATUSES: raise HTTPException(400,'Status tidak valid.')
    # Status boleh dipilih langsung (maju/mundur), aturan role & dokumen tetap berlaku.
    if data.status==p['status']: raise HTTPException(400,'Project sudah berada di status ini.')
    if data.status in ['Uploaded to Production','Selesai'] and u['role']!='Admin': raise HTTPException(403,'Hanya Admin yang dapat menetapkan status final.')
    if u['role']=='Developer' and not (p['status'] in DEV_STATUSES and data.status in DEV_STATUSES[1:]): raise HTTPException(403,'Developer hanya dapat memperbarui status teknis.')
    if STATUSES.index(data.status)>=STATUSES.index('Development') and STATUSES.index(p['status'])<STATUSES.index('Development'):
        docs=await db.project_documents.distinct('kind',{'project_id':pid,'is_deleted':False})
        if not any(d in docs for d in REQUIRED_DEV_DOCS): raise HTTPException(400,'Lengkapi dokumen wajib: Penawaran/Kontrak')
    if data.status=='Uploaded to Production':
        active=await db.revisions.count_documents({'project_id':pid,'status':{'$ne':'Selesai'}})
        if active: raise HTTPException(400,'Selesaikan semua revisi sebelum production.')
    update={'status':data.status,'updated_at':now()}
    if data.status=='Uploaded to Production': update['production_at']=now()
    if data.status=='Selesai': update['progress']=100
    await db.projects.update_one({'id':pid},{'$set':update})
    await log_event(pid,u,f"{p['status']} → {data.status}",from_status=p['status'],to_status=data.status,note=data.note)
    await log_activity(u,'ubah status','project',pid,p['name'],pid,{'dari':p['status'],'ke':data.status})
    await notify(await project_people(p),f"Status project {p['name']}: {data.status}",f"{u['name']} memperbarui status project {p['code']} dari {p['status']} menjadi {data.status}."+(f" Catatan: {data.note}" if data.note else ''),'project',f'/projects/{pid}',pid,'project',pid,u)
    return project_public({**p,**update},u)

@router.get('/projects/{pid}/history',response_model=list[Record])
async def history(pid:str,u=Depends(current_user)):
    await project_for(u,pid,'history.read')
    rows=await db.project_status_logs.find({'project_id':pid},{'_id':0}).sort('created_at',-1).to_list(500)
    if u['role']=='Client':
        return [{k:r[k] for k in ['id','message','created_at','to_status'] if k in r} for r in rows if r.get('to_status')]
    return rows

@router.get('/projects/{pid}/features',response_model=list[Record])
async def features(pid:str,u=Depends(current_user)):
    await project_for(u,pid,'feature.read')
    projection={'_id':0}
    if u['role'] not in MANAGERS+['Accounting']: projection['price']=0
    return await db.project_features.find({'project_id':pid},projection).to_list(1000)

@router.post('/projects/{pid}/features',response_model=Record)
async def create_feature(pid:str,data:FeatureInput,u=Depends(current_user)):
    p=await project_for(u,pid,'feature.write')
    await validate_assignee(data.assigned_to,p)
    f={**data.model_dump(mode='json'),'id':uid(),'project_id':pid,'status':'Belum dimulai','created_at':now()}
    await db.project_features.insert_one(f.copy())
    task=await create_task(pid,u,title=data.name,description=f"Fitur {data.category}",assigned_to=data.assigned_to,due_date=f['due_date'],source='feature',source_id=f['id'],tags=[data.category])
    await db.project_features.update_one({'id':f['id']},{'$set':{'task_id':task['id']}})
    await recalc_progress(pid)
    await log_activity(u,'buat','fitur',f['id'],f['name'],pid)
    return {**f,'task_id':task['id']}

FEATURE_TO_TASK={'Belum dimulai':'Belum Mulai','Dikerjakan':'Dikerjakan','Selesai':'Selesai'}

@router.patch('/projects/{pid}/features/{fid}',response_model=Record)
async def update_feature(pid:str,fid:str,data:ProgressInput,u=Depends(current_user)):
    await project_for(u,pid,'feature.progress')
    f=await db.project_features.find_one({'id':fid,'project_id':pid},{'_id':0})
    if not f: raise HTTPException(404,'Fitur tidak ditemukan.')
    if u['role']=='Developer' and f.get('assigned_to') not in ['',u['id']]: raise HTTPException(403,'Fitur ditugaskan kepada developer lain.')
    await db.project_features.update_one({'id':fid,'project_id':pid},{'$set':{'status':data.status}})
    await sync_task_status('feature',fid,FEATURE_TO_TASK[data.status])
    await recalc_progress(pid)
    await log_activity(u,'ubah status','fitur',fid,f['name'],pid,{'dari':f['status'],'ke':data.status})
    p=await db.projects.find_one({'id':pid},{'_id':0,'name':1})
    await notify(await manager_ids() if u['role']=='Developer' else [f.get('assigned_to','')],f"Fitur \"{f['name']}\" → {data.status}",f"{u['name']} memperbarui progres fitur pada project {p['name'] if p else ''}.",'fitur',f'/projects/{pid}',pid,'fitur',fid,u,email=False)
    f['status']=data.status
    if u['role']=='Developer': f.pop('price',None)
    return f

@router.delete('/projects/{pid}/features/{fid}')
async def delete_feature(pid:str,fid:str,u=Depends(current_user)):
    await project_for(u,pid,'feature.write')
    f=await db.project_features.find_one({'id':fid,'project_id':pid},{'_id':0})
    if not f: raise HTTPException(404,'Fitur tidak ditemukan.')
    tasks=await db.tasks.find({'source':'feature','source_id':fid},{'_id':0}).to_list(10)
    await trash_item(u,'project_features',f,'fitur',f['name'],[{'collection':'tasks','docs':tasks}])
    await recalc_progress(pid)
    return {'message':'Fitur dipindahkan ke arsip.'}

@router.get('/projects/{pid}/costs')
async def costs(pid:str,u=Depends(current_user)):
    p=await project_for(u,pid,'cost.read')
    return {k:p.get(k,0) for k in ['value','development_cost','server_cost','other_cost']} | {'profit':p['value']-p.get('development_cost',0)-p.get('server_cost',0)-p.get('other_cost',0)}

@router.post('/projects/{pid}/costs')
async def update_costs(pid:str,data:CostInput,u=Depends(current_user)):
    await project_for(u,pid,'cost.write')
    await db.projects.update_one({'id':pid},{'$set':data.model_dump()})
    await log_event(pid,u,'Biaya project diperbarui')
    await log_activity(u,'ubah biaya','project',pid,'',pid,data.model_dump())
    p=await db.projects.find_one({'id':pid},{'_id':0,'name':1})
    await notify(await finance_ids(),f"Biaya project {p['name']} diperbarui",f"{u['name']} memperbarui biaya development/server project ini.",'keuangan',f'/projects/{pid}',pid,'project',pid,u,email=False)
    return await costs(pid,u)

@router.get('/projects/{pid}/documents',response_model=list[Record])
async def documents(pid:str,u=Depends(current_user)):
    await project_for(u,pid,'document.read')
    query={'project_id':pid,'is_deleted':False,'task_id':{'$exists':False}}
    if u['role']=='Client': query['visibility']='Client'
    if u['role']=='Accounting': query['kind']={'$in':['Kontrak','Penawaran Harga','Invoice','BAST']}
    return await db.project_documents.find(query,{'_id':0,'storage_path':0}).to_list(1000)

@router.post('/projects/{pid}/documents',response_model=Record)
async def upload_document(pid:str,file:UploadFile=File(None),kind:str=Form(...),visibility:str=Form('Internal'),name:str=Form(''),url:str=Form(''),u=Depends(current_user)):
    await project_for(u,pid,'document.write')
    if kind=='Lampiran Task': raise HTTPException(400,'Lampiran task diunggah melalui Kanban.')
    doc=await store_document(pid,u,file,kind,visibility,name=name,url=url)
    p=await db.projects.find_one({'id':pid},{'_id':0,'name':1,'client_id':1,'assigned_to':1})
    await notify(await project_people(p,clients=visibility=='Client'),f"Dokumen baru: {doc['name']}",f"{u['name']} mengunggah dokumen {kind} pada project {p['name']}.",'dokumen',f'/projects/{pid}',pid,'dokumen',doc['id'],u)
    return doc

@router.get('/projects/{pid}/documents/{did}/download')
async def download_document(pid:str,did:str,u=Depends(current_user)):
    await project_for(u,pid,'document.read')
    q={'id':did,'project_id':pid,'is_deleted':False}
    if u['role']=='Client': q['visibility']='Client'
    if u['role']=='Accounting': q['kind']={'$in':['Kontrak','Penawaran Harga','Invoice','BAST']}
    d=await db.project_documents.find_one(q,{'_id':0})
    if not d: raise HTTPException(404,'Dokumen tidak ditemukan.')
    if d.get('document_type') == 'link': return RedirectResponse(d['url'], status_code=303)
    try: content=await asyncio.to_thread(get_object,d['storage_path'])
    except Exception: raise HTTPException(503,'Dokumen belum dapat diunduh.')
    return Response(content,media_type=d['content_type'],headers={'Content-Disposition':f"attachment; filename*=UTF-8''{quote(d.get('filename') or d['name'])}",'X-Content-Type-Options':'nosniff'})

@router.delete('/projects/{pid}/documents/{did}')
async def delete_document(pid:str,did:str,u=Depends(current_user)):
    await project_for(u,pid,'document.write')
    d=await db.project_documents.find_one({'id':did,'project_id':pid,'is_deleted':False},{'_id':0})
    if not d: raise HTTPException(404,'Dokumen tidak ditemukan.')
    await db.project_documents.update_one({'id':did},{'$set':{'is_deleted':True}})
    await db.trash.insert_one({'id':uid(),'collection':'project_documents','entity_type':'dokumen','entity_id':did,'name':d['name'],'project_id':pid,'data':d,'related':[],'deleted_by':u['id'],'deleted_by_name':u['name'],'deleted_at':now(),'soft':True})
    await log_activity(u,'hapus','dokumen',did,d['name'],pid,{'ke_arsip':True})
    return {'message':'Dokumen dipindahkan ke arsip.'}

def work_action(kind):
    if kind not in ['revisions','maintenances']: raise HTTPException(404,'Modul tidak ditemukan.')
    return 'revision' if kind=='revisions' else 'maintenance'

async def attach_task_info(rows):
    """Kanban adalah sumber kebenaran: PIC, prioritas & tanggal kartu mengikuti task Kanban terkait."""
    tids=[r['task_id'] for r in rows if r.get('task_id')]
    if not tids: return rows
    tasks={t['id']:t async for t in db.tasks.find({'id':{'$in':tids}},{'_id':0,'id':1,'assigned_to':1,'assignee_ids':1,'priority':1,'due_date':1,'start_date':1,'status':1,'description_html':1})}
    people=set()
    for t in tasks.values(): people.update(assignee_ids(t))
    names={x['id']:x['name'] async for x in db.users.find({'id':{'$in':list(people)}},{'_id':0,'id':1,'name':1})}
    for r in rows:
        t=tasks.get(r.get('task_id'))
        if not t: continue
        ids=assignee_ids(t)
        r['assigned_to']=ids[0] if ids else ''
        r['assignees']=[{'id':i,'name':names.get(i,'Pengguna tidak aktif')} for i in ids]
        r['task_status']=t.get('status')
        if t.get('description_html') is not None: r['description_html']=t['description_html']
        if t.get('priority'): r['priority']=t['priority']
        if t.get('due_date'): r['due_date']=t['due_date']
        if t.get('start_date') and not r.get('started_date'): r['started_date']=t['start_date']
    return rows

@router.get('/work/{kind}',response_model=list[Record])
async def all_work(kind:str,u=Depends(current_user)):
    action=work_action(kind)
    await authorize(u,action+'.read')
    projects=await db.projects.find(project_scope(u),{'_id':0,'id':1,'name':1}).to_list(2000)
    names={p['id']:p['name'] for p in projects}
    rows=await db[kind].find({'project_id':{'$in':list(names)}},{'_id':0}).sort('created_at',-1).to_list(2000)
    if kind == 'maintenances': rows += await ticket_maintenance_rows(u, list(names))
    rows.sort(key=lambda r: r.get('created_at', ''), reverse=True)
    if u['role']=='Developer':
        for r in rows: r.pop('estimate',None)
    await attach_task_info(rows)
    return [{**r,'project_name':names[r['project_id']]} for r in rows]

@router.get('/projects/{pid}/work/{kind}',response_model=list[Record])
async def project_work(pid:str,kind:str,u=Depends(current_user)):
    await project_for(u,pid,work_action(kind)+'.read')
    projection={'_id':0}
    if u['role']=='Developer': projection['estimate']=0
    rows = await db[kind].find({'project_id':pid},projection).sort('created_at',-1).to_list(1000)
    if kind == 'maintenances': rows += await ticket_maintenance_rows(u, [pid])
    await attach_task_info(rows)
    return sorted(rows, key=lambda r: r.get('created_at', ''), reverse=True)

@router.post('/projects/{pid}/work/{kind}',response_model=Record)
async def create_work(pid:str,kind:str,data:WorkInput,u=Depends(current_user)):
    p=await project_for(u,pid,work_action(kind)+'.write')
    allowed=['In-scope','Out-of-scope','Change Request'] if kind=='revisions' else ['Adaptive','Corrective','Preventive','Support','Change Request']
    if data.kind not in allowed: raise HTTPException(400,'Jenis pekerjaan tidak valid.')
    await validate_assignee(data.assigned_to,p)
    body=data.model_dump(mode='json'); subtasks=body.pop('subtasks')
    body['entry_date']=body.get('entry_date') or now()[:10]
    initial='Belum dikerjakan' if kind=='maintenances' else 'Terbuka'
    if kind=='maintenances' and body.get('started_date'): initial='Development'
    doc={**body,'id':uid(),'project_id':pid,'status':initial,'approved':False,'created_at':now(),'completed_at':None,'created_by':u['id']}
    task=await create_task(pid,u,title=data.title,description=data.description,status='Revisi' if kind=='revisions' else ('Dikerjakan' if initial=='Development' else 'Belum Mulai'),assigned_to=data.assigned_to,due_date=body['due_date'],start_date=body.get('started_date'),priority=data.priority,source=work_action(kind),source_id=doc['id'],subtasks=subtasks,tags=[data.kind])
    doc['task_id']=task['id']
    await db[kind].insert_one(doc.copy())
    label='Revisi' if kind=='revisions' else 'Maintenance'
    await log_activity(u,'buat',label.lower(),doc['id'],data.title,pid)
    await notify(await manager_ids(),f"{label} baru: {data.title}",f"{u['name']} mencatat {label.lower()} ({data.kind}) pada project {p['name']}.",label.lower(),'/'+('revisions' if kind=='revisions' else 'maintenance'),pid,label.lower(),doc['id'],u,email=False)
    return doc

MAINT_TO_TASK={'Belum dikerjakan':'Belum Mulai','Development':'Dikerjakan','Testing':'Testing','Selesai':'Selesai','Terbuka':'Belum Mulai','Dikerjakan':'Dikerjakan'}

@router.patch('/projects/{pid}/work/{kind}/{wid}',response_model=Record)
async def update_work(pid:str,kind:str,wid:str,data:WorkUpdate,u=Depends(current_user)):
    await project_for(u,pid,work_action(kind)+'.write')
    doc=await db[kind].find_one({'id':wid,'project_id':pid},{'_id':0})
    if not doc: raise HTTPException(404,'Pekerjaan tidak ditemukan.')
    allowed=MAINTENANCE_STATUSES if kind=='maintenances' else WORK_STATUSES
    if data.status not in allowed: raise HTTPException(400,'Status tidak valid.')
    todo=allowed[0]
    if doc['kind'] in ['Out-of-scope','Change Request'] and data.status!=todo and (max(doc.get('estimate',0),data.estimate or 0)<=0 or not (data.approved or doc.get('approved'))): raise HTTPException(400,'Pekerjaan di luar scope wajib memiliki estimasi biaya dan persetujuan.')
    update={'status':data.status,'approved':data.approved or doc.get('approved',False),'completed_at':now() if data.status=='Selesai' else None}
    for k in ['started_date','due_date','priority','estimate']:
        v=getattr(data,k)
        if v is not None: update[k]=v.isoformat() if hasattr(v,'isoformat') else v
    if kind=='maintenances' and data.status in ['Development','Testing'] and not update.get('started_date',doc.get('started_date')): update['started_date']=now()[:10]
    await db[kind].update_one({'id':wid,'project_id':pid},{'$set':update})
    task_sync={k2:update[k1] for k1,k2 in [('priority','priority'),('due_date','due_date'),('started_date','start_date')] if k1 in update}
    if task_sync: await db.tasks.update_many({'source':work_action(kind),'source_id':wid},{'$set':{**task_sync,'updated_at':now()}})
    if data.status!=doc['status']: await sync_task_status(work_action(kind),wid,MAINT_TO_TASK.get(data.status,'Belum Mulai'))
    label='Revisi' if kind=='revisions' else 'Maintenance'
    await log_activity(u,'ubah',label.lower(),wid,doc['title'],pid,{'dari':doc['status'],'ke':data.status})
    if data.status!=doc['status']:
        await notify([doc.get('assigned_to','')]+await manager_ids(),f"{label} \"{doc['title']}\" → {data.status}",f"{u['name']} memperbarui status {label.lower()} dari {doc['status']} menjadi {data.status}.",label.lower(),'/'+('revisions' if kind=='revisions' else 'maintenance'),pid,label.lower(),wid,u)
    return {**doc,**update}

@router.delete('/projects/{pid}/work/{kind}/{wid}')
async def delete_work(pid:str,kind:str,wid:str,u=Depends(current_user)):
    await project_for(u,pid,work_action(kind)+'.write')
    doc=await db[kind].find_one({'id':wid,'project_id':pid},{'_id':0})
    if not doc: raise HTTPException(404,'Pekerjaan tidak ditemukan.')
    tasks=await db.tasks.find({'source':work_action(kind),'source_id':wid},{'_id':0}).to_list(10)
    await trash_item(u,kind,doc,'revisi' if kind=='revisions' else 'maintenance',doc['title'],[{'collection':'tasks','docs':tasks}])
    return {'message':'Pekerjaan dipindahkan ke arsip.'}

@router.get('/projects/{pid}/deployments',response_model=list[Record])
async def deployments(pid:str,u=Depends(current_user)):
    await project_for(u,pid,'deployment.read')
    return await db.deployments.find({'project_id':pid},{'_id':0}).sort('created_at',-1).to_list(500)

@router.post('/projects/{pid}/deployments',response_model=Record)
async def create_deploy(pid:str,data:DeployInput,u=Depends(current_user)):
    p=await project_for(u,pid,'deployment.write')
    if data.environment=='Production' and (u['role']!='Admin' or not p.get('production_at')): raise HTTPException(403,'Deployment production dicatat Admin setelah persetujuan production.')
    doc={**data.model_dump(),'id':uid(),'project_id':pid,'created_at':now(),'created_by':u['name']}
    await db.deployments.insert_one(doc.copy())
    await notify(await project_people(p,clients=data.environment=='Production'),f"Deployment {data.environment}: {p['name']} v{data.version}",f"{u['name']} mencatat deployment {data.environment.lower()} di {data.url}.",'deployment',f'/projects/{pid}',pid,'deployment',doc['id'],u)
    return doc