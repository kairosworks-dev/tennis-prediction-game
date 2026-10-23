#!/usr/bin/env python3
"""Demo of the alert on user impact (#57): Normal -> Firing -> Normal.

Needs the telemetry stack (`make telemetry-up`) started with the same
RESPONDER_URL and RESPONDER_TOKEN this script sees, because the webhook contact
point is provisioned from them. Python 3 standard library only.

The token is a local shared value, generated per shell session and held in no
file; start the stack, and the responder or this script, from that shell:

    export RESPONDER_TOKEN=$(openssl rand -hex 32)

What it does, in order:
  1. starts a listener on the port of RESPONDER_URL that records every POST,
     answers 401 to one whose `Authorization` is not exactly
     `Bearer <RESPONDER_TOKEN>` (not counted as a delivery), and proves that
     with a request of its own with no token and one with a wrong token;
  2. checks the rule is provisioned and Normal, and that Grafana's contact-point
     test reaches the listener;
  3. signs in as the seeded demo participant and sends the 4xx set to the
     journey's prediction route (401, 404, 422, 403), waits three evaluations,
     and asserts the rule stayed Normal and nothing reached the listener;
  4. stops Postgres, sends exactly one failing PUT (it must answer 5xx), starts
     Postgres again and waits until the app is ready;
  5. polls the rule through Grafana's HTTP API until it is Firing, then Normal
     again, and waits for the firing and the resolved POST;
  6. prints the state transitions with times and the bodies it received.

Postgres is left started, whatever happens.

Settings (environment):
  RESPONDER_URL           default http://host.docker.internal:8001/alerts (as in
                          docker-compose.telemetry.yml); its port is where the
                          listener binds
  RESPONDER_TOKEN         required, non-empty; the bearer token Grafana sends
  LISTEN_HOST             default 127.0.0.1; use 0.0.0.0 on a Linux host
  BASE_URL                default http://127.0.0.1:${APP_PORT:-8000}
  GRAFANA_URL             default http://127.0.0.1:3000
  GRAFANA_ADMIN_PASSWORD  default: the development default of the overlay
  DEMO_EMAIL, DEMO_PASSWORD   the seeded demo participant
  DOCKER                  the docker binary, default docker
"""

import base64
import hmac
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE_UID = "journey-5xx"
CONTACT_POINT_UID = "responder-webhook"
ROUTE = "/api/tournaments/{tournament_id}/questions/{question_id}/prediction"

RESPONDER_URL = os.environ.get("RESPONDER_URL", "http://host.docker.internal:8001/alerts")
RESPONDER_TOKEN = os.environ.get("RESPONDER_TOKEN", "")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "127.0.0.1")
BASE_URL = os.environ.get("BASE_URL", f"http://127.0.0.1:{os.environ.get('APP_PORT', '8000')}")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_ADMIN_PASSWORD", "telemetry-dev-only-not-a-secret")
DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "you@example.com")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "deuce-demo-password")
DOCKER = os.environ.get("DOCKER", "docker")
COMPOSE = [DOCKER, "compose", "-f", "docker-compose.yml", "-f", "docker-compose.telemetry.yml"]

EVALUATION_SECONDS = 10
FIRE_DEADLINE = 90  # seconds after the failing request
NORMAL_DEADLINE = 240  # seconds after the failing request
RESOLVED_DEADLINE = 300  # seconds after the failing request


def now():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def say(text=""):
    print(f"{now()}  {text}", flush=True)


class Failure(Exception):
    pass


def check(condition, text):
    if not condition:
        raise Failure(text)
    say(f"ok    {text}")


# --- the listener ----------------------------------------------------------

received = []  # (time, path, parsed body): deliveries that carried the right token
rejected = []  # times of requests refused with 401
received_lock = threading.Lock()


def authorized(header):
    """The responder's rule: exactly `Bearer <token>`, compared in constant time."""
    expected = f"Bearer {RESPONDER_TOKEN}".encode()
    return hmac.compare_digest((header or "").encode(), expected)


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        if not authorized(self.headers.get("Authorization")):
            with received_lock:
                rejected.append(now())
            self.send_response(401)
            self.end_headers()
            return
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"unparsed": True}
        with received_lock:
            received.append((now(), self.path, body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def start_listener():
    port = urllib.parse.urlparse(RESPONDER_URL).port
    if port is None:
        raise Failure(f"RESPONDER_URL has no port: {RESPONDER_URL}")
    try:
        server = ThreadingHTTPServer((LISTEN_HOST, port), Receiver)
    except OSError as error:
        raise Failure(f"cannot listen on {LISTEN_HOST}:{port} ({error}); is the responder already there?")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    say(f"listener on {LISTEN_HOST}:{port} (RESPONDER_URL={RESPONDER_URL})")
    return server, port


def check_listener_refuses_a_bad_token(port):
    """One self-test: no token and a wrong token get 401 and are not deliveries."""
    url = f"http://127.0.0.1:{port}/alerts"
    for name, headers in (
        ("no token", {}),
        ("a wrong token", {"Authorization": "Bearer " + "0" * len(RESPONDER_TOKEN)}),
    ):
        status, _ = request("POST", url, {"status": "firing", "alerts": []}, headers=headers)
        check(status == 401, f"the listener answers 401 to a request with {name}")
    check(len(posts()) == 0 and len(rejected) == 2, "and counts neither as a delivery")
    with received_lock:
        rejected.clear()


def posts(status=None):
    with received_lock:
        items = list(received)
    if status is None:
        return items
    return [i for i in items if i[2].get("status") == status]


# --- HTTP helpers ----------------------------------------------------------

def request(method, url, body=None, opener=None, headers=None):
    """Return (status, parsed JSON or None). Never raises on an HTTP error status."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=30) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        return status, None


def grafana(method, path, body=None):
    token = base64.b64encode(f"admin:{GRAFANA_PASSWORD}".encode()).decode()
    return request(method, GRAFANA_URL + path, body, headers={"Authorization": f"Basic {token}"})


def app_opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


# --- the rule --------------------------------------------------------------

def rule_state():
    """(overall state, {route: instance state}, health). Overall is one of
    Normal, Pending, Firing, Error."""
    status, data = grafana("GET", "/api/prometheus/grafana/api/v1/rules")
    if status != 200:
        raise Failure(f"Grafana rules API answered {status}")
    for group in data["data"]["groups"]:
        for rule in group["rules"]:
            if rule.get("uid") != RULE_UID:
                continue
            instances = {
                a["labels"].get("http_route", "(no route)"): a["state"] for a in rule.get("alerts", [])
            }
            states = list(instances.values()) + [rule.get("state", "")]
            if rule.get("health") == "error" or any("Error" in s for s in states):
                overall = "Error"
            elif any(s.startswith("Alerting") for s in states) or rule.get("state") == "firing":
                overall = "Firing"
            elif any(s.startswith("Pending") for s in states) or rule.get("state") == "pending":
                overall = "Pending"
            else:
                overall = "Normal"
            return overall, instances, rule.get("health")
    raise Failure(f"rule {RULE_UID} is not loaded in Grafana")


timeline = []  # (time, overall state, instances)


def poll_rule():
    overall, instances, _ = rule_state()
    if not timeline or timeline[-1][1] != overall:
        timeline.append((now(), overall, instances))
        say(f"rule state: {overall}  {instances}")
    return overall


# --- Postgres --------------------------------------------------------------

def compose(*args):
    return subprocess.run(COMPOSE + list(args), cwd=ROOT, capture_output=True, text=True)


def postgres_start_and_wait():
    result = compose("start", "postgres")
    if result.returncode != 0:
        raise Failure(f"could not start Postgres: {result.stderr.strip()}")
    deadline = time.time() + 90
    while time.time() < deadline:
        status, _ = request("GET", BASE_URL + "/ready")
        if status == 200:
            say("Postgres is back, the app answers /ready")
            return
        time.sleep(1)
    raise Failure("the app was not ready 90 s after Postgres was started")


# --- the journey ------------------------------------------------------------

def sign_in(opener):
    status, _ = request(
        "POST", BASE_URL + "/api/auth/login",
        {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, opener,
    )
    check(status == 200, f"sign in as the seeded participant answers 200 (got {status})")


def find_ids(opener):
    _, tournaments = request("GET", BASE_URL + "/api/tournaments", opener=opener)
    tournament = tournaments[0]["tournament"]["id"]
    _, groups = request("GET", f"{BASE_URL}/api/tournaments/{tournament}/bet-groups", opener=opener)
    open_group = next(g["id"] for g in groups if g["status"] == "OPEN")
    closed = next((g["id"] for g in groups if g["status"] != "OPEN"), None)
    _, questions = request(
        "GET", f"{BASE_URL}/api/tournaments/{tournament}/bet-groups/{open_group}/questions", opener=opener
    )
    question = next(q for q in questions if q["answerType"] == "MATCH_RESULT")
    _, draws = request("GET", f"{BASE_URL}/api/tournaments/{tournament}/draws", opener=opener)
    best_of = next(d["bestOf"] for d in draws if d["id"] == question["drawId"])
    closed_question = None
    if closed:
        _, closed_questions = request(
            "GET", f"{BASE_URL}/api/tournaments/{tournament}/bet-groups/{closed}/questions", opener=opener
        )
        closed_question = closed_questions[0]["id"]
    return {
        "tournament": tournament,
        "question": question["id"],
        "winner": question["matchup"][0],
        "score": "3-1" if best_of == 5 else "2-1",
        "closed_question": closed_question,
    }


def prediction_body(ids, question, payload=None):
    return {
        "tournamentId": ids["tournament"],
        "questionId": question,
        "payload": payload
        or {"kind": "GENERIC_MATCH_RESULT", "winnerId": ids["winner"], "setScore": ids["score"]},
        "asDraft": False,
    }


def put_prediction(ids, question, body, opener):
    url = f"{BASE_URL}/api/tournaments/{ids['tournament']}/questions/{question}/prediction"
    return request("PUT", url, body, opener)[0]


def four_xx_set(ids, opener):
    sent = [
        ("401  no session cookie", 401, put_prediction(ids, ids["question"], prediction_body(ids, ids["question"]), app_opener())),
        ("404  unknown question", 404, put_prediction(ids, "no-such-question", prediction_body(ids, "no-such-question"), opener)),
        ("422  invalid payload", 422, put_prediction(ids, ids["question"], {"bad": 1}, opener)),
    ]
    if ids["closed_question"]:
        sent.append((
            "403  question of a closed group",
            403,
            put_prediction(ids, ids["closed_question"], prediction_body(ids, ids["closed_question"]), opener),
        ))
    else:
        raise Failure("the seed data has no closed bet group to produce a 403")
    for name, expected, got in sent:
        check(got == expected, f"PUT prediction, {name}: answered {got}")


# --- the run ------------------------------------------------------------------

def contact_point_test():
    status, points = grafana("GET", "/api/v1/provisioning/contact-points")
    point = next((p for p in points or [] if p.get("uid") == CONTACT_POINT_UID), None)
    check(point is not None, "the webhook contact point is provisioned")
    check(
        point["settings"]["url"] == RESPONDER_URL,
        "the contact point posts to RESPONDER_URL (restart the stack with the same RESPONDER_URL if not)",
    )
    check(
        point["settings"].get("authorization_scheme") == "Bearer",
        "the contact point authorizes with the Bearer scheme",
    )
    name = urllib.parse.quote(base64.urlsafe_b64encode(CONTACT_POINT_UID.encode()).decode().rstrip("="))
    base = "/apis/notifications.alerting.grafana.app/v1beta1/namespaces/default/receivers/"
    status, receiver = grafana("GET", base + name)
    check(status == 200, f"Grafana returns the stored contact point ({status})")
    integration = receiver["spec"]["integrations"][0]
    check(
        integration.get("secureFields", {}).get("authorization_credentials") is True,
        "it holds credentials (RESPONDER_TOKEN was set when the stack started)",
    )
    # The stored integration, secure fields flagged: Grafana fills in the
    # credentials it holds, as its Test button does. The token never passes here.
    status, answer = grafana("POST", base + name + "/test", {"integration": integration})
    check(
        status == 200 and answer.get("status") == "success",
        f"Grafana's contact-point test is accepted ({status}); if not, the stack was probably "
        "started with another RESPONDER_TOKEN than this shell has",
    )
    deadline = time.time() + 15
    while time.time() < deadline and not posts():
        time.sleep(0.5)
    tests = [p for p in posts() if p[2].get("alerts", [{}])[0].get("labels", {}).get("alertname") == "TestAlert"]
    check(len(tests) == 1, "the test notification, with the right token, reached the listener exactly once")
    with received_lock:
        received.clear()


def run():
    _, port = start_listener()
    check_listener_refuses_a_bad_token(port)
    contact_point_test()

    overall = poll_rule()
    check(overall == "Normal", f"the rule is Normal before any traffic from this script (is {overall})")

    opener = app_opener()
    sign_in(opener)
    ids = find_ids(opener)

    say("sending the 4xx set to the journey's prediction route")
    four_xx_set(ids, opener)
    say(f"waiting three evaluations ({3 * EVALUATION_SECONDS + 5} s) to see the rule stay Normal")
    end = time.time() + 3 * EVALUATION_SECONDS + 5
    while time.time() < end:
        check_overall = poll_rule()
        if check_overall != "Normal":
            raise Failure(f"a 4xx moved the rule to {check_overall}")
        time.sleep(2)
    check(len(posts()) == 0 and not rejected, "4xx never fires it: no notification reached the listener")

    say("stopping Postgres")
    stopped = compose("stop", "postgres")
    if stopped.returncode != 0:
        raise Failure(f"could not stop Postgres: {stopped.stderr.strip()}")
    t5xx = time.time()
    started = time.time()
    failing = put_prediction(ids, ids["question"], prediction_body(ids, ids["question"]), opener)
    elapsed = time.time() - started
    say(f"the one failing PUT answered {failing} in {elapsed * 1000:.0f} ms")
    check(500 <= failing < 600, "the request with the database stopped answers a 5xx")
    check(elapsed < 5, "it fails fast (under 5 s), it does not hang")
    postgres_start_and_wait()

    say("polling the rule")
    fired_at = resolved_at = None
    while time.time() - t5xx < RESOLVED_DEADLINE:
        overall = poll_rule()
        if overall == "Firing" and fired_at is None:
            fired_at = time.time()
        if overall == "Normal" and fired_at is not None and resolved_at is None:
            resolved_at = time.time()
        if resolved_at and posts("resolved"):
            break
        if fired_at is None and time.time() - t5xx > FIRE_DEADLINE:
            raise Failure(f"not Firing {FIRE_DEADLINE} s after the failing request")
        time.sleep(2)

    check(fired_at is not None, f"Firing {fired_at - t5xx:.0f} s after the failing request" if fired_at else "Firing")
    check(fired_at - t5xx <= FIRE_DEADLINE, f"within {FIRE_DEADLINE} s")
    check(resolved_at is not None, "back to Normal" + (f" {resolved_at - t5xx:.0f} s after the failing request" if resolved_at else ""))
    check(resolved_at - t5xx <= NORMAL_DEADLINE, f"within {NORMAL_DEADLINE} s of the 5xx")

    firing, resolved = posts("firing"), posts("resolved")
    check(len(firing) == 1, f"exactly one firing notification (got {len(firing)})")
    check(len(resolved) == 1, f"exactly one resolved notification (got {len(resolved)})")
    check(not rejected, "no request was refused for a wrong or missing token")
    check_notification(firing[0][2])
    return firing[0], resolved[0]


def check_notification(body):
    alert = body["alerts"][0]
    labels, annotations = alert["labels"], alert["annotations"]
    expected = {
        "journey": "place-a-prediction",
        "service": "tennis-prediction-game",
        "kind": "http-5xx",
        "severity": "page",
        "http_route": ROUTE,
    }
    check(all(labels.get(k) == v for k, v in expected.items()), "the labels name the journey, the kind and the route template")
    check(annotations.get("window") == "2m", "the window (2m) is an annotation")
    check("docs/alerting.md#runbook" in annotations.get("runbook_url", ""), "runbook_url points at the Runbook section")
    check("place-a-prediction" in alert.get("dashboardURL", ""), "dashboardURL names the dashboard")
    check("viewPanel=3" in alert.get("panelURL", ""), "panelURL names panel 3")
    for key in ("dashboardURL", "panelURL"):
        url = alert[key]
        token = base64.b64encode(f"admin:{GRAFANA_PASSWORD}".encode()).decode()
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
        with urllib.request.urlopen(req, timeout=30) as response:
            check(response.status == 200, f"{key} opens ({url})")


def main():
    if not RESPONDER_TOKEN:
        print(
            "RESPONDER_TOKEN is not set. The webhook sends it as a bearer token and this\n"
            "listener checks it. Generate one for this shell, then start the stack and run\n"
            "the demo from the same shell:\n\n"
            "    export RESPONDER_TOKEN=$(openssl rand -hex 32)\n",
            file=sys.stderr,
        )
        sys.exit(2)
    exit_code = 0
    results = None
    try:
        results = run()
    except Failure as failure:
        say(f"FAIL  {failure}")
        exit_code = 1
    except Exception as error:  # a broken demo must still restore Postgres
        say(f"FAIL  unexpected {type(error).__name__}: {error}")
        exit_code = 1
    finally:
        started = compose("start", "postgres")  # no-op when it is running
        if started.returncode != 0:
            say(f"WARNING could not start Postgres: {started.stderr.strip()}")
            exit_code = 1

    print()
    print("State transitions of the rule")
    for when, state, instances in timeline:
        print(f"  {when}  {state}  {instances}")
    print("  " + " -> ".join(state for _, state, _ in timeline))
    if results:
        for label, item in zip(("firing", "resolved"), results):
            when, path, body = item
            print()
            print(f"Received at {when}, POST {path} ({label})")
            print(json.dumps(body, indent=2))
    if exit_code == 0:
        print("\nDemo passed. Postgres is started.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
