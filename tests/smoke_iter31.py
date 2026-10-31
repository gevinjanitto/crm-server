import os
import requests, re
B='http://localhost:8001/api'
def login(u):
    s=requests.Session(); c=s.get(B+'/auth/captcha').json(); a,b=map(int,re.findall(r'\d+',c['question']))
    r=s.post(B+'/auth/login',json={'username':u,'password':os.environ.get('SEED_PASSWORD',''),'captcha_id':c['id'],'captcha_answer':str(a+b)}); r.raise_for_status()
    tok=r.json().get('token') or r.json().get('access_token')
    if tok: s.headers['Authorization']='Bearer '+tok
    return s
adm=login('admin'); dev=login('developer')
ps=adm.get(B+'/projects').json(); print('admin projects',len(ps), [ (p['code'],p['status'],len(p['assigned_to'])) for p in ps])
print('dev projects',len(dev.get(B+'/projects').json()))
w=adm.get(B+'/work/maintenances').json(); print('maint', [(r['title'][:20], r.get('assignees')) for r in w][:4])
