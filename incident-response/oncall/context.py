"""Collect the evidence for an incident's time window and save it.

Three sources, each optional except Loki:

- Loki (LOKI_URL): the error log records of the window. Unreachable means the
  run escalates before any worktree or agent: there is nothing to diagnose from.
- Tempo (TEMPO_URL): the failing traces. Unreachable is noted; the run goes on.
- The app container's stderr (decision A, 22 Oct): telemetry carries the
  exception type only, so the traceback comes from `docker logs` of the
  overlay's app container, stderr only. Unavailable is noted; the run goes on.

Only allow-listed fields of each record are kept. Everything is redacted on
write (folder.py).
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .folder import IncidentFolder
from .incident import Incident, iso
from .seams import Commands, Http, Unreachable

LOKI_QUERIES = (
    ("unhandled exceptions", '{service_name="%s"} |= "unhandled exception"'),
    (
        "5xx responses",
        '{service_name="%s"} |= "request completed" | http_response_status_code=~"5.."',
    ),
)
LOKI_LIMIT = 200
#: The log fields kept, after dots become underscores (Loki's own spelling).
LOG_FIELDS = (
    "time",
    "level",
    "severity_text",
    "detected_level",
    "message",
    "http_route",
    "http_request_method",
    "http_response_status_code",
    "exception_type",
    "duration_ms",
    "trace_id",
    "span_id",
)

TEMPO_QUERY = '{ resource.service.name = "%s" && span.http.response.status_code >= 500 }'
TEMPO_LIMIT = 20
TRACES_FETCHED = 5
#: The span attributes kept from a trace.
SPAN_ATTRIBUTES = (
    "http.route",
    "http.request.method",
    "http.response.status_code",
    "error.type",
    "exception.type",
)
TRACE_ID = re.compile(r"^[0-9a-fA-F]{16,32}$")

COMPOSE_FILES = ("docker-compose.yml", "docker-compose.telemetry.yml")
APP_SERVICE = "app"
STDERR_MAX_LINES = 400
TRACEBACKS_KEPT = 3
TRACEBACK_MAX_LINES = 120


@dataclass
class Source:
    name: str
    reachable: bool = False
    detail: str = ""
    count: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {"reachable": self.reachable, "detail": self.detail, "count": self.count}


@dataclass
class Context:
    loki: Source = field(default_factory=lambda: Source("loki"))
    tempo: Source = field(default_factory=lambda: Source("tempo"))
    traceback: Source = field(default_factory=lambda: Source("traceback"))
    log_records: List[Dict[str, Any]] = field(default_factory=list)
    traces: List[Dict[str, Any]] = field(default_factory=list)
    tracebacks: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self, incident: Incident, folder: IncidentFolder) -> Dict[str, Any]:
        return {
            "incident": folder.path.name,
            "source": incident.source,
            "endpoint": incident.endpoint,
            "window": [iso(incident.window[0]), iso(incident.window[1])] if incident.window else None,
            "sources": {
                "loki": self.loki.as_dict(),
                "tempo": self.tempo.as_dict(),
                "traceback": self.traceback.as_dict(),
            },
            **self.extra,
            "files": folder.files(),
        }


def _ns(moment: datetime) -> str:
    return str(int(moment.timestamp() * 1_000_000_000))


def _ns_to_iso(value: Any) -> str:
    try:
        seconds = int(value) / 1_000_000_000
    except (TypeError, ValueError):
        return ""
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _keep_log_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    flat = {str(k).replace(".", "_"): v for k, v in fields.items()}
    return {k: flat[k] for k in LOG_FIELDS if k in flat and flat[k] not in (None, "")}


def parse_loki(body: Any) -> List[Dict[str, Any]]:
    """Loki query_range streams -> allow-listed records, oldest first."""
    if not isinstance(body, dict) or body.get("status") not in (None, "success"):
        raise Unreachable("Loki answered without a result")
    result = (body.get("data") or {}).get("result") or []
    records: List[Dict[str, Any]] = []
    for stream in result:
        labels = dict(stream.get("stream") or {})
        for value in stream.get("values") or []:
            if not isinstance(value, list) or len(value) < 2:
                continue
            fields: Dict[str, Any] = dict(labels)
            if len(value) > 2 and isinstance(value[2], dict):
                meta = value[2]
                for part in ("structuredMetadata", "parsed"):
                    if isinstance(meta.get(part), dict):
                        fields.update(meta[part])
                fields.update({k: v for k, v in meta.items() if not isinstance(v, dict)})
            line = str(value[1])
            try:
                parsed = json.loads(line)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                fields.update(parsed)
            else:
                fields["message"] = line
            fields["time"] = _ns_to_iso(value[0])
            records.append(_keep_log_fields(fields))
    records.sort(key=lambda r: r.get("time", ""))
    return records


def collect_logs(http: Http, base: str, service: str, window: Tuple[datetime, datetime]) -> Tuple[Source, List[Dict[str, Any]]]:
    source = Source("loki")
    records: List[Dict[str, Any]] = []
    seen = set()
    for _, template in LOKI_QUERIES:
        query = urllib.parse.urlencode(
            {
                "query": template % service,
                "start": _ns(window[0]),
                "end": _ns(window[1]),
                "limit": str(LOKI_LIMIT),
                "direction": "forward",
            }
        )
        try:
            body = http.get_json(f"{base}/loki/api/v1/query_range?{query}")
            found = parse_loki(body)
        except Unreachable as error:
            source.reachable = False
            source.detail = f"Loki unreachable: {error}"
            return source, []
        for record in found:
            marker = json.dumps(record, sort_keys=True)
            if marker not in seen:
                seen.add(marker)
                records.append(record)
    records.sort(key=lambda r: r.get("time", ""))
    source.reachable = True
    source.count = len(records)
    source.detail = (
        f"{len(records)} error record(s) in the window"
        if records
        else "reachable, but no error records in the window"
    )
    return source, records


def _attr_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for kind in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if kind in value:
            return value[kind]
    return None


def summarise_trace(trace_id: str, body: Any) -> Dict[str, Any]:
    if isinstance(body, dict) and isinstance(body.get("trace"), dict):
        body = body["trace"]
    batches = []
    if isinstance(body, dict):
        batches = body.get("batches") or body.get("resourceSpans") or []
    spans: List[Dict[str, Any]] = []
    for batch in batches:
        for scope in batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []:
            for span in scope.get("spans") or []:
                attributes = {
                    a.get("key"): _attr_value(a.get("value"))
                    for a in span.get("attributes") or []
                    if a.get("key") in SPAN_ATTRIBUTES
                }
                events = [
                    {
                        a.get("key"): _attr_value(a.get("value"))
                        for a in event.get("attributes") or []
                        if a.get("key") == "exception.type"
                    }
                    for event in span.get("events") or []
                    if event.get("name") == "exception"
                ]
                try:
                    duration_ms = round(
                        (int(span.get("endTimeUnixNano", 0)) - int(span.get("startTimeUnixNano", 0)))
                        / 1_000_000,
                        1,
                    )
                except (TypeError, ValueError):
                    duration_ms = None
                spans.append(
                    {
                        "name": str(span.get("name", ""))[:200],
                        "start": _ns_to_iso(span.get("startTimeUnixNano")),
                        "duration_ms": duration_ms,
                        "status": (span.get("status") or {}).get("code", ""),
                        "attributes": attributes,
                        "exception_events": [e for e in events if e],
                    }
                )
    return {"trace_id": trace_id, "spans": spans}


def collect_traces(
    http: Http,
    base: str,
    service: str,
    window: Tuple[datetime, datetime],
    known_ids: Iterable[str],
) -> Tuple[Source, List[Dict[str, Any]]]:
    source = Source("tempo")
    ids: List[str] = []
    for trace_id in known_ids:
        if TRACE_ID.match(trace_id) and trace_id.lower() not in ids:
            ids.append(trace_id.lower())
    errors: List[str] = []
    answered = False
    query = urllib.parse.urlencode(
        {
            "q": TEMPO_QUERY % service,
            "start": str(int(window[0].timestamp())),
            "end": str(int(window[1].timestamp())),
            "limit": str(TEMPO_LIMIT),
        }
    )
    try:
        body = http.get_json(f"{base}/api/search?{query}")
        answered = True
        for trace in (body or {}).get("traces") or []:
            trace_id = str(trace.get("traceID", ""))
            if TRACE_ID.match(trace_id) and trace_id.lower() not in ids:
                ids.append(trace_id.lower())
    except Unreachable as error:
        errors.append(f"search: {error}")

    traces: List[Dict[str, Any]] = []
    for trace_id in ids[:TRACES_FETCHED]:
        try:
            traces.append(summarise_trace(trace_id, http.get_json(f"{base}/api/traces/{trace_id}")))
            answered = True
        except Unreachable as error:
            errors.append(f"trace {trace_id}: {error}")

    source.reachable = answered
    source.count = len(traces)
    if not answered:
        source.detail = "Tempo unreachable: " + "; ".join(errors[:2])
    elif traces:
        source.detail = f"{len(traces)} failing trace(s) fetched"
    else:
        source.detail = "reachable, but no failing traces found in the window"
    if answered and errors:
        source.detail += " (some lookups failed: " + "; ".join(errors[:2]) + ")"
    return source, traces


def extract_tracebacks(text: str) -> List[str]:
    """The `Traceback (most recent call last):` blocks of a stderr text."""
    blocks: List[List[str]] = []
    current: Optional[List[str]] = None
    previous = ""
    just_closed = False
    chained = ("During handling of the above exception", "The above exception was the direct cause")
    for line in text.splitlines():
        if line.startswith("Traceback (most recent call last):"):
            if current is None:
                current = [previous] if previous.startswith("ERROR:") else []
            current.append(line)
        elif current is None and just_closed and line.startswith(chained):
            current = blocks.pop() + ["", line]  # a chained exception: one block
        elif current is not None:
            if line.startswith((" ", "\t")) or not line.strip() or line.startswith(chained):
                current.append(line)
            else:
                current.append(line)  # the exception line closes the block
                blocks.append(current)
                current = None
                previous = line
                just_closed = True
                continue
        if line.strip():
            just_closed = False
        previous = line
    if current:
        blocks.append(current)
    kept = []
    for block in blocks[-TRACEBACKS_KEPT:]:
        if len(block) > TRACEBACK_MAX_LINES:
            half = TRACEBACK_MAX_LINES // 2
            block = block[:half] + [f"... {len(block) - 2 * half} lines left out ..."] + block[-half:]
        kept.append("\n".join(block))
    return kept


def find_app_container(commands: Commands, compose_dir: Path, env: Dict[str, str]) -> Tuple[Optional[str], str]:
    argv = ["docker", "compose"]
    for name in COMPOSE_FILES:
        argv += ["-f", name]
    argv += ["ps", "-q", APP_SERVICE]
    result = commands.run(argv, cwd=compose_dir, env=env, timeout=30)
    if not result.ok:
        return None, f"docker compose ps failed: {_first_line(result.stderr)}"
    ids = result.stdout.split()
    if not ids:
        return None, "the telemetry stack's app container is not running"
    return ids[0], "the telemetry stack's app container"


def collect_traceback(
    commands: Commands,
    compose_dir: Path,
    container: Optional[str],
    window: Tuple[datetime, datetime],
    env: Dict[str, str],
) -> Tuple[Source, str, List[str]]:
    source = Source("traceback")
    if container:
        how = "RESPONDER_APP_CONTAINER"
    else:
        container, how = find_app_container(commands, compose_dir, env)
        if container is None:
            source.detail = f"container stderr unavailable: {how}"
            return source, "", []
    argv = ["docker", "logs", "--since", iso(window[0]), "--until", iso(window[1]), container]
    result = commands.run(argv, cwd=compose_dir, env=env, timeout=60, discard_stdout=True)
    if not result.ok:
        source.detail = f"container stderr unavailable: docker logs failed: {_first_line(result.stderr)}"
        return source, "", []
    lines = result.stderr.splitlines()[-STDERR_MAX_LINES:]
    text = "\n".join(lines) + ("\n" if lines else "")
    tracebacks = extract_tracebacks(text)
    source.reachable = True
    source.count = len(tracebacks)
    source.detail = (
        f"{len(tracebacks)} traceback(s) in the container's stderr ({how})"
        if tracebacks
        else f"container stderr read ({how}), but no traceback in the window"
    )
    return source, text, tracebacks


def _first_line(text: str) -> str:
    stripped = text.strip()
    return stripped.splitlines()[0][:200] if stripped else "no message"


def collect(
    incident: Incident,
    folder: IncidentFolder,
    *,
    http: Http,
    commands: Commands,
    loki_url: str,
    tempo_url: str,
    service: str,
    compose_dir: Path,
    container: Optional[str],
    env: Dict[str, str],
) -> Context:
    """Fetch and save the evidence. Stops after Loki if Loki is unreachable."""
    ctx = Context()
    if incident.window is None:
        ctx.loki.detail = "the trigger gave no time window"
        folder.write_json("context.json", ctx.as_dict(incident, folder))
        return ctx

    ctx.loki, ctx.log_records = collect_logs(http, loki_url, service, incident.window)
    if not ctx.loki.reachable:
        ctx.tempo.detail = "not queried: Loki is unreachable, the run escalates"
        ctx.traceback.detail = "not read: Loki is unreachable, the run escalates"
        folder.write_json("context.json", ctx.as_dict(incident, folder))
        return ctx
    folder.write_json("logs.json", ctx.log_records)

    known = [str(r["trace_id"]) for r in ctx.log_records if r.get("trace_id")]
    ctx.tempo, ctx.traces = collect_traces(http, tempo_url, service, incident.window, known)
    if ctx.tempo.reachable:
        folder.write_json("traces.json", ctx.traces)

    ctx.traceback, stderr_text, ctx.tracebacks = collect_traceback(
        commands, compose_dir, container, incident.window, env
    )
    if ctx.traceback.reachable:
        folder.write("app-stderr.txt", stderr_text)
        folder.write("tracebacks.txt", "\n\n".join(ctx.tracebacks) + "\n" if ctx.tracebacks else "")

    folder.write_json("context.json", ctx.as_dict(incident, folder))
    return ctx
