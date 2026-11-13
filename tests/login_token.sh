#!/usr/bin/env bash
# Test-only: login as admin via math captcha, print token.
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
C=$(curl -s $API/api/auth/captcha)
ID=$(echo "$C" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
ANS=$(echo "$C" | python3 -c "import sys,json;q=json.load(sys.stdin)['question'].split('=')[0];print(eval(q))")
curl -s -X POST $API/api/auth/login -H 'Content-Type: application/json' -d "{\"username\":\"${1:-admin}\",\"password\":\"Maiharta123!\",\"captcha_id\":\"$ID\",\"captcha_answer\":\"$ANS\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('token') or d.get('access_token') or d)"
