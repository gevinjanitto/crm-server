@echo off
cd /d "%~dp0"
start "CRM Backend" cmd /k "cd backend && .venv\Scripts\python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload"
cd frontend && yarn start
