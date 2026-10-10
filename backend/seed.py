import os
from datetime import datetime,timedelta,timezone
from core import db,now
from auth import hash_password

async def seed_cost_types():
    if await db.cost_types.count_documents({}): return
    for name,group in [('Gaji Developer','Development'),('Freelancer / Outsource','Development'),('Hosting / VPS','Server'),('Domain & SSL','Server'),('Lisensi & Tools','Lainnya'),('Operasional & Transport','Lainnya')]:
        await db.cost_types.insert_one({'id':'cost-'+name.split()[0].lower(),'name':name,'group':group,'description':'','active':True,'created_at':now()})

async def seed():
    if await db.users.count_documents({}): return
    password=hash_password(os.environ['SEED_PASSWORD'])
    if os.environ.get('SEED_SAMPLE_DATA', 'true').strip().lower() == 'false':
        await db.users.insert_one({'id':'user-admin','username':'admin','name':'Administrator','role':'Admin','email':os.environ['ADMIN_EMAIL'],'client_id':'','password_hash':password,'active':True,'must_change_password':True,'created_at':now()})
        return
    users=[('admin','Giselle Haruka','Admin',os.environ['ADMIN_EMAIL'],''),('adminproject','Made Arya','Admin Project','arya@maiharta.example',''),('developer','Kadek Putra','Developer','putra@maiharta.example',''),('accounting','Putu Dewi','Accounting','dewi@maiharta.example',''),('client','Ayu Pratiwi','Client','ayu@nusantara.example','client-1')]
    for username,name,role,email,cid in users:
        await db.users.insert_one({'id':'user-'+username,'username':username,'name':name,'role':role,'email':email,'client_id':cid,'password_hash':password,'active':True,'created_at':now()})
    clients=[('Nusantara Living','Ayu Pratiwi','Properti & Hospitality'),('Bali Coffee Co.','Wayan Aditya','Food & Beverage'),('Svara Creative','Dian Putri','Industri Kreatif'),('Aruna Wellness','Citra Lestari','Kesehatan'),('Loka Studio','Rama Wijaya','Arsitektur')]
    for i,(name,contact,industry) in enumerate(clients,1):
        await db.clients.insert_one({'id':f'client-{i}','name':name,'contact':contact,'industry':industry,'email':f'hello@client{i}.example','phone':f'+62 812 3400 000{i}','address':'Denpasar, Bali','created_at':now()})
    base=datetime.now(timezone.utc)
    samples=[('Nusantara Living — Website',1,'Web Development','Development',65,45000000,22000000,2500000,12),('Bali Coffee — Online Store',2,'E-Commerce','Testing',85,32000000,14000000,1800000,5),('Svara — Brand Experience',3,'UI/UX Design','UI/UX',30,24000000,9000000,0,21),('Aruna — Booking Platform',4,'Web Application','Uploaded to Production',100,68000000,31000000,4000000,-2),('Loka — Company Profile',5,'Web Development','Selesai',100,18500000,7000000,1000000,-10),('Nusantara — Client Portal',1,'Web Application','Scope Dirinci',15,52000000,23000000,3000000,40),('Bali Coffee — Loyalty App',2,'Mobile Application','Project Masuk',0,38000000,16000000,2000000,55),('Svara — Event Microsite',3,'Web Development','Revisi',90,16000000,6500000,1000000,3)]
    for i,(name,ci,cat,status,progress,value,dev,server,days) in enumerate(samples,1):
        pid=f'project-{i}';start=(base-timedelta(days=40-i*2)).date().isoformat();due=(base+timedelta(days=days)).date().isoformat()
        await db.projects.insert_one({'id':pid,'code':f'MH-{i:03d}','name':name,'client_id':f'client-{ci}','client_name':clients[ci-1][0],'category':cat,'type':'Besar' if value>20000000 else 'Kecil','description':f'Pengembangan {cat.lower()} untuk {clients[ci-1][0]}, dengan pengalaman digital yang intuitif dan identitas brand yang kuat.','status':status,'progress':progress,'value':value,'development_cost':dev,'server_cost':server,'start_date':start,'due_date':due,'assigned_to':['user-developer'] if i!=7 else [],'internal_notes':'Koordinasikan seluruh perubahan scope dengan Admin Project.','production_at':now() if status in ['Uploaded to Production','Selesai'] else None,'created_at':(base-timedelta(days=40-i*2)).isoformat(),'updated_at':(base-timedelta(hours=i)).isoformat(),'created_by':'user-admin','tickets_closed':False})
        features=[('Desain antarmuka & design system','UI/UX'),('Halaman utama & navigasi','Frontend'),('Autentikasi & manajemen akun','Backend'),('Dashboard & laporan','Frontend'),('Integrasi API & database','Backend'),('Pengujian & optimasi','Lainnya')]
        for j,(fn,fc) in enumerate(features):
            await db.project_features.insert_one({'id':f'feature-{i}-{j}','project_id':pid,'name':fn,'category':fc,'price':round(value/6),'status':'Selesai' if j<round(progress/100*6) else 'Dikerjakan' if j==round(progress/100*6) else 'Belum dimulai','assigned_to':'user-developer' if i!=7 else '', 'due_date':(base+timedelta(days=days-5+j)).date().isoformat(),'created_at':now()})
        await db.project_status_logs.insert_one({'id':f'log-{i}','project_id':pid,'user_name':'Made Arya','message':f'Project diperbarui ke {status}','to_status':status,'created_at':(base-timedelta(hours=i)).isoformat()})
    await db.counters.update_one({'id':'project'},{'$set':{'value':8}},upsert=True)
    for i,(pid,title,cat,priority,status) in enumerate([('project-1','Penyesuaian tampilan galeri mobile','Bug / Problem','Sedang','Baru'),('project-4','Pembaruan jadwal konsultasi','Maintenance','Rendah','Ditinjau'),('project-2','Tombol checkout tidak merespons','Bug / Problem','Tinggi','Dikerjakan'),('project-1','Penambahan pilihan bahasa Inggris','Change Request','Sedang','Menunggu Estimasi Biaya')],1):
        p=await db.projects.find_one({'id':pid},{'_id':0})
        await db.tickets.insert_one({'id':f'ticket-{i}','code':f'TKT-{i:04d}','project_id':pid,'project_name':p['name'],'title':title,'description':title+'. Mohon ditinjau oleh tim MaiHarta. Terima kasih.','category':cat,'priority':priority,'status':status,'assigned_to':'user-developer' if status=='Dikerjakan' else '', 'triaged':status!='Baru','approved':False,'estimate':0,'created_by':'user-client','created_by_name':'Ayu Pratiwi','created_at':(base-timedelta(hours=i*3)).isoformat(),'updated_at':now()})
    await db.revisions.insert_one({'id':'revision-1','project_id':'project-8','title':'Penyesuaian layout halaman agenda','description':'Sesuaikan jarak antar sesi pada versi mobile.','kind':'In-scope','assigned_to':'user-developer','due_date':(base+timedelta(days=3)).date().isoformat(),'estimate':0,'status':'Dikerjakan','approved':True,'created_at':now(),'completed_at':None})
    await db.maintenances.insert_one({'id':'maintenance-1','project_id':'project-4','title':'Pembaruan dependensi & optimasi performa','description':'Pemeriksaan berkala platform booking.','kind':'Corrective','assigned_to':'user-developer','due_date':(base+timedelta(days=7)).date().isoformat(),'estimate':0,'status':'Terbuka','approved':False,'created_at':now(),'completed_at':None})
async def backfill_tasks():
    from kanban import create_task
    system = {'id': 'system', 'name': 'Sistem'}
    F = {'Belum dimulai': 'Belum Mulai', 'Dikerjakan': 'Dikerjakan', 'Selesai': 'Selesai'}
    async for f in db.project_features.find({'task_id': {'$exists': False}}, {'_id': 0}):
        t = await create_task(f['project_id'], system, title=f['name'], description=f"Fitur {f.get('category', '')}", status=F.get(f.get('status'), 'Belum Mulai'), assigned_to=f.get('assigned_to', ''), due_date=f.get('due_date'), source='feature', source_id=f['id'], tags=[f.get('category', 'Fitur')])
        await db.project_features.update_one({'id': f['id']}, {'$set': {'task_id': t['id']}})
    async for k in db.tickets.find({'task_id': {'$exists': False}, 'status': {'$nin': ['Ditolak', 'Ditutup']}}, {'_id': 0}):
        st = {'Dikerjakan': 'Dikerjakan', 'Selesai': 'Selesai'}.get(k['status'], 'Belum Mulai')
        t = await create_task(k['project_id'], system, title=f"[{k['code']}] {k['title']}", description=k.get('description', ''), status=st, assigned_to=k.get('assigned_to', ''), priority=k.get('priority', 'Sedang'), source='ticket', source_id=k['id'], tags=['Tiket', k.get('category', '')])
        await db.tickets.update_one({'id': k['id']}, {'$set': {'task_id': t['id']}})
    for kind, src, default in [('revisions', 'revision', 'Revisi'), ('maintenances', 'maintenance', 'Belum Mulai')]:
        async for w in db[kind].find({'task_id': {'$exists': False}}, {'_id': 0}):
            st = {'Dikerjakan': 'Dikerjakan', 'Selesai': 'Selesai'}.get(w['status'], default)
            t = await create_task(w['project_id'], system, title=w['title'], description=w.get('description', ''), status=st, assigned_to=w.get('assigned_to', ''), due_date=w.get('due_date'), source=src, source_id=w['id'], tags=[w.get('kind', '')])
            await db[kind].update_one({'id': w['id']}, {'$set': {'task_id': t['id']}})

async def migrate():
    await db.maintenances.update_many({'status': 'Terbuka'}, {'$set': {'status': 'Belum dikerjakan'}})
    await db.maintenances.update_many({'status': 'Dikerjakan'}, {'$set': {'status': 'Development'}})
    await db.maintenances.update_many({'priority': {'$exists': False}}, {'$set': {'priority': 'Sedang'}})
    await db.revisions.update_many({'priority': {'$exists': False}}, {'$set': {'priority': 'Sedang'}})
    for coll in ['maintenances', 'revisions']:
        async for w in db[coll].find({'entry_date': {'$exists': False}}, {'_id': 0, 'id': 1, 'created_at': 1}):
            await db[coll].update_one({'id': w['id']}, {'$set': {'entry_date': (w.get('created_at') or now())[:10], 'started_date': None}})
    async for p in db.projects.find({'platforms': {'$exists': False}}, {'_id': 0, 'id': 1, 'category': 1}):
        c = p.get('category', '')
        plat = ['Mobile Android', 'Mobile iOS'] if 'Mobile' in c else ['UI/UX Design'] if 'UI/UX' in c else ['Web']
        await db.projects.update_one({'id': p['id']}, {'$set': {'platforms': plat}})
