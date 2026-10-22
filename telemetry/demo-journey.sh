#!/usr/bin/env bash
# Drives the journey of #56 against a running stack, with curl:
#   two client errors (a sign-in with a wrong password, which the contract
#   answers 422, and a request without a session, 401), then sign in, list games, open one, list its bet
#   groups and the questions of an open group, and place a prediction.
# Ids come from the API, not from this file. Exits non-zero if any step answers
# an unexpected status. Prints each step with the X-Trace-Id of its response.
#
#   BASE_URL       default http://127.0.0.1:${APP_PORT:-8000}
#   DEMO_EMAIL     default you@example.com (the seeded demo participant)
#   DEMO_PASSWORD  default deuce-demo-password (the seeded demo password)
#   REPEAT         how many times to run the journey, default 1
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:${APP_PORT:-8000}}"
DEMO_EMAIL="${DEMO_EMAIL:-you@example.com}"
DEMO_PASSWORD="${DEMO_PASSWORD:-deuce-demo-password}"
REPEAT="${REPEAT:-1}"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
jar="$work/cookies"

# step NAME EXPECTED_STATUS curl-args...  -> body in $work/body, trace id in $trace_id
step() {
  local name="$1" expected="$2"
  shift 2
  local status
  status="$(curl -sS -o "$work/body" -D "$work/headers" -w '%{http_code}' \
    -b "$jar" -c "$jar" "$@")" || { echo "FAIL  $name: no answer from $BASE_URL" >&2; exit 1; }
  trace_id="$(awk 'tolower($1) == "x-trace-id:" { gsub(/\r/, "", $2); print $2 }' "$work/headers")"
  printf '%-34s %s  trace_id=%s\n' "$name" "$status" "${trace_id:-none}"
  if [ "$status" != "$expected" ]; then
    echo "FAIL  $name: expected $expected, got $status" >&2
    cat "$work/body" >&2
    exit 1
  fi
}

# json PYTHON_EXPRESSION  -> evaluates against the last body, as `d`
json() {
  python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' \
    "$work/body" "$1"
}

journey() {
  : > "$jar"
  step "(401) tournaments, not signed in" 401 "$BASE_URL/api/tournaments"
  step "(422) sign in, wrong password" 422 -X POST "$BASE_URL/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\": \"$DEMO_EMAIL\", \"password\": \"not-the-password\"}"

  step "1 POST /api/auth/login" 200 -X POST "$BASE_URL/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\": \"$DEMO_EMAIL\", \"password\": \"$DEMO_PASSWORD\"}"

  step "2 GET tournaments" 200 "$BASE_URL/api/tournaments"
  local tournament
  tournament="$(json 'd[0]["tournament"]["id"]')"

  step "3 GET tournament" 200 "$BASE_URL/api/tournaments/$tournament"

  step "4 GET bet-groups" 200 "$BASE_URL/api/tournaments/$tournament/bet-groups"
  local group
  group="$(json 'next(g["id"] for g in d if g["status"] == "OPEN")')"

  step "5 GET questions" 200 "$BASE_URL/api/tournaments/$tournament/bet-groups/$group/questions"
  local question winner draw
  question="$(json 'next(q["id"] for q in d if q["answerType"] == "MATCH_RESULT")')"
  winner="$(json 'next(q["matchup"][0] for q in d if q["answerType"] == "MATCH_RESULT")')"
  draw="$(json 'next(q["drawId"] for q in d if q["answerType"] == "MATCH_RESULT")')"

  # The set score a legal result needs depends on the draw's best-of.
  step "(draws, for the best-of)" 200 "$BASE_URL/api/tournaments/$tournament/draws"
  local score
  score="$(DRAW="$draw" json '"3-1" if next(x["bestOf"] for x in d if x["id"] == __import__("os").environ["DRAW"]) == 5 else "2-1"')"

  step "6 PUT prediction" 200 -X PUT \
    "$BASE_URL/api/tournaments/$tournament/questions/$question/prediction" \
    -H 'Content-Type: application/json' \
    -d "{\"tournamentId\": \"$tournament\", \"questionId\": \"$question\", \"payload\": {\"kind\": \"GENERIC_MATCH_RESULT\", \"winnerId\": \"$winner\", \"setScore\": \"$score\"}, \"asDraft\": false}"
  echo "prediction trace_id: $trace_id"
}

for _ in $(seq 1 "$REPEAT"); do
  journey
done
echo "journey complete against $BASE_URL"
