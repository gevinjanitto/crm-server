import os
import requests, re
B='http://localhost:8001/api'
def login(u):
    s=requests.Session(); c=s.get(B+'/auth/captcha').json(); a,b=map(int,re.findall(r'\d+',c['question']))
    r=s.post(B+'/auth/login',json={'username':u,'password':os.environ.get('SEED_PASSWORD',''),'captcha_id':c['id'],'captcha_answer':str(a+b)}); r.raise_for_status()
    tok=r.json().get('token') or r.json().get('access_token')
    if tok: s.headers['Authorization']='Bearer '+tok
    return s
adm=login('admin'); ap=login('adminproject'); dev=login('developer')
st=lambda s,pid,x: (lambda r:(r.status_code,r.json().get('detail',r.json().get('status'))))(s.post(f'{B}/projects/{pid}/status',json={'status':x,'note':''}))
print('p3 Disetujui->Testing (no docs)', st(adm,'project-3','Testing'))
print('p3 Disetujui->Follow Up', st(adm,'project-3','Follow Up'))
print('p3 Follow Up->Disetujui', st(adm,'project-3','Disetujui'))
print('p2 Testing->Selesai by adminproject', st(ap,'project-2','Selesai'))
print('p2 Testing->Follow Up by dev', st(dev,'project-2','Follow Up'))
print('p2 Testing->Uploaded to Dev Server by dev', st(dev,'project-2','Uploaded to Dev Server'))
print('p2 back ->Testing by dev', st(dev,'project-2','Testing'))
