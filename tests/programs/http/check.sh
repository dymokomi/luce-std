#!/bin/sh
# Prove the HTTP server: build it natively, start it, and drive it with curl.
# Usage: tests/programs/http/check.sh [luce-base binary]
set -eu
cd "$(dirname "$0")/../../.."
mkdir -p build
LB=${1:-../luce-base/build/luce-base}
PORT=18090
"$LB" build tests/programs/http/main.lucb --native -o build/http-check
./build/http-check --port $PORT --root tests/programs/http/www --threads 4 > build/http-check.log 2>&1 &
SERVER=$!
sleep 1
fail() { echo "FAIL: $1"; kill $SERVER 2>/dev/null || true; exit 1; }
[ "$(curl -s -m 5 http://127.0.0.1:$PORT/note.txt)" = "plain text" ] || fail "static file"
[ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/missing)" = "404" ] || fail "missing file"
[ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' --path-as-is http://127.0.0.1:$PORT/../etc/passwd)" = "403" ] || fail "traversal"
[ "$(curl -s -m 5 -X POST --data-binary 'echo me' http://127.0.0.1:$PORT/echo)" = "echo me" ] || fail "echo"
[ "$(curl -s -m 5 http://127.0.0.1:$PORT/note.txt http://127.0.0.1:$PORT/note.txt | wc -l | tr -d ' ')" = "2" ] || fail "keep-alive"
[ "$(curl -s -m 5 -I http://127.0.0.1:$PORT/note.txt | head -1 | tr -d '\r')" = "HTTP/1.1 200 OK" ] || fail "head"
CLIENTS=""
for i in $(seq 1 40); do curl -s -m 5 -o /dev/null http://127.0.0.1:$PORT/ & CLIENTS="$CLIENTS $!"; done
wait $CLIENTS
STATS=$(curl -s -m 5 http://127.0.0.1:$PORT/stats)
COUNT=$(printf '%s' "$STATS" | sed -n 's/.*"requests": \([0-9]*\).*/\1/p')
[ -n "$COUNT" ] && [ "$COUNT" -ge 48 ] || fail "stats: $STATS"
[ "$(curl -s -m 5 http://127.0.0.1:$PORT/quit)" = "bye" ] || fail "quit"
wait $SERVER || fail "exit status"
grep -q "served $((COUNT + 1)) requests" build/http-check.log || fail "count: $(cat build/http-check.log)"
rm -f build/http-check build/http-check.log
echo "ok tests/programs/http"
