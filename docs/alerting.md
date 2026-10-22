# Alerting on user impact

One Grafana alert rule, provisioned as code, goes **Firing** when participants
get server errors (5xx) on the key journey and **Normal** again when they
stop. It alerts on what a user experienced, not on CPU or memory, and it
notifies a webhook, which is where the on-call responder (#58) listens.
Decisions: D20 (local demo only, on the author's machine) and D21 (built by
agents, the author reviewing). It sits on the telemetry stack of
[`observability.md`](observability.md) (#56) and is as optional as that stack:
`docker compose up`, `make run`, `make check` and CI never start it.

It is distinct from #8, the by-hand uptime check on the deployed app.

## What the rule measures, and why

Files, all under `telemetry/grafana/provisioning/alerting/` and loaded when
Grafana starts (nothing is created in the UI):

| File | Holds |
|---|---|
| `rules.yaml` | the rule group and the rule |
| `contact-points.yaml` | the webhook contact point |
| `policies.yaml` | the notification policy |

**What counts.** Any response with a status of `5xx` (500 to 599) on one of the
six routes of the journey (the list in `observability.md`, *The journey*). A 4xx
is a correct answer to a bad request and never counts: 401 (no session), 403
(group closed, or not joined), 404, 409 and 422. Filtering is on the status
code, not on the exception type. `/health`, `/ready` and the static frontend
are not observed at all. A 5xx on any other `/api/` route (for example
`.../draws`) is on the dashboard but not in this alert.

**Threshold: any, not a rate.** The game has tens of participants, so traffic
is sparse and a percentage means nothing (one error in three requests is 33 %,
one in a thousand is 0.1 %, and both are an incident for the person who got
it). The condition is: the number of 5xx responses in the window is above 0.

**One instance per route.** The query is `sum by (http_route)`, so each affected
route is its own alert instance and `{{ $labels.http_route }}` names it. The
label is the route **template** the code uses, for example
`/api/tournaments/{tournament_id}/questions/{question_id}/prediction`
(not the contract's `{questionId}`, and never the raw path), so ids do not
multiply instances and none reaches the alert. The label is `http_route` in
Prometheus.

**The route selector is written once in each file, by the same expression:**
one regex of the six templates, in `rules.yaml` (query A) and as an extra
matcher in the query of panel 3, *Errors by route and status*, of
`telemetry/grafana/dashboards/place-a-prediction.json`, so the graph and the
alert agree. `{` and `}` need no escaping in Prometheus' regex. The dashboard
link in the notification opens that panel (`__dashboardUid__: place-a-prediction`,
`__panelId__: "3"`).
`backend/tests/test_alerting.py` keeps the two regexes equal, equal to the
six routes of `observability.md`, and equal to templates that exist in the app.

The values, all visible in `rules.yaml` and `policies.yaml`:

| | Value | Why |
|---|---|---|
| Query | `sum by (http_route) (increase(http_server_request_duration_seconds_count{http_route=~"<six routes>", http_response_status_code=~"5.."}[2m]))` | 5xx per route over the window |
| Window | `2m` | long enough to hold several metric exports (5 s), short enough that the alert returns to Normal about two minutes after the last error, so a demo fits in a few minutes. Five minutes is the usual production choice; it is one token, `[2m]`, and the `window` annotation |
| Evaluation interval | `10s` (the rule group's `interval`) | Grafana's smallest |
| Pending period | `for: 0s` | one evaluation that sees a 5xx fires; no *Pending* stop |
| Condition | threshold `> 0` on the reduced query | "any" |
| No data | `noDataState: OK` | a quiet period is normal, see below |
| Query error | `execErrState: Error` | an unreachable Prometheus must not look healthy |
| Group wait | `group_wait: 0s` | the default 30 s would delay the first webhook |
| Group interval | `group_interval: 1m` | |
| Repeat interval | `repeat_interval: 12h` | a still-firing alert must not start a second responder run while the first is working |
| Grouping | `group_by: [alertname, http_route]` | one notification per route |

The metric is pushed over OTLP: the app exports every 5 s to the Collector,
which pushes to Prometheus' OTLP receiver. There is no scrape.

### The first 5xx on a brand-new series

A counter series that does not exist until its first error has a single sample
(1) at first, so `increase()` has nothing to subtract and reads 0: a first 5xx
on a route that never had one would not fire. The author's decision (17 Oct)
was to try Prometheus' created-timestamp zero injection with a plain
`increase()` first, and to fall back to "count now minus count two minutes ago"
only if that did not work.

**It works over OTLP on Prometheus v3.15.0.** Observed on this stack, one 500
on a route and instance with no earlier 5xx, the same query in both runs:

| Prometheus | Samples of the new 5xx series | `increase(...[2m])` |
|---|---|---|
| without the flag (before this issue) | `1, 1, 1, ...` | `0` |
| with `--enable-feature=created-timestamp-zero-ingestion` | `0, 1, 1, 1, ...` | `1.16` |

With the flag Prometheus stores a 0 sample at the start time the OTLP data
point carries (the SDK sets it to when that label set was first recorded; it
sat 1.7 s before the first real sample). The feature's documentation talks of
scrapes, so this was found by trying, not read. The only change to the
telemetry stack is that one flag on the `prometheus` service in
`docker-compose.telemetry.yml`; `backend/tests/test_alerting.py` fails if it is
removed. The demo below proves it with exactly one failing request on a route
and series that had never had a 5xx, on a stack started from empty volumes.

Two consequences, both visible in the recorded run:

- `increase()` extrapolates, so one request reads between about 1 and 2 (2.08
  in the recorded run). The description therefore says "about N". The rule
  fires on any value above 0 and the count is for orientation only; Loki has
  the exact requests.
- The 0 leaves the window two minutes after the 5xx, so the instance resolves
  about two minutes after the last 5xx (125 s in the recorded run).

If the flag stops working (a Prometheus upgrade that changes it), the fallback
is an expression that does not depend on it, for example
`sum by (http_route) (X - (X offset 2m or X * 0))` with `X` the selector above.
It was **not** needed and has not been run.

### No data is normal; an unreachable datasource is not

On a stack with no 5xx series at all (including one with no traffic), the query
returns nothing. `noDataState: OK` makes that Normal. Grafana lists the instance
as `Normal (NoData)`, the rule's state is Normal and its health is `ok`; it is
not *No data* and not *Error*. (An `or vector(0)` would give a plain `Normal`
but adds an instance with no route; it was left out.)

`execErrState: Error` means that when Prometheus cannot be queried the rule
shows **Error**, never Normal. Grafana then also sends an alert named
**`DatasourceError`** through the same notification policy, so it reaches the
same webhook, with the rule's labels (`severity=page`, `journey=...`), no
`http_route`, an `Error` annotation holding the query error, and a summary that
says the alert could not be evaluated. Seen once, below. The responder must not
treat it as an application incident; see the Runbook.

## The notification

Labels on the rule: `journey=place-a-prediction`, `service=tennis-prediction-game`,
`kind=http-5xx`, `severity=page`; Grafana adds `alertname`, `grafana_folder` and
`http_route`. Annotations: `summary`, `description` (the endpoint, the status
class, the window and the count), `window: 2m`, `runbook_url` (the *Runbook*
section below, on `main` at GitHub). Because of `__dashboardUid__` and
`__panelId__`, the webhook body carries `dashboardURL` and `panelURL`, built
from `GF_SERVER_ROOT_URL` (`http://localhost:3000`), so they open from outside
the container.

The contact point is a `webhook`, `POST`, to `${RESPONDER_URL}`, with resolve
messages on. `RESPONDER_URL` is read from the environment by Grafana's
provisioning (the overlay passes it on, default
`http://host.docker.internal:8001/alerts`, where the responder of #58 listens on
the host). Change the variable and restart Grafana; no file changes. The Grafana
service has `extra_hosts: ["host.docker.internal:host-gateway"]` so the name also
resolves on Linux. No credentials or tokens are involved.

Grafana's **Test** button on the contact point posts a `TestAlert` to that URL.
The demo does the same through the HTTP API (Grafana 13 moved it to
`POST /apis/notifications.alerting.grafana.app/v1beta1/namespaces/default/receivers/<name>/test`).

## Run the demo

```bash
RESPONDER_URL=http://host.docker.internal:8001/alerts make telemetry-up   # the default; any port will do
make telemetry-alert-demo
make telemetry-down
```

`make telemetry-alert-demo` (`telemetry/alert-demo.py`, Python 3 standard
library only, optional like the stack) needs the stack started with the same
`RESPONDER_URL` it sees, because Grafana reads it at start. The script starts a
listener on that URL's port (a stand-in for the responder; stop the responder of
#58 first if it uses the same port), and then:

1. checks the contact point is provisioned and points at `RESPONDER_URL`, and
   that Grafana's test delivery reaches the listener exactly once;
2. checks the rule is Normal, signs in as the seeded participant
   (`you@example.com`), and sends the 4xx set to the journey's prediction route:
   **401** (no session cookie), **404** (unknown question), **422** (invalid
   payload) and **403** (a question of a settled bet group; the seed data has
   one, so no extra user is needed);
3. waits three evaluations (35 s) and asserts the rule stayed Normal and
   nothing reached the listener;
4. stops Postgres, sends **exactly one** valid `PUT` (it must answer 5xx, and
   within 5 s: the stopped container's name no longer resolves, so it fails at once and does not hang),
   starts Postgres again and waits until `/ready` answers;
5. polls Grafana's API every 2 s until the rule is Firing (within 90 s of the
   request) and Normal again (within 240 s), and waits for the `resolved` POST;
6. asserts exactly one `firing` and one `resolved` request, checks the labels,
   the `window`, the `runbook_url`, and opens `dashboardURL` and `panelURL`;
7. prints `Normal -> Firing -> Normal` with times and the bodies.

Postgres is started again however the script ends. It takes about three
minutes. Settings, all optional: `RESPONDER_URL`, `LISTEN_HOST` (default
`127.0.0.1`; a Linux host needs `0.0.0.0` so the container can reach it),
`BASE_URL` (default `http://127.0.0.1:${APP_PORT:-8000}`), `GRAFANA_URL`,
`GRAFANA_ADMIN_PASSWORD`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `DOCKER`.

Notes from running it:

- The 5xx here is a real unhandled exception from a stopped database; nothing
  in the application, no flag, no route, makes it, and no code changed.
- Grafana applies `GF_SECURITY_ADMIN_PASSWORD` only when its volume is first
  created. If a stack was first started with another `GRAFANA_ADMIN_PASSWORD`,
  the script (and the API calls above) get a 401: `make telemetry-reset`
  starts Grafana again from nothing.
- A Grafana restarted with a new `RESPONDER_URL` needs no reset;
  `docker compose ... up -d grafana` is enough.

## Runbook

For whoever, or whatever, receives the notification (the on-call responder of
#58, or a person following the `runbook_url`).

### What the alert means

At least one request on the key journey was answered with a server error in the
last 2 minutes. The `http_route` label is the endpoint, as a route template.
The journey is: sign in (`POST /api/auth/login`), list games, open one, list
its bet groups, list the questions of a group, place a prediction (`PUT
.../questions/{question_id}/prediction`). A participant got an error page or a
failed save. It resolves by itself two minutes after the last 5xx, and one
firing notification is sent per route; no second one comes for the same
incident within 12 hours.

### First: is it an application incident?

Look at `alertname` and the labels.

| What arrives | Meaning | Do |
|---|---|---|
| `alertname` is the rule's title, `http_route` is set, `severity=page` | participants are getting 5xx on that route | the steps below |
| `alertname=DatasourceError` (no `http_route`; an `Error` annotation names the failing query) | Grafana could not query Prometheus; **no statement about the application is possible** | not an application incident; check Prometheus (`http://localhost:9090/-/ready`, `docker compose ... ps prometheus`) and start it; the rule recovers within a minute |
| `alertname=DatasourceNoData` | not produced: `noDataState` is `OK` | - |
| `alertname=TestAlert` (labels `alertname` and `instance=Grafana`, annotation "Notification test") | someone pressed *Test* | ignore |
| `status: resolved` | the instance went back to Normal | nothing to fix |

### Where to look, in this order

1. **The dashboard**: open `panelURL` or `dashboardURL` (the dashboard
   *Place a prediction*, panel *Errors by route and status*). It shows the
   route and the 5xx status code, and, in *Requests per minute by route*, when
   it started. Set the `Route` and `Status` variables to the alert's route and
   `500`.
2. **The log lines (Loki)** for that route and status. In Grafana (Explore,
   Loki) or by the API:

   ```logql
   {service_name="tennis-prediction-game"} |= "request completed" | http_route="<the route>" | http_response_status_code=~"5.."
   ```

   Each line has the `trace_id` of the request. A request that ended in an
   unhandled exception also has one ERROR record with the same `trace_id`:

   ```logql
   {service_name="tennis-prediction-game"} |= "unhandled exception"
   ```

   Its `exception_type` (for example `OperationalError`, the type only, never the
   message or the stack) says what broke. The API's own container output
   (`docker compose ... logs app`) holds the traceback for it; it is not collected
   as telemetry.
3. **The trace (Tempo)**: open the `trace_id` from either record (the log line's
   **Open trace in Tempo** link). The server span is named `<METHOD> <route>`,
   has status `Error`, `http.response.status_code=500` and an `exception` event.
   To find 5xx traces without a log line: TraceQL `{ span.http.response.status_code >= 500 }`.
4. **`X-Trace-Id`** is the header that carries the trace ID on a normal response
   (`curl -i`), but it is **absent on an unhandled 500**, whose response is built
   outside the app's middleware. Find the request by route and status 500 in
   Loki, as in step 2, not from a header.

### Usual causes on this stack

- All routes, or login, 500 together and `exception_type` is `OperationalError`:
  the database is down or unreachable. `docker compose ... ps postgres`; start
  it. This is exactly what the demo does.
- One route only, a different `exception_type`: a code defect on that route;
  the trace and the `exception_type` point at it. Reproduce with the request
  that the log line names (method and route; no bodies or ids are logged).
- After the cause is fixed, the alert resolves by itself two minutes after the
  last 5xx. Do not silence it to make it go away.

## One recorded run

22 Oct 2026, a stack started from empty telemetry volumes (so no earlier 5xx
series), the stand-in receiver on port 18001
(`RESPONDER_URL=http://host.docker.internal:18001/alerts`), the app on port 18080.
Times are UTC. `make telemetry-alert-demo`, console output unedited except that
the long `message`, `silenceURL`, `valueString`, `commonLabels` and
`commonAnnotations` fields of the two bodies are left out (they repeat the rest):

```text
17:43:59  listener on 127.0.0.1:18001 (RESPONDER_URL=http://host.docker.internal:18001/alerts)
17:43:59  ok    the webhook contact point is provisioned
17:43:59  ok    the contact point posts to RESPONDER_URL (restart the stack with the same RESPONDER_URL if not)
17:43:59  ok    Grafana's contact-point test is accepted (200)
17:43:59  ok    the test notification reached the listener exactly once
17:43:59  rule state: Normal  {'(no route)': 'Normal (NoData)'}
17:43:59  ok    the rule is Normal before any traffic from this script (is Normal)
17:43:59  ok    sign in as the seeded participant answers 200 (got 200)
17:43:59  sending the 4xx set to the journey's prediction route
17:43:59  ok    PUT prediction, 401  no session cookie: answered 401
17:43:59  ok    PUT prediction, 404  unknown question: answered 404
17:43:59  ok    PUT prediction, 422  invalid payload: answered 422
17:43:59  ok    PUT prediction, 403  question of a closed group: answered 403
17:43:59  waiting three evaluations (35 s) to see the rule stay Normal
17:44:35  ok    4xx never fires it: no notification reached the listener
17:44:35  stopping Postgres
17:44:36  the one failing PUT answered 500 in 12 ms
17:44:36  ok    the request with the database stopped answers a 5xx
17:44:36  ok    it fails fast (under 5 s), it does not hang
17:44:37  Postgres is back, the app answers /ready
17:44:37  polling the rule
17:44:41  rule state: Firing  {'(no route)': 'Normal (NoData)', '/api/tournaments/{tournament_id}/questions/{question_id}/prediction': 'Alerting'}
17:46:40  rule state: Normal  {'/api/tournaments/{tournament_id}/questions/{question_id}/prediction': 'Normal'}
17:46:40  ok    Firing 5 s after the failing request
17:46:40  ok    within 90 s
17:46:40  ok    back to Normal 125 s after the failing request
17:46:40  ok    within 240 s of the 5xx
17:46:40  ok    exactly one firing notification (got 1)
17:46:40  ok    exactly one resolved notification (got 1)
17:46:40  ok    the labels name the journey, the kind and the route template
17:46:40  ok    the window (2m) is an annotation
17:46:40  ok    runbook_url points at the Runbook section
17:46:40  ok    dashboardURL names the dashboard
17:46:40  ok    panelURL names panel 3
17:46:40  ok    dashboardURL opens (http://localhost:3000/d/place-a-prediction?from=1792687480000&orgId=1&to=1792691080027)
17:46:40  ok    panelURL opens (http://localhost:3000/d/place-a-prediction?from=1792687480000&orgId=1&to=1792691080027&viewPanel=3)

State transitions of the rule
  17:43:59  Normal  {'(no route)': 'Normal (NoData)'}
  17:44:41  Firing  {'(no route)': 'Normal (NoData)', '/api/tournaments/{tournament_id}/questions/{question_id}/prediction': 'Alerting'}
  17:46:40  Normal  {'/api/tournaments/{tournament_id}/questions/{question_id}/prediction': 'Normal'}
  Normal -> Firing -> Normal
```

What it shows:

- **Normal -> Firing -> Normal.** Firing at 17:44:41, 5 s after the failing
  request at 17:44:36, which answered 500 in 12 ms (limit: 90 s). Normal again at
  17:46:40, 125 s after it (limit: 240 s). The 4xx set before it (401, 404, 422,
  403) and the three evaluations after it left the rule Normal and the listener
  empty.
- **One notification each way.** One `firing` POST at 17:44:40, one `resolved`
  at 17:46:40, nothing else. The firing body carries the route template as
  `http_route`, the `window` (`2m`), a `runbook_url`, and `dashboardURL` and
  `panelURL` (the script opens both with a 200). The first `5xx` on a series
  that never had one fired it, which is the point of the zero injection: the
  value of the query was 2.08, for one request (see above).
- **Within the run, no second `firing`**, which holds until the 12 h repeat
  interval; the demo does not wait ten minutes.

```text
Received at 17:44:40, POST /alerts (firing)
{
  "receiver": "responder-webhook",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "5xx on the place-a-prediction journey",
        "grafana_folder": "Place a prediction",
        "http_route": "/api/tournaments/{tournament_id}/questions/{question_id}/prediction",
        "journey": "place-a-prediction",
        "kind": "http-5xx",
        "service": "tennis-prediction-game",
        "severity": "page"
      },
      "annotations": {
        "description": "Participants got server errors (HTTP 5xx) on /api/tournaments/{tournament_id}/questions/{question_id}/prediction: about 2 in the last 2m. Status class 5xx, any count above 0 fires.",
        "runbook_url": "https://github.com/kairosworks-dev/tennis-prediction-game/blob/main/docs/alerting.md#runbook",
        "summary": "5xx responses on /api/tournaments/{tournament_id}/questions/{question_id}/prediction",
        "window": "2m"
      },
      "startsAt": "2026-10-22T17:44:40Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://localhost:3000/alerting/grafana/journey-5xx/view?orgId=1",
      "fingerprint": "23ce3e9960198439",
      "dashboardURL": "http://localhost:3000/d/place-a-prediction?from=1792687480000&orgId=1&to=1792691080027",
      "panelURL": "http://localhost:3000/d/place-a-prediction?from=1792687480000&orgId=1&to=1792691080027&viewPanel=3",
      "ruleUID": "journey-5xx",
      "values": {
        "A": 2.081665765278529,
        "B": 2.081665765278529,
        "C": 1
      },
      "orgId": 1
    }
  ],
  "groupLabels": {
    "alertname": "5xx on the place-a-prediction journey",
    "http_route": "/api/tournaments/{tournament_id}/questions/{question_id}/prediction"
  },
  "externalURL": "http://localhost:3000/",
  "appVersion": "13.2.4",
  "version": "1",
  "groupKey": "{}:{alertname=\"5xx on the place-a-prediction journey\", http_route=\"/api/tournaments/{tournament_id}/questions/{question_id}/prediction\"}",
  "truncatedAlerts": 0,
  "orgId": 1,
  "title": "[FIRING:1] 5xx on the place-a-prediction journey /api/tournaments/{tournament_id}/questions/{question_id}/prediction (Place a prediction place-a-prediction http-5xx tennis-prediction-game page)",
  "state": "alerting"
}

Received at 17:46:40, POST /alerts (resolved)
{
  "receiver": "responder-webhook",
  "status": "resolved",
  "alerts": [
    {
      "status": "resolved",
      "labels": {
        "alertname": "5xx on the place-a-prediction journey",
        "grafana_folder": "Place a prediction",
        "http_route": "/api/tournaments/{tournament_id}/questions/{question_id}/prediction",
        "journey": "place-a-prediction",
        "kind": "http-5xx",
        "service": "tennis-prediction-game",
        "severity": "page"
      },
      "annotations": {
        "description": "Participants got server errors (HTTP 5xx) on /api/tournaments/{tournament_id}/questions/{question_id}/prediction: about 0 in the last 2m. Status class 5xx, any count above 0 fires.",
        "runbook_url": "https://github.com/kairosworks-dev/tennis-prediction-game/blob/main/docs/alerting.md#runbook",
        "summary": "5xx responses on /api/tournaments/{tournament_id}/questions/{question_id}/prediction",
        "window": "2m"
      },
      "startsAt": "2026-10-22T17:44:40Z",
      "endsAt": "2026-10-22T17:46:40Z",
      "generatorURL": "http://localhost:3000/alerting/grafana/journey-5xx/view?orgId=1",
      "fingerprint": "23ce3e9960198439",
      "dashboardURL": "http://localhost:3000/d/place-a-prediction?from=1792687480000&orgId=1&to=1792691200000",
      "panelURL": "http://localhost:3000/d/place-a-prediction?from=1792687480000&orgId=1&to=1792691200000&viewPanel=3",
      "ruleUID": "journey-5xx",
      "values": {
        "A": 0,
        "B": 0,
        "C": 0
      },
      "orgId": 1
    }
  ],
  "groupLabels": {
    "alertname": "5xx on the place-a-prediction journey",
    "http_route": "/api/tournaments/{tournament_id}/questions/{question_id}/prediction"
  },
  "externalURL": "http://localhost:3000/",
  "appVersion": "13.2.4",
  "version": "1",
  "groupKey": "{}:{alertname=\"5xx on the place-a-prediction journey\", http_route=\"/api/tournaments/{tournament_id}/questions/{question_id}/prediction\"}",
  "truncatedAlerts": 0,
  "orgId": 1,
  "title": "[RESOLVED] 5xx on the place-a-prediction journey /api/tournaments/{tournament_id}/questions/{question_id}/prediction (Place a prediction place-a-prediction http-5xx tennis-prediction-game page)",
  "state": "ok"
}
```

The two bodies are the `firing` and the `resolved` POST the listener received, in that order.

### Checked once, by hand

- **A quiet stack.** A stack started from empty volumes, with no traffic at all,
  loaded the three files with no provisioning error in Grafana's log (the
  `provisioning.alerting` lines say `starting to provision alerting` and
  `finished to provision alerting`; no `level=error` line), and the rule was
  Normal (the instance as `Normal (NoData)`, health `ok`).
- **Datasource down is visible.** Prometheus stopped at 17:46:59: at the next
  evaluation (17:47:09) the rule health was `error` and its instance `Error`
  (the error text names the failed query; the Grafana log has the same), and it
  stayed that way for the 40 s it was down. Started again at 17:47:40: Normal at
  the next poll (17:47:50). In a second run Grafana sent a `DatasourceError`
  `firing` webhook (at 17:49:10, labels `alertname=DatasourceError`,
  `datasource_uid=prometheus`, `ref_id=A`, `rulename=...`, no `http_route`,
  the summary "The 5xx alert could not be evaluated") and a `resolved` one
  30 s later.
- **Every route of the journey.** With a session from before, Postgres stopped
  and one request to each of the other five routes (login included), all five
  answered 500, and five instances, one per route, went Alerting, each with its
  own `firing` webhook (one per `http_route`, because of `group_by`) and its own
  `resolved` one a few minutes later.
- **The dashboard panel.** Panel 3's query, with the six-route selector added,
  returns the 401, 403, 404, 422 and 500 rows of the demo for the prediction
  route, and the selector matches all six routes after the journey demo of
  `observability.md`.
- **The contact point's test delivery** reaches the listener (done by every run
  of the script; the body is `TestAlert`).

## What changed outside this file

`docker-compose.telemetry.yml`: the `prometheus` service gets one flag
(`--enable-feature=created-timestamp-zero-ingestion`); the `grafana` service
gets `GF_SERVER_ROOT_URL`, `RESPONDER_URL`, `extra_hosts` and the read-only
mount of `telemetry/grafana/provisioning/alerting`. The dashboard's panel 3
query gets the route selector. Nothing in `backend/app`, `frontend/` or the
default stack changed.
