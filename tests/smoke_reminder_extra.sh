set -e
API=${API:-http://localhost:8001}
C=$(curl -s $API/api/auth/captcha)
CID=$(echo $C | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
ANS=$(echo $C | python3 -c "import sys,json,re;q=json.load(sys.stdin)['question'];a,o,b=re.match(r'\s*(\d+)\s*([+\-*])\s*(\d+)',q).groups();a,b=int(a),int(b);print({'+':a+b,'-':a-b,'*':a*b}[o])")
R=$(curl -s -X POST $API/api/auth/login -H 'Content-Type: application/json' -d "{\"username\":\"admin\",\"password\":\"Maiharta123!\",\"captcha_id\":\"$CID\",\"captcha_answer\":\"$ANS\"}")
echo "LOGIN: $(echo $R | head -c 200)"
T=$(echo $R | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $T"
PID=$(curl -s $API/api/projects -H "$H" | python3 -c "import sys,json;d=json.load(sys.stdin);d=d.get('items',d) if isinstance(d,dict) else d;print(d[0]['id'])")
echo PID=$PID
END=$(date -d "+20 days" +%F)
RR=$(curl -s -X POST $API/api/projects/$PID/reminders -H "$H" -H 'Content-Type: application/json' -d "{\"name\":\"Domain\",\"description\":\"Perpanjang domain\",\"start_date\":\"$(date +%F)\",\"end_date\":\"$END\",\"extra_notify\":true,\"extra_notify_days\":3}")
echo "CREATE: $RR"
RID=$(echo $RR | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo hello > /tmp/a.pdf
echo "UPLOAD: $(curl -s -X POST $API/api/projects/$PID/reminders/$RID/attachments -H "$H" -F files=@/tmp/a.pdf | head -c 600)"
echo "BAD14: $(curl -s -X POST $API/api/projects/$PID/reminders -H "$H" -H 'Content-Type: application/json' -d "{\"name\":\"X\",\"start_date\":\"$(date +%F)\",\"end_date\":\"$END\",\"extra_notify\":true,\"extra_notify_days\":14}")"
echo "PATCH10: $(curl -s -X PATCH $API/api/projects/$PID/reminders/$RID -H "$H" -H 'Content-Type: application/json' -d "{\"end_date\":\"$(date -d '+10 days' +%F)\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['notified_at'],d['extra_notified_at'])")"
echo "PATCH2: $(curl -s -X PATCH $API/api/projects/$PID/reminders/$RID -H "$H" -H 'Content-Type: application/json' -d "{\"end_date\":\"$(date -d '+2 days' +%F)\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['notified_at'],d['extra_notified_at'])")"
curl -s "$API/api/notifications" -H "$H" | python3 -c "import sys,json;d=json.load(sys.stdin);d=d.get('items',d) if isinstance(d,dict) else d;[print('NOTIF:',n.get('title')) for n in d[:5]]"
AID=$(curl -s $API/api/projects/$PID/reminders -H "$H" | python3 -c "import sys,json;r=[x for x in json.load(sys.stdin) if x['id']=='$RID'][0];print(r['attachments'][0]['id'])")
echo "DOWNLOAD: $(curl -s $API/api/projects/$PID/reminders/$RID/attachments/$AID -H "$H")"
echo "DEL: $(curl -s -X DELETE $API/api/projects/$PID/reminders/$RID/attachments/$AID -H "$H" | python3 -c "import sys,json;print(len(json.load(sys.stdin)['attachments']))")"
