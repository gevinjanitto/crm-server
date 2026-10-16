import os
from dotenv import dotenv_values
from pymongo import MongoClient


frontend_env = dotenv_values("/app/frontend/.env")
backend_env = dotenv_values("/app/backend/.env")

mongo_url = os.environ.get("MONGO_URL") or backend_env.get("MONGO_URL", "")
db_name = os.environ.get("DB_NAME") or backend_env.get("DB_NAME", "")

if not mongo_url or not db_name:
    raise SystemExit("Missing MONGO_URL/DB_NAME")

client = MongoClient(mongo_url)
db = client[db_name]

try:
    users = list(
        db.users.find(
            {
                "$or": [
                    {"username": {"$regex": r"^test_dependency_ui_", "$options": "i"}},
                    {"name": {"$regex": r"^TEST_DEPENDENCY_UI_", "$options": "i"}},
                ]
            },
            {"_id": 0, "id": 1, "username": 1, "client_id": 1},
        )
    )
    user_ids = [u["id"] for u in users if u.get("id")]
    client_ids_from_users = [u.get("client_id") for u in users if u.get("client_id")]

    clients = list(
        db.clients.find(
            {
                "$or": [
                    {"name": {"$regex": r"^TEST_DEPENDENCY_UI_", "$options": "i"}},
                    {"contact": {"$regex": r"^TEST_DEPENDENCY_UI_", "$options": "i"}},
                    {"email": {"$regex": r"^test_dependency_ui_", "$options": "i"}},
                ]
            },
            {"_id": 0, "id": 1},
        )
    )
    client_ids = list({c.get("id") for c in clients if c.get("id")} | set(client_ids_from_users))

    if user_ids:
        db.sessions.delete_many({"user_id": {"$in": user_ids}})
        db.notifications.delete_many({"user_id": {"$in": user_ids}})
        db.activity_logs.delete_many({"user_id": {"$in": user_ids}})
        db.audit_logs.delete_many({"user_id": {"$in": user_ids}})
        db.users.delete_many({"id": {"$in": user_ids}})

    if client_ids:
        db.projects.delete_many({"client_id": {"$in": client_ids}})
        db.clients.delete_many({"id": {"$in": client_ids}})

    db.notifications.delete_many({"message": {"$regex": r"TEST_DEPENDENCY_UI_", "$options": "i"}})
    print({"deleted_user_ids": user_ids, "deleted_client_ids": client_ids})
finally:
    client.close()
