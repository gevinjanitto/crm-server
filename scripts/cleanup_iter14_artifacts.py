import re
import requests
from dotenv import dotenv_values


BASE = dotenv_values('/app/frontend/.env').get('REACT_APP_BACKEND_URL', '').rstrip('/')
SEED_PASSWORD = dotenv_values('/app/backend/.env').get('SEED_PASSWORD', '')
API = f"{BASE}/api"


def solve(question: str) -> str:
    return str(sum(int(x) for x in re.findall(r'\d+', question)))


def login_admin() -> requests.Session:
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    c = s.get(f"{API}/auth/captcha", timeout=20).json()
    r = s.post(
        f"{API}/auth/login",
        json={
            'username': 'admin',
            'password': SEED_PASSWORD,
            'captcha_id': c['id'],
            'captcha_answer': solve(c['question']),
        },
        timeout=25,
    )
    r.raise_for_status()
    token = r.json()['token']
    s.headers.update({'Authorization': f'Bearer {token}'})
    return s


def main():
    s = login_admin()
    pid = 'project-1'

    tasks = s.get(f"{API}/projects/{pid}/tasks", timeout=25)
    tasks.raise_for_status()
    removed_tasks = 0
    for t in tasks.json():
        title = t.get('title', '')
        if title.startswith('TEST_TOUCH_') or title.startswith('TEST_EMPTY_MOVE_') or title.startswith('WILL_CANCEL_TOUCH'):
            d = s.delete(f"{API}/projects/{pid}/tasks/{t['id']}", timeout=20)
            if d.status_code == 200:
                removed_tasks += 1

    statuses = s.get(f"{API}/projects/{pid}/statuses", timeout=25)
    statuses.raise_for_status()
    removed_status = 0
    for col in statuses.json():
        if str(col.get('name', '')).startswith('Tmp '):
            d = s.delete(f"{API}/projects/{pid}/statuses/{col['id']}?move_to=Belum Mulai", timeout=20)
            if d.status_code == 200:
                removed_status += 1

    print({'removed_tasks': removed_tasks, 'removed_status': removed_status})


if __name__ == '__main__':
    main()
