import csv, io
from datetime import datetime, timezone
from fastapi import APIRouter,Depends,HTTPException,Response
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from core import db,uid,now,authorize,project_scope,project_public,log_activity,FINANCE,MANAGERS,STATUSES,TICKET_STATUSES,DEFAULT_CLIENT_PASSWORD
from auth import current_user,hash_password,public_user
from schemas import Record,ClientInput,UserInput,UserUpdate
from notify import notify,manager_ids,finance_ids
from whatsapp import normalize_phone

router=APIRouter()
TICKET_OPEN=['Baru','Ditinjau','Menunggu Klarifikasi','Diterima','Menunggu Estimasi Biaya','Menunggu Persetujuan']
TICKET_CLOSED=['Selesai','Ditutup','Ditolak']
@router.get('/users',response_model=list[Record])
async def users(u=Depends(current_user)):
    await authorize(u,'user.manage')
    rows=await db.users.find({},{'_id':0,'password_hash':0}).to_list(1000)
    return rows
@router.get('/team',response_model=list[Record])
async def team(u=Depends(current_user)):
    await authorize(u,'team.read')
    return await db.users.find({'active':True,'role':{'$in':MANAGERS+['Developer']}},{'_id':0,'id':1,'name':1,'role':1}).sort('name',1).to_list(500)
def _wa_fields(number,source):
    if not number: return {}
    return {'whatsapp_number':number,'notification_preferences':{'in_app':True,'email':True,'whatsapp':True},'whatsapp_opt_in_at':now(),'whatsapp_opt_in_source':source}
async def send_welcome(account,actor,password=''):
    """Selamat datang: in-app + email + WhatsApp, email & WhatsApp sama-sama memuat username dan password awal."""
    title=f"Selamat datang di CRM Maiharta, {account['name']}"
    base=f"Akun Anda di CRM Maiharta sudah aktif dengan role {account['role']}. Username Anda: {account['username']}."
    first_login=" Saat pertama kali masuk, Anda akan diminta membuat password baru (minimal 10 karakter)."
    in_app=base+first_login
    wa_msg=base+(f" Password awal: {password}." if password else '')+first_login+" Jika email dari CRM Maiharta masuk folder Spam, mohon tandai sebagai Bukan Spam."
    sender=(actor or {}).get('name') or 'Tim CV Maiharta'
    email_msg=(f"{sender} dari CV Maiharta telah menambahkan Anda ke CRM Maiharta sebagai {account['role']}. "
               "Di sini kita akan berkoordinasi mengenai progres project, dokumen dan tiket bersama. "
               "Masuk memakai username"+(" dan password awal" if password else '')+" di bawah ini."+first_login+" "
               "Bila ada pertanyaan, cukup balas email ini. Terima kasih dan selamat bergabung.")
    credentials=[('Username',account['username'])]+([('Password awal',password)] if password else [])
    await notify([account['id']],title,in_app,'akun','/','','user',account['id'],None,external={'kind':'sambutan','title':f"Selamat bergabung, {account['name']}",'message':email_msg,'whatsapp_message':wa_msg,'credentials':credentials,'link':'/'})
@router.post('/users',response_model=Record)
async def add_user(data:UserInput,u=Depends(current_user)):
    await authorize(u,'user.manage')
    if await db.users.find_one({'username':data.username.lower()},{'_id':0}): raise HTTPException(409,'Username sudah digunakan.')
    if data.role=='Client' and not await db.clients.find_one({'id':data.client_id},{'_id':0}): raise HTTPException(400,'Akun Client harus terhubung ke client yang valid.')
    try: number=normalize_phone(data.whatsapp_number)
    except ValueError as e: raise HTTPException(400,str(e))
    row={k:v for k,v in data.model_dump().items() if k not in ('password','whatsapp_number')}  # password awal selalu default, sama seperti akun Client
    row.update(id=uid(),username=data.username.lower(),password_hash=hash_password(DEFAULT_CLIENT_PASSWORD),active=True,must_change_password=True,welcome_pending=True,created_at=now(),**_wa_fields(number,'admin_created'))
    try: await db.users.insert_one(row.copy())
    except Exception: raise HTTPException(409,'Username sudah digunakan.')
    await log_activity(u,'buat','user',row['id'],row['name'],'',{'role':row['role']})
    await send_welcome(row,u,DEFAULT_CLIENT_PASSWORD)
    return public_user(row)|{'default_password':DEFAULT_CLIENT_PASSWORD}
@router.patch('/users/{user_id}',response_model=Record)
async def edit_user(user_id:str,data:UserUpdate,u=Depends(current_user)):
    await authorize(u,'user.manage')
    row=await db.users.find_one({'id':user_id},{'_id':0})
    if not row: raise HTTPException(404,'User tidak ditemukan.')
    updates=data.model_dump(exclude_none=True)
    new_password=updates.pop('new_password',None)
    if new_password:
        updates['password_hash']=hash_password(new_password)
        await db.sessions.delete_many({'user_id':user_id})
    if 'username' in updates:
        updates['username']=updates['username'].lower()
        if updates['username']!=row['username'] and await db.users.find_one({'username':updates['username'],'id':{'$ne':user_id}},{'_id':0,'id':1}): raise HTTPException(409,'Username sudah digunakan.')
    if 'email' in updates:
        updates['email']=str(updates['email']).lower()
        if await db.users.find_one({'email':updates['email'],'id':{'$ne':user_id}},{'_id':0,'id':1}): raise HTTPException(409,'Email sudah digunakan akun lain.')
    if 'whatsapp_number' in updates:
        try: updates['whatsapp_number']=normalize_phone(updates['whatsapp_number'])
        except ValueError as e: raise HTTPException(400,str(e))
        if not updates['whatsapp_number'] and row.get('notification_preferences',{}).get('whatsapp'):
            updates['notification_preferences']={**row.get('notification_preferences',{}),'whatsapp':False}
            updates['whatsapp_opt_out_at']=now()
    if user_id==u['id'] and (updates.get('active') is False or updates.get('role',u['role'])!='Admin'): raise HTTPException(400,'Anda tidak dapat menonaktifkan atau menurunkan role akun sendiri.')
    merged={**row,**updates}
    if merged['role']=='Client' and not await db.clients.find_one({'id':merged.get('client_id','')},{'_id':0}): raise HTTPException(400,'Pilih client untuk akun ini.')
    try: await db.users.update_one({'id':user_id},{'$set':updates})
    except Exception: raise HTTPException(409,'Username sudah digunakan.')
    await log_activity(u,'ubah','user',user_id,merged['name'],'',{k:v for k,v in updates.items() if k not in ('password_hash','notification_preferences')}|({'reset_password':True} if new_password else {}))
    if updates.get('active') is False: await db.sessions.delete_many({'user_id':user_id})
    return public_user(merged)
@router.delete('/users/{user_id}')
async def delete_user(user_id:str,u=Depends(current_user)):
    await authorize(u,'user.manage')
    if user_id==u['id']: raise HTTPException(400,'Anda tidak dapat menghapus akun sendiri.')
    row=await db.users.find_one({'id':user_id},{'_id':0,'password_hash':0})
    if not row: raise HTTPException(404,'User tidak ditemukan.')
    if row['role']=='Admin' and await db.users.count_documents({'role':'Admin','active':True,'id':{'$ne':user_id}})==0: raise HTTPException(400,'Minimal harus ada satu Admin aktif.')
    await db.users.delete_one({'id':user_id})
    await db.sessions.delete_many({'user_id':user_id})
    await db.notifications.delete_many({'user_id':user_id})
    await db.projects.update_many({'assigned_to':user_id},{'$pull':{'assigned_to':user_id}})
    await db.tasks.update_many({'assignee_ids':user_id},{'$pull':{'assignee_ids':user_id}})
    await db.tasks.update_many({'assigned_to':user_id},{'$set':{'assigned_to':''}})
    await log_activity(u,'hapus','user',user_id,row['name'],'',{'username':row['username'],'role':row['role']})
    return {'message':f"User {row['name']} dihapus permanen."}

@router.get('/clients',response_model=list[Record])
async def clients(u=Depends(current_user)):
    await authorize(u,'client.read')
    rows=await db.clients.find({},{'_id':0}).sort('created_at',-1).to_list(2000)
    for r in rows: r['project_count']=await db.projects.count_documents({'client_id':r['id']})
    return rows
@router.post('/clients',response_model=Record)
async def add_client(data:ClientInput,u=Depends(current_user)):
    await authorize(u,'client.write')
    row={**data.model_dump(),'id':uid(),'created_at':now()}
    await db.clients.insert_one(row.copy())
    await log_activity(u,'buat','client',row['id'],row['name'])
    username=data.email.lower()
    account={'username':username,'created':False}
    if not await db.users.find_one({'username':username},{'_id':0,'id':1}):
        try: number=normalize_phone(data.phone)
        except ValueError: number=''
        new_account={'id':uid(),'username':username,'name':data.contact,'role':'Client','email':data.email,'client_id':row['id'],'password_hash':hash_password(DEFAULT_CLIENT_PASSWORD),'active':True,'must_change_password':True,'welcome_pending':True,'created_at':now(),**_wa_fields(number,'admin_client_created')}
        await db.users.insert_one(new_account.copy())
        account.update(created=True,password=DEFAULT_CLIENT_PASSWORD)
        await send_welcome(new_account,u,DEFAULT_CLIENT_PASSWORD)
    await notify(await manager_ids()+await finance_ids(),f"Client baru: {data.name}",f"{u['name']} menambahkan client {data.name} ({data.contact}).",'client','/clients','','client',row['id'],u,email=False)
    return {**row,'account':account}
@router.patch('/clients/{cid}',response_model=Record)
async def edit_client(cid:str,data:ClientInput,u=Depends(current_user)):
    await authorize(u,'client.write')
    r=await db.clients.update_one({'id':cid},{'$set':data.model_dump()})
    if not r.matched_count: raise HTTPException(404,'Client tidak ditemukan.')
    await db.projects.update_many({'client_id':cid},{'$set':{'client_name':data.name}})
    return await db.clients.find_one({'id':cid},{'_id':0})
@router.delete('/clients/{cid}')
async def delete_client(cid:str,u=Depends(current_user)):
    await authorize(u,'client.write')
    if await db.projects.count_documents({'client_id':cid}) or await db.users.count_documents({'client_id':cid}): raise HTTPException(400,'Client masih terhubung dengan project atau akun.')
    r=await db.clients.delete_one({'id':cid})
    if not r.deleted_count: raise HTTPException(404,'Client tidak ditemukan.')
    await log_activity(u,'hapus','client',cid,'')
    return {'message':'Client dihapus.'}

@router.get('/dashboard')
async def dashboard(u=Depends(current_user)):
    await authorize(u,'dashboard.read')
    rows=await db.projects.find(project_scope(u),{'_id':0}).sort('updated_at',-1).to_list(2000)
    ids=[p['id'] for p in rows]
    status_counts={s:sum(p['status']==s for p in rows) for s in STATUSES}
    tq={'project_id':{'$in':ids}}
    if u['role']=='Developer': tq['assigned_to']=u['id']
    result={'total':len(rows),'active':sum(p['status']!='Selesai' for p in rows),'completed':status_counts['Selesai'],'development':status_counts['Development'],'dev_server':status_counts['Uploaded to Dev Server'],'production':status_counts['Uploaded to Production'],'status_counts':status_counts,'projects':[project_public(p,u) for p in rows[:5]],'active_revisions':0,'active_maintenance':0,'open_tickets':0,'closed_tickets':0}
    if u['role']=='Client':
        counts={s:await db.tickets.count_documents({**tq,'status':s}) for s in TICKET_STATUSES}
        result['ticket_stats']={'total':sum(counts.values()),'open':sum(counts[s] for s in TICKET_OPEN),'in_progress':counts['Dikerjakan'],'closed':sum(counts[s] for s in TICKET_CLOSED),'waiting_client':counts['Menunggu Klarifikasi']+counts['Menunggu Persetujuan'],'rejected':counts['Ditolak']}
    if u['role']!='Accounting':
        result['open_tickets']=await db.tickets.count_documents({**tq,'status':{'$nin':['Selesai','Ditutup','Ditolak']}})
        result['closed_tickets']=await db.tickets.count_documents({**tq,'status':{'$in':['Selesai','Ditutup']}})
    if u['role'] in MANAGERS+['Developer']:
        result['active_revisions']=await db.revisions.count_documents({'project_id':{'$in':ids},'status':{'$ne':'Selesai'}})
        result['active_maintenance']=await db.maintenances.count_documents({'project_id':{'$in':ids},'status':{'$ne':'Selesai'}})
        result['active_maintenance']+=await db.tickets.count_documents({**tq,'status':{'$nin':['Selesai','Ditutup','Ditolak']}})
    if u['role'] in FINANCE:
        result['finance']={k:sum(p.get(k,0) for p in rows) for k in ['value','development_cost','server_cost','other_cost']}
        result['finance']['profit']=result['finance']['value']-result['finance']['development_cost']-result['finance']['server_cost']-result['finance']['other_cost']
    elif u['role']=='Admin Project': result['total_value']=sum(p.get('value',0) for p in rows)
    histories=await db.project_status_logs.find({'project_id':{'$in':ids}},{'_id':0}).sort('created_at',-1).to_list(30)
    names={p['id']:p['name'] for p in rows}
    if u['role']=='Client': histories=[{k:r[k] for k in ['id','project_id','message','created_at'] if k in r} for r in histories if r.get('to_status')]
    result['activity']=[{**r,'project_name':names.get(r['project_id'],'')} for r in histories[:5]]
    result['deadlines']=[project_public(p,u) for p in sorted(rows,key=lambda p:p['due_date']) if p['status']!='Selesai'][:4]
    return result

@router.get('/reports/projects.csv')
async def report(u=Depends(current_user)):
    await authorize(u,'project.list')
    rows=await db.projects.find(project_scope(u),{'_id':0}).to_list(2000)
    fields=['Kode','Project','Client','Status','Progress','Deadline']
    if u['role'] in FINANCE: fields+=['Nilai Project','Biaya Development','Biaya Server','Profit']
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(fields)
    def safe(v):
        s=str(v)
        return "'"+s if s.startswith(('=','+','-','@')) else s
    for p in rows:
        values=[p['code'],p['name'],p['client_name'],p['status'],p['progress'],p['due_date']]
        if u['role'] in FINANCE: values += [p['value'],p.get('development_cost',0),p.get('server_cost',0),p['value']-p.get('development_cost',0)-p.get('server_cost',0)]
        writer.writerow([safe(v) for v in values])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=laporan-project-maiharta.csv'})

@router.get('/reports/projects.xlsx')
async def report_xlsx(u=Depends(current_user)):
    await authorize(u,'project.list')
    rows=await db.projects.find(project_scope(u),{'_id':0}).sort('code',1).to_list(2000)
    is_finance=u['role'] in FINANCE
    headers=['Kode','Project','Client','Status','Progress','Deadline']
    if is_finance: headers+=['Nilai Project','Biaya Development','Biaya Server','Profit']
    ncols=len(headers); last=get_column_letter(ncols)
    NAVY='1E3A5F'; BLUE='2F5FE0'; LIGHT='EEF3FF'; BAND='F7F9FE'; LINE='D9E1F2'
    thin=Side(style='thin', color=LINE)
    border=Border(left=thin,right=thin,top=thin,bottom=thin)
    money_fmt='"Rp"#,##0'
    wb=Workbook(); ws=wb.active; ws.title='Laporan Project'
    # Title band
    ws.merge_cells(f'A1:{last}1')
    c=ws['A1']; c.value='Laporan Project — CRM Maiharta'
    c.font=Font(name='Calibri',size=16,bold=True,color='FFFFFF')
    c.fill=PatternFill('solid',fgColor=NAVY)
    c.alignment=Alignment(horizontal='left',vertical='center',indent=1)
    ws.row_dimensions[1].height=34
    ws.merge_cells(f'A2:{last}2')
    s=ws['A2']
    s.value=f"Dibuat {datetime.now(timezone.utc).strftime('%d %b %Y')}  ·  {len(rows)} project"
    s.font=Font(name='Calibri',size=10,italic=True,color='FFFFFF')
    s.fill=PatternFill('solid',fgColor=BLUE)
    s.alignment=Alignment(horizontal='left',vertical='center',indent=1)
    ws.row_dimensions[2].height=20
    # Header row
    hr=4
    for i,h in enumerate(headers, start=1):
        cell=ws.cell(row=hr,column=i,value=h)
        cell.font=Font(bold=True,color='FFFFFF',size=11)
        cell.fill=PatternFill('solid',fgColor=BLUE)
        cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
        cell.border=border
    ws.row_dimensions[hr].height=26
    # Data rows
    r=hr+1
    for idx,p in enumerate(rows):
        prof=p['value']-p.get('development_cost',0)-p.get('server_cost',0)
        vals=[p['code'],p['name'],p['client_name'],p['status'],(p.get('progress',0) or 0)/100,p['due_date']]
        if is_finance: vals+=[p['value'],p.get('development_cost',0),p.get('server_cost',0),prof]
        for ci,v in enumerate(vals, start=1):
            cell=ws.cell(row=r,column=ci,value=v)
            cell.border=border
            cell.alignment=Alignment(vertical='center',horizontal='center' if ci in (1,4,5,6) else 'left')
            if idx%2: cell.fill=PatternFill('solid',fgColor=BAND)
        pc=ws.cell(row=r,column=5); pc.number_format='0%'; pc.alignment=Alignment(horizontal='center',vertical='center')
        if is_finance:
            for ci in range(7,ncols+1):
                mc=ws.cell(row=r,column=ci); mc.number_format=money_fmt
                mc.alignment=Alignment(horizontal='right',vertical='center')
        r+=1
    # Totals
    if is_finance and rows:
        tr=r
        lc=ws.cell(row=tr,column=6,value='Total'); lc.font=Font(bold=True)
        lc.alignment=Alignment(horizontal='right',vertical='center')
        for ci in range(1,7):
            ws.cell(row=tr,column=ci).fill=PatternFill('solid',fgColor=LIGHT)
            ws.cell(row=tr,column=ci).border=border
        for ci in range(7,ncols+1):
            col=get_column_letter(ci)
            tc=ws.cell(row=tr,column=ci,value=f'=SUM({col}{hr+1}:{col}{r-1})')
            tc.number_format=money_fmt; tc.font=Font(bold=True,color=NAVY)
            tc.fill=PatternFill('solid',fgColor=LIGHT); tc.border=border
            tc.alignment=Alignment(horizontal='right',vertical='center')
        ws.row_dimensions[tr].height=22
    # Widths + view
    widths=[12,32,24,22,11,14]
    if is_finance: widths+=[16,18,15,16]
    for ci,w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(ci)].width=w
    ws.freeze_panes=f'A{hr+1}'
    ws.sheet_view.showGridLines=False
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    return Response(buf.getvalue(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition':'attachment; filename=laporan-project-maiharta.xlsx'})