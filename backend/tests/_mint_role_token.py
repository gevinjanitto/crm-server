"""Test-only: mint a short-lived session token for an existing demo user (by username). Prints token / deletes session with 'del <sid>'."""
import sys, os, asyncio, jwt
from datetime import datetime, timedelta, timezone
sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')
from core import db, uid  # noqa: E402
from auth import SECRET  # noqa: E402


async def main():
    if sys.argv[1] == 'del':
        await db.sessions.delete_one({'id': sys.argv[2]}); return
    u = await db.users.find_one({'username': sys.argv[1]}, {'_id': 0})
    sid = 'TEST_' + uid()
    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    await db.sessions.insert_one({'id': sid, 'user_id': u['id'], 'expires_at': exp, 'last_activity_at': datetime.now(timezone.utc)})
    print(sid, jwt.encode({'sub': u['id'], 'jti': sid, 'exp': exp}, SECRET, algorithm='HS256'))

asyncio.run(main())
