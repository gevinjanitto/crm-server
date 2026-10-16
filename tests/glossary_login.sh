#!/bin/bash
# Usage: source tests/glossary_login.sh <username>  -> exports TOKEN
API=${API:-http://localhost:8001/api}
C=$(curl -s $API/auth/captcha)
CID=$(echo "$C" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
ANS=$(echo "$C" | python3 -c "import sys,json;q=json.load(sys.stdin)['question'].split();print(int(q[0])+int(q[2]))")
TOKEN=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' -d "{\"username\":\"$1\",\"password\":\"$SEED_PASSWORD\",\"captcha_id\":\"$CID\",\"captcha_answer\":\"$ANS\"}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")
export TOKEN
