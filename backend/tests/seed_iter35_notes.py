# Seeds sample project notes (workspace docs) for Notes menu testing
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("PYTEST_CURRENT_TEST", "x")
from test_iter35_notes_menu import login, BASE

s = login("admin")
for pid, title, content, vis in [
    ("project-8", "TEST_Catatan kickoff", "<p>Kickoff <b>agenda</b></p><ul><li>Scope</li><li>Timeline</li></ul>", "Client"),
    ("project-8", "TEST_Catatan teknis", "<p>Stack: React + FastAPI</p>", "Internal"),
    ("project-7", "TEST_Catatan meeting", "<p>Diskusi <b>scope</b> awal</p><ul><li>Login</li></ul>", "Internal"),
]:
    r = s.post(f"{BASE}/api/projects/{pid}/workspace/docs", json={"title": title, "content": content, "visibility": vis})
    print(pid, r.status_code, r.json().get("id"))
