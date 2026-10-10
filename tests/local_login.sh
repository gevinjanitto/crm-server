#!/bin/bash
# Usage: source /app/tests/local_login.sh; TOKEN=$(login admin)
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)/api
login() { C=$(curl -s $API/auth/captcha); CID=$(echo $C | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])"); ANS=$(echo $C | python3 -c "import sys,json;q=json.load(sys.stdin)['question'].split();print(int(q[0])+int(q[2]))"); curl -s -X POST $API/auth/login -H 'Content-Type: application/json' -d "{\"username\":\"$1\",\"password\":\"${2:-Tes12345}\",\"captcha_id\":\"$CID\",\"captcha_answer\":\"$ANS\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])"; }
