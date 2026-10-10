#!/usr/bin/env bash
# Test harness for /app/deploy/update.sh
# Simulates docker + git with fakes; tests SSH-drop survival, double-run guard,
# build-failure path, and git-pull-failure path.
set -u

PASS=0; FAIL=0
report() { if [ "$2" = "0" ]; then echo "PASS: $1"; PASS=$((PASS+1)); else echo "FAIL: $1 ($3)"; FAIL=$((FAIL+1)); fi; }

ROOT=/tmp/update_sh_test
rm -rf "$ROOT"
mkdir -p "$ROOT/deploy" "$ROOT/fakebin"
cp /app/deploy/update.sh "$ROOT/deploy/update.sh"
chmod +x "$ROOT/deploy/update.sh"

# ----- fake binaries -----
cat > "$ROOT/fakebin/docker" <<'EOF'
#!/usr/bin/env bash
echo "[docker $*]" >> "$FAKE_CMD_LOG"
case "$1 $2" in
  "compose stop")
      exit 0 ;;
  "compose build")
      if [ "${FAKE_BUILD_FAIL:-0}" = "1" ]; then sleep 1; exit 1; fi
      sleep "${FAKE_BUILD_SLEEP:-6}"; exit 0 ;;
  "compose up")
      exit 0 ;;
  "compose ps")
      echo "backend  Up"; echo "web  Up"; exit 0 ;;
esac
exit 0
EOF
cat > "$ROOT/fakebin/git" <<'EOF'
#!/usr/bin/env bash
echo "[git $*]" >> "$FAKE_CMD_LOG"
if [ "${FAKE_GIT_FAIL:-0}" = "1" ]; then echo "fatal: fake git failure" >&2; exit 1; fi
exit 0
EOF
chmod +x "$ROOT/fakebin/docker" "$ROOT/fakebin/git"

export PATH="$ROOT/fakebin:/usr/bin:/bin"
export FAKE_CMD_LOG="$ROOT/cmd.log"

cleanup_tails() {
  # kill any leftover tail -f on our log
  pkill -f "tail -n \+1 -f update.log" 2>/dev/null || true
  pkill -f "update.sh --run" 2>/dev/null || true
  sleep 0.3
}

wait_for_done() {
  local log="$1" timeout="${2:-30}" i=0
  while [ $i -lt $timeout ]; do
    if grep -Eq "SELESAI|BUILD GAGAL" "$log" 2>/dev/null; then return 0; fi
    sleep 1; i=$((i+1))
  done
  return 1
}

run_case() {
  local name="$1"
  echo
  echo "=============================================="
  echo "CASE: $name"
  echo "=============================================="
  : > "$FAKE_CMD_LOG"
  rm -f "$ROOT/deploy/update.log"
  cleanup_tails
}

############################################################
# CASE 1: SSH-drop simulation; detached --run must finish OK
############################################################
run_case "1. SSH drop survival + command order + SELESAI"
export FAKE_BUILD_FAIL=0 FAKE_GIT_FAIL=0 FAKE_BUILD_SLEEP=6
# timeout 4 simulates SSH disconnect while fake build is still sleeping.
timeout --preserve-status 4 bash "$ROOT/deploy/update.sh" >/dev/null 2>&1 || true
caller_rc=$?
echo "caller exited (rc=$caller_rc) ~4s in; waiting for detached --run..."

if wait_for_done "$ROOT/deploy/update.log" 30; then
  rc=0
else
  rc=1
fi
report "C1 detached run completed with SELESAI/BUILD GAGAL marker" "$rc" "log never finished"

# check SELESAI present
grep -q "SELESAI" "$ROOT/deploy/update.log" && rc=0 || rc=1
report "C1 log ends with SELESAI" "$rc" "no SELESAI in log"

# check order: git pull -> stop n8n waha -> build backend web -> up -d -> ps
LOG="$ROOT/deploy/update.log"
CMD="$FAKE_CMD_LOG"
echo "---- update.log ----"; cat "$LOG"
echo "---- cmd.log ----";    cat "$CMD"

check_order() {
  local f="$1"; shift
  local prev=-1
  for pat in "$@"; do
    local line
    line=$(grep -n -m1 -F "$pat" "$f" | head -1 | cut -d: -f1)
    if [ -z "$line" ]; then echo "missing: $pat"; return 1; fi
    if [ "$line" -le "$prev" ]; then echo "out of order: $pat (line $line after $prev)"; return 1; fi
    prev=$line
  done
  return 0
}

check_order "$CMD" \
  "[git -C .. pull --ff-only]" \
  "[docker compose stop n8n waha]" \
  "[docker compose build backend web]" \
  "[docker compose up -d]" \
  "[docker compose ps"
rc=$?
report "C1 commands executed in correct order" "$rc" "order wrong"

cleanup_tails

############################################################
# CASE 2: Second invocation while first running => guarded
############################################################
run_case "2. Double-run guard"
export FAKE_BUILD_FAIL=0 FAKE_GIT_FAIL=0 FAKE_BUILD_SLEEP=8
# start first in background, abandon tail
( timeout --preserve-status 2 bash "$ROOT/deploy/update.sh" >/dev/null 2>&1 || true ) &
first_pid=$!
sleep 3  # first caller gone, --run still in build sleep
out=$(bash "$ROOT/deploy/update.sh" 2>&1 | head -5)
echo "second invocation output: $out"
echo "$out" | grep -q "Update masih berjalan" && rc=0 || rc=1
report "C2 second invocation shows 'Update masih berjalan'" "$rc" "guard message missing"

# verify no second --run spawned (should be exactly 1)
nproc=$(pgrep -af "update.sh --run" | wc -l)
[ "$nproc" -le 1 ] && rc=0 || rc=1
report "C2 only one --run process alive (got $nproc)" "$rc" "duplicate --run"

wait $first_pid 2>/dev/null || true
wait_for_done "$ROOT/deploy/update.log" 30 || true
cleanup_tails

############################################################
# CASE 3: Build failure => up -d still runs, BUILD GAGAL, rc=1
############################################################
run_case "3. Build failure path"
export FAKE_BUILD_FAIL=1 FAKE_GIT_FAIL=0 FAKE_BUILD_SLEEP=0
# run detached via wrapper and wait
timeout --preserve-status 3 bash "$ROOT/deploy/update.sh" >/dev/null 2>&1 || true
wait_for_done "$ROOT/deploy/update.log" 30 || true
cleanup_tails

LOG="$ROOT/deploy/update.log"; CMD="$FAKE_CMD_LOG"
echo "---- update.log ----"; cat "$LOG"
echo "---- cmd.log ----";    cat "$CMD"

grep -q "BUILD GAGAL" "$LOG" && rc=0 || rc=1
report "C3 log contains BUILD GAGAL" "$rc" "no BUILD GAGAL marker"

grep -q "\[docker compose up -d\]" "$CMD" && rc=0 || rc=1
report "C3 'docker compose up -d' still executed after failed build" "$rc" "up -d missing"

# Reproduce exit code of --run directly (foreground mode, bypass wrapper)
# by invoking with --run so we can read $?
bash "$ROOT/deploy/update.sh" --run >/dev/null 2>&1
rc=$?
[ "$rc" = "1" ] && pass=0 || pass=1
report "C3 --run exits with code 1 on build failure (got $rc)" "$pass" "exit code wrong"

############################################################
# CASE 4: git pull failure => warn and continue
############################################################
run_case "4. git pull failure -> warn & continue"
export FAKE_BUILD_FAIL=0 FAKE_GIT_FAIL=1 FAKE_BUILD_SLEEP=0
bash "$ROOT/deploy/update.sh" --run > "$ROOT/deploy/update.log" 2>&1
rc=$?
echo "---- update.log ----"; cat "$ROOT/deploy/update.log"
echo "---- cmd.log ----";    cat "$FAKE_CMD_LOG"

[ "$rc" = "0" ] && pass=0 || pass=1
report "C4 --run exits 0 despite git failure (got $rc)" "$pass" "unexpected exit"

grep -q "PERINGATAN" "$ROOT/deploy/update.log" && pass=0 || pass=1
report "C4 warning message printed on git failure" "$pass" "warning missing"

grep -q "\[docker compose build backend web\]" "$FAKE_CMD_LOG" && pass=0 || pass=1
report "C4 build step still ran after git failure" "$pass" "build skipped"

grep -q "SELESAI" "$ROOT/deploy/update.log" && pass=0 || pass=1
report "C4 run completed with SELESAI" "$pass" "no SELESAI"

cleanup_tails

echo
echo "=============================================="
echo "TOTAL: PASS=$PASS FAIL=$FAIL"
echo "=============================================="
[ "$FAIL" = "0" ]
