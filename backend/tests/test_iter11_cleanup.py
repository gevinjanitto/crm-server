"""Cleanup temporary Iter11 test data created during regression runs."""

import os

from dotenv import dotenv_values
from pymongo import MongoClient


ENV_VALUES = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or ENV_VALUES.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or ENV_VALUES.get("DB_NAME")


def test_cleanup_iter11_temp_records():
    if not (MONGO_URL and DB_NAME):
        return

    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    try:
        projects = list(
            db.projects.find(
                {"name": {"$regex": r"^(TEST_WF_|TEST_I11_)"}},
                {"_id": 0, "id": 1},
            )
        )
        pids = [p["id"] for p in projects if p.get("id")]

        for pid in pids:
            db.projects.delete_one({"id": pid})
            for col in [
                "project_status_logs",
                "project_features",
                "project_documents",
                "revisions",
                "maintenances",
                "deployments",
                "tickets",
                "tasks",
                "expenses",
                "task_comments",
                "workspace_docs",
                "doc_versions",
                "workspace_boards",
                "workspace_nodes",
                "workspace_fields",
                "workspace_sprints",
                "workspace_goals",
                "workspace_capacities",
                "workspace_automations",
                "saved_views",
                "notifications",
                "activity_logs",
                "audit_logs",
            ]:
                db[col].delete_many({"project_id": pid})
            db.trash.delete_many({"project_id": pid})

        db.clients.delete_many({"name": {"$regex": r"^(TEST_WF_Client_|TEST_I11_Client_)"}})
        assert True
    finally:
        mongo.close()
