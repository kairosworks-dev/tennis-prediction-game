"""make demo-trigger: send the demo's failing request N times and print each status.

Signs in as the public demo participant, finds the open bet group's first
match-result question, and submits a legal result with the second player of
the tie as the winner, N times. With the demo fault in place every answer is
500; after the fix every answer is 200. Same command both times.

  BASE_URL       default http://127.0.0.1:${APP_PORT:-8000}
  N              how many times to send it, default 5
  DEMO_EMAIL     default you@example.com (the seeded demo participant)
  DEMO_PASSWORD  default deuce-demo-password (the seeded demo password)
  WAIT           if set, pause after signing in, before the first request (to stop
                 Postgres for the escalation run: signing in needs the database)

Standard library only. Exits 0 when every request got an answer (whatever its
status), 1 when the app did not answer or the sign-in failed.
"""

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL") or f"http://127.0.0.1:{os.environ.get('APP_PORT') or '8000'}"
COUNT = int(os.environ.get("N") or "5")
EMAIL = os.environ.get("DEMO_EMAIL") or "you@example.com"
SECRET = os.environ.get("DEMO_PASSWORD") or "deuce-demo-password"

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE_URL + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with opener.open(request, timeout=15) as response:
            return response.status, response.headers.get("X-Trace-Id"), json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("X-Trace-Id"), None


def main():
    try:
        status, _, _ = call("POST", "/api/auth/login", {"email": EMAIL, "password": SECRET})
    except (urllib.error.URLError, OSError) as error:
        print(f"demo-trigger: no answer from {BASE_URL}: {error}", file=sys.stderr)
        return 1
    if status != 200:
        print(f"demo-trigger: sign-in answered {status}", file=sys.stderr)
        return 1

    _, _, games = call("GET", "/api/tournaments")
    tournament = games[0]["tournament"]["id"]
    _, _, groups = call("GET", f"/api/tournaments/{tournament}/bet-groups")
    group = next(g["id"] for g in groups if g["status"] == "OPEN")
    _, _, questions = call("GET", f"/api/tournaments/{tournament}/bet-groups/{group}/questions")
    question = next(q for q in questions if q["answerType"] == "MATCH_RESULT" and q.get("matchup"))
    _, _, draws = call("GET", f"/api/tournaments/{tournament}/draws")
    best_of = next(d["bestOf"] for d in draws if d["id"] == question["drawId"])
    body = {
        "tournamentId": tournament,
        "questionId": question["id"],
        "payload": {
            "kind": "GENERIC_MATCH_RESULT",
            "winnerId": question["matchup"][1],
            "setScore": "3-1" if best_of == 5 else "2-1",
        },
        "asDraft": False,
    }
    path = f"/api/tournaments/{tournament}/questions/{question['id']}/prediction"
    if os.environ.get("WAIT"):
        input("Signed in. Do what the demo step says (for example stop Postgres), then press Enter: ")
    print(f"PUT {path}  (winner: the second player of the tie), {COUNT} time(s) against {BASE_URL}")
    for number in range(1, COUNT + 1):
        try:
            status, trace_id, _ = call("PUT", path, body)
        except (urllib.error.URLError, OSError) as error:
            print(f"  {number}: no answer ({error})")
            return 1
        print(f"  {number}: {status}  trace_id={trace_id or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
