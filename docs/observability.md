# Observability

An optional, local telemetry stack for one key journey. Metrics, traces and
request logs share a trace ID, flow through an OpenTelemetry Collector into
Prometheus, Tempo and Loki, and are walked in Grafana from a request metric to
its log line to its trace. No customer data and no credentials are in any
signal. Decisions: D20 (local demo only) and D22 (optional platform service, no
personal data), spec Section 11.

It is **off unless asked for**. `docker compose up`, `make run`,
`make test-integration` and CI never start it, and the app sets up no telemetry
unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set (only the overlay sets it).

## The journey

A participant signs in, opens a game and submits a prediction. The routes, as
route templates (never the raw path):

1. `POST /api/auth/login`
2. `GET /api/tournaments`
3. `GET /api/tournaments/{tournament_id}`
4. `GET /api/tournaments/{tournament_id}/bet-groups`
5. `GET /api/tournaments/{tournament_id}/bet-groups/{bet_group_id}/questions`
6. `PUT /api/tournaments/{tournament_id}/questions/{question_id}/prediction`

The instrumentation is app-wide, so every `/api/` route is observed; the
dashboard and the demo are about these six. `/health`, `/ready` (called every
30 s by the container healthcheck), the static frontend and the other
non-`/api/` paths are excluded from every signal.

## Start, demo, stop

Needs Docker with the compose plugin.

```bash
make telemetry-up      # app, Postgres, Collector, Prometheus, Loki, Tempo, Grafana; returns when healthy
make telemetry-demo    # the journey, plus two client errors; REPEAT=5 make telemetry-demo to repeat it
make telemetry-down    # stop everything, keep the telemetry data
make telemetry-reset   # stop everything and delete the telemetry volumes (the database volume stays)
```

Behind them: `docker compose -f docker-compose.yml -f docker-compose.telemetry.yml ...`.
The overlay is never loaded by default (it is deliberately not called
`docker-compose.override.yml`, which Compose loads on its own).

- The app is on `127.0.0.1:${APP_PORT:-8000}`. Set `APP_PORT` if 8000 is taken.
- Grafana: `http://localhost:3000`, user `admin`, password from
  `GRAFANA_ADMIN_PASSWORD` (development default in the overlay; not a secret).
- Prometheus `:9090`, Loki `:3100`, Tempo `:3200`, Collector OTLP/HTTP `:4318`.
- **Every published port is bound to `127.0.0.1`** (check with
  `docker compose -f docker-compose.yml -f docker-compose.telemetry.yml ps`).
- Data sits in named volumes with about two days of retention.

`telemetry/demo-journey.sh` (what `make telemetry-demo` runs) reads its ids from
the API, prints each step with the `X-Trace-Id` of the response, and exits
non-zero if a step answers an unexpected status. Besides the six steps (plus
one `GET .../draws` that reads the best-of for a legal set score) it sends two
client errors: a request without a session (**401**) and a sign-in with a wrong
password, which the contract answers **422**. Both are 4xx on the dashboard.
It uses the seeded demo participant (`you@example.com`) and the seeded demo
password; override with `DEMO_EMAIL`, `DEMO_PASSWORD`, `BASE_URL`.

## The signals

All three carry the same resource: `service.name=tennis-prediction-game`,
`deployment.environment.name=local-demo`, and the SDK's own identifiers.

**Metrics** (Prometheus, pushed by the Collector). The request metric is the
FastAPI instrumentation's HTTP server duration histogram. Names and labels as
confirmed on a running stack:

| Prometheus series | Labels |
|---|---|
| `http_server_request_duration_seconds_count`, `_sum`, `_bucket` | `http_route` (the template), `http_request_method`, `http_response_status_code`, `service_name`, plus `job` and `instance` added by Prometheus |

Nothing else is a label: no user, no id. A request that matches no route has
no `http_route` label; its raw path is never a label.

**Logs** (Loki, over OTLP, and JSON lines on stdout). One record per `/api/`
request, written while the request's trace context is current:
message `request completed`, level INFO. In Loki the fields arrive as labels
and structured metadata with dots turned into underscores: `http_route`,
`http_request_method`, `http_response_status_code`, `duration_ms`, and the
record's own `trace_id` and `span_id` (the span's IDs). An unhandled exception
adds one ERROR record, `unhandled exception`, with `exception_type` only.

The stdout lines (`docker compose ... logs app`) are one JSON object per
request, with `LOG_FORMAT=json` (set by the overlay):

```json
{"timestamp": "2026-10-22T16:20:36.152Z", "level": "INFO", "message": "request completed", "service": "tennis-prediction-game", "trace_id": "<32 hex>", "span_id": "<16 hex>", "http.route": "/api/tournaments", "http.request.method": "GET", "http.response.status_code": 200, "duration_ms": 3.4}
```

Outside a trace the two ID fields are left out. The handler that exports logs
is attached to one dedicated logger (`tennis.requests`), never to the root
logger, so nothing else logged in the process reaches telemetry.

**Traces** (Tempo). One server span per request, named from the method and
route template, for example `PUT /api/tournaments/{tournament_id}/questions/{question_id}/prediction`.
The ASGI `send`/`receive` child spans are turned off. There are no database
spans: traces are one span per request (the optional SQLAlchemy
instrumentation is not installed).

**`X-Trace-Id`** is added to every response of an `/api/` request when
telemetry is on, so `curl -i` shows the ID to look up. It is an operational
header and is not in `openapi.yaml` (hard rule 3; the same kind of exception as
the probes in D17). It is absent on an unhandled 500, whose response Starlette
builds outside the app's middleware; find that request by route and status in
Loki.

**Sampling** is 100 % (`parentbased_always_on`): the demo has a handful of
requests and each must have a trace. A real deployment would use
`parentbased_traceidratio`. **Metric export interval** is 5 s so the demo does
not wait a minute.

## What is kept out, and what is not covered

Defence in two layers. The first is proven by unit tests, the second is
configuration.

1. **In the app** (`backend/app/telemetry/allowlist.py`): every span, metric and
   log attribute whose key is not on an explicit allowlist is dropped before
   export, as are span links, span-status descriptions, resource keys that are
   not listed, and the source-location attributes the SDK's logging handler adds
   (`code.file.path`, `code.function.name`, `code.line.number`). Anything an
   instrumentation library adds in a later release is dropped by default.
   Metrics keep three labels: method, status code, route template.
2. **In the Collector** (`telemetry/otel-collector.yaml`): the `transform/guard`
   processor applies the same allowlists again, and the `redaction` processor
   masks any attribute value shaped like an e-mail address. Both sit in the
   traces, metrics and logs pipelines. A test keeps the Collector's lists equal
   to the app's. The Collector has no `debug` exporter: nothing is echoed to its
   own log.

Covered by `backend/tests/test_telemetry.py`, with sentinel values: e-mail
addresses (login and register), passwords, display names, the session cookie
value, the `Authorization`, `Cookie` and `Set-Cookie` headers, request and
response bodies, query strings, the client address (including a forwarded one)
and user agent, the signed-in user (not identified at all; the trace ID links a
report to a request), and exception messages and stack traces.

**Exceptions are reported by type only**, never the message or the stack, in
spans, span events and logs. The span status carries no description.

The console e-mail mock (`EMAIL_PROVIDER=console`) prints
`[email] verification for <address>: token=<token>` to stderr with `print`
since #59. It does not use `logging`, so no handler can ship it, and it is not
exported; a test registers an account with that provider on and asserts that
neither the line nor the address reaches any signal. The default provider
writes nothing.

Not covered, honestly:

- **`url.path` on spans** keeps the concrete path, so path parameters such as
  `roland-garros-2026` appear there (they are not personal data), and for a
  request that matches no route, whatever the client typed. The Collector masks
  an e-mail-shaped value in it, but a path is not otherwise inspected. It is
  never a metric label and never in a log record.
- **Container output that is not telemetry**: uvicorn's access log and its
  traceback for an unhandled exception go to the container's stderr, which this
  stack does not collect. They are not part of the signals described here.
- Postgres and Grafana logs, and host and container resource metrics, are not
  collected (out of scope for this journey).
- The Collector and the stack on the author's machine are a local demo, not a
  hardened service: ports are loopback-only and the Grafana password is a
  development default.

## Walking metric, log and trace in Grafana

Open the dashboard **Place a prediction** (Dashboards; it is provisioned from
`telemetry/grafana/dashboards/`, so it is there on a fresh stack with no clicks).

1. **Requests by route and status** lists the counts per route template and
   status. **Errors by class** counts 4xx and 5xx (the 401 and the 422 of the
   demo are 4xx). **Errors by route and status** lists the failing routes.
   **Requests per minute by route** and **p95 latency per route** are time
   series; the p95 is taken over the cumulative histogram, since the app started,
   because a short demo has no steady rate to take a quantile of.
2. The **Logs** panel (Loki, same `Route` and `Status` variables) lists the
   `request completed` lines. Open a line: its `trace_id` field has an
   **Open trace in Tempo** link (a Loki derived field).
3. The link opens the trace in Tempo. **Logs for this span** (Tempo traces to
   logs) opens Loki filtered on that trace ID, so the walk also works in
   reverse.
4. From the metric: click a route in **Errors by route and status**
   (*Logs for this route*) to land in Explore on Loki, filtered on that route
   and status.

Grafana 13 can open an empty `-- Grafana --` pane on the first derived-field
click after it starts; a second click works. It is not a configuration error.

### The three queries for one request

Take the `PUT` of the demo; the demo prints `prediction trace_id: <id>`, and the
same value is in that response's `X-Trace-Id` header.

```bash
TID=<the trace_id>
# Loki: the log record, by trace ID
curl -sG "http://127.0.0.1:3100/loki/api/v1/query_range" \
  --data-urlencode "query={service_name=\"tennis-prediction-game\"} |= \"request completed\" | trace_id=\"$TID\"" \
  --data-urlencode "start=$(( $(date +%s) - 900 ))000000000"
# Tempo: the trace (the raw JSON shows IDs in base64; compare in hex)
curl -s "http://127.0.0.1:3200/api/traces/$TID"
# Prometheus: the request metric for that route
curl -sG http://127.0.0.1:9090/api/v1/query --data-urlencode \
  'query=sum by (http_route, http_response_status_code) (http_server_request_duration_seconds_count{http_route="/api/tournaments/{tournament_id}/questions/{question_id}/prediction"})'
```

The log record's `trace_id` and `span_id` equal the span's, and the trace ID is
the one in `X-Trace-Id`.

## A 5xx you can see

```bash
docker compose -f docker-compose.yml -f docker-compose.telemetry.yml stop postgres
# then, with a session cookie obtained before stopping it, repeat the PUT of step 6:
# it answers 500 Internal Server Error.
```

A 500 shows, within the 5 s export interval plus one dashboard refresh (10 s), as a 5xx in **Errors by class** and as a
row in **Errors by route and status**; Loki has the `request completed` line with
status 500 and an ERROR record carrying only the exception type (for example
`OperationalError`). Sign in before stopping Postgres, because signing in needs
the database too. Start it again with `start postgres` and wait until it is
healthy. The alert on exactly this is #57.

## When the Collector is down

`docker compose -f docker-compose.yml -f docker-compose.telemetry.yml stop otel-collector`:
the app answers every request with the same statuses and writes no traceback per
request. The exporters log one-line warnings per failed batch
(`Transient error ... Failed to export ... batch`) and drop the batch; signals
produced during the outage are lost. Started again, new requests appear in
Grafana.

## Configuration

Standard OpenTelemetry variables, set only by `docker-compose.telemetry.yml`:

| Variable | Value |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4318` (the switch: unset means off) |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_SERVICE_NAME` | `tennis-prediction-game` |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment.name=local-demo` |
| `OTEL_TRACES_SAMPLER` | `parentbased_always_on` |
| `OTEL_METRIC_EXPORT_INTERVAL` | `5000` (ms) |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `http` (stable HTTP names; the app also defaults it) |
| `LOG_FORMAT` | `json` (JSON lines on stdout; the default is the plain format) |

`OTEL_SDK_DISABLED=true` turns telemetry off even with an endpoint set.
`docker-compose.yml` carries none of these. Images are pinned by tag and digest;
the Collector is the contrib build (it has the `transform` and `redaction`
processors).

Files: `backend/app/telemetry/` (setup, allowlist, request log, JSON formatter),
`docker-compose.telemetry.yml`, `telemetry/` (Collector, Prometheus, Loki, Tempo,
Grafana provisioning and the dashboard, the demo script). The layout leaves room
for alert rules under `telemetry/grafana/provisioning/alerting/` (#57). Nothing
in `backend/app/domain/`, `services/` or `providers/` imports OpenTelemetry; a
test checks it.
