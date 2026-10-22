"""Telemetry (#56): the journey is observable, and nothing personal leaves.

No Docker and no network: spans, metrics and log records go to in-memory
exporters, behind the same allowlist the OTLP exporters sit behind. Every test
that turns telemetry on sets `OTEL_EXPORTER_OTLP_ENDPOINT` itself; the rest of
the suite never sets it, which is the "off by default" case.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import telemetry
from app.main import create_app
from app.repositories.memory import MemoryRepositories
from app.seed import DEMO_PASSWORD
from app.telemetry import allowlist
from app.telemetry.request_log import REQUEST_LOGGER

REPO = Path(__file__).resolve().parents[2]
TOURNAMENT_ID = "roland-garros-2026"
LOCAL_ENDPOINT = "http://127.0.0.1:4318"

#: Substrings that must not appear in any attribute key.
FORBIDDEN_KEY_PARTS = (
    "cookie",
    "authorization",
    "url.query",
    "client.",
    "user_agent",
    "http.target",
    "http.url",
    "server.",
    "code.",
    "exception.message",
    "exception.stacktrace",
    "enduser",
    "user.",
)


@dataclass
class Captured:
    app: FastAPI
    client: TestClient
    spans: InMemorySpanExporter
    metrics: InMemoryMetricReader
    logs: InMemoryLogRecordExporter

    def span_list(self) -> list[Any]:
        return list(self.spans.get_finished_spans())

    def log_list(self) -> list[Any]:
        return list(self.logs.get_finished_logs())

    def data_points(self, metric_name: str = "http.server.request.duration") -> list[Any]:
        data = self.metrics.get_metrics_data()
        points = []
        for resource_metrics in data.resource_metrics if data else []:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == metric_name:
                        points.extend(metric.data.data_points)
        return points

    def everything_exported(self) -> str:
        """Every exported span, metric and log record as one text."""
        parts = [span.to_json() for span in self.span_list()]
        data = self.metrics.get_metrics_data()
        if data:
            parts.append(data.to_json())
        parts.extend(record.to_json() for record in self.log_list())
        return "\n".join(parts)

    def every_attribute_key(self) -> set[str]:
        keys: set[str] = set()
        for span in self.span_list():
            keys |= set(span.attributes or {})
            keys |= set(span.resource.attributes)
            for event in span.events:
                keys |= set(event.attributes or {})
        data = self.metrics.get_metrics_data()
        for resource_metrics in data.resource_metrics if data else []:
            keys |= set(resource_metrics.resource.attributes)
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    for point in metric.data.data_points:
                        keys |= set(point.attributes or {})
        for record in self.log_list():
            keys |= set(record.log_record.attributes or {})
            keys |= set(record.resource.attributes)
        return keys


@pytest.fixture
def telemetry_on(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Captured]:
    """Build an app with telemetry on and in-memory exporters."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", LOCAL_ENDPOINT)
    monkeypatch.setenv("OTEL_SERVICE_NAME", "tennis-test")
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)

    def build(**create_kwargs: Any) -> Captured:
        spans = InMemorySpanExporter()
        metrics = InMemoryMetricReader()
        logs = InMemoryLogRecordExporter()
        monkeypatch.setattr(
            "app.main.setup_telemetry",
            functools.partial(
                telemetry.setup_telemetry,
                span_exporter=spans,
                metric_reader=metrics,
                log_exporter=logs,
            ),
        )
        app = create_app(repositories=MemoryRepositories(), **create_kwargs)
        client = TestClient(app, raise_server_exceptions=False)
        return Captured(app, client, spans, metrics, logs)

    return build


@pytest.fixture(autouse=True)
def _clean_request_logger() -> Iterator[None]:
    yield
    logger = logging.getLogger(REQUEST_LOGGER)
    logger.handlers.clear()


def _login(client: TestClient, **kwargs: Any) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "you@example.com", "password": DEMO_PASSWORD},
        **kwargs,
    )
    assert response.status_code == 200, response.text


def _run_journey(client: TestClient, *, probe: str = "") -> dict[str, Any]:
    """The six routes of the journey. Returns the responses by step."""
    query = f"?probe={probe}" if probe else ""
    steps: dict[str, Any] = {}
    steps["login"] = client.post(
        f"/api/auth/login{query}",
        json={"email": "you@example.com", "password": DEMO_PASSWORD},
        headers={"User-Agent": f"agent-{probe}", "X-Forwarded-For": "203.0.113.9"},
    )
    steps["list"] = client.get(f"/api/tournaments{query}")
    steps["one"] = client.get(f"/api/tournaments/{TOURNAMENT_ID}{query}")
    groups = client.get(f"/api/tournaments/{TOURNAMENT_ID}/bet-groups{query}")
    steps["groups"] = groups
    open_group = next(g for g in groups.json() if g["status"] == "OPEN")
    questions = client.get(
        f"/api/tournaments/{TOURNAMENT_ID}/bet-groups/{open_group['id']}/questions{query}"
    )
    steps["questions"] = questions
    question = next(q for q in questions.json() if q["answerType"] == "MATCH_RESULT")
    draws = client.get(f"/api/tournaments/{TOURNAMENT_ID}/draws").json()
    best_of = next(d["bestOf"] for d in draws if d["id"] == question["drawId"])
    steps["put"] = client.put(
        f"/api/tournaments/{TOURNAMENT_ID}/questions/{question['id']}/prediction{query}",
        json={
            "tournamentId": TOURNAMENT_ID,
            "questionId": question["id"],
            "payload": {
                "kind": "GENERIC_MATCH_RESULT",
                "winnerId": question["matchup"][0],
                "setScore": "3-1" if best_of == 5 else "2-1",
            },
            "asDraft": False,
        },
    )
    return steps


class TestOffByDefault:
    def test_without_an_endpoint_nothing_is_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        logging.getLogger(REQUEST_LOGGER).handlers.clear()
        app = create_app(repositories=MemoryRepositories())
        client = TestClient(app)

        _login(client)
        response = client.get("/api/tournaments")

        assert response.status_code == 200
        assert "x-trace-id" not in response.headers
        assert not getattr(app, "_is_instrumented_by_opentelemetry", False)
        assert logging.getLogger(REQUEST_LOGGER).handlers == []

    def test_the_sdk_switch_turns_it_off_even_with_an_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", LOCAL_ENDPOINT)
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        client = TestClient(create_app(repositories=MemoryRepositories()))

        assert "x-trace-id" not in client.get("/api/tournaments").headers

    def test_create_app_can_run_repeatedly_with_telemetry_on(
        self, telemetry_on: Callable[..., Captured]
    ) -> None:
        for _ in range(3):
            captured = telemetry_on()
            assert captured.client.get("/api/tournaments").status_code in {200, 401}
        # One handler for the OTLP sink, however many apps were built.
        assert len(logging.getLogger(REQUEST_LOGGER).handlers) == 1


class TestOn:
    def test_each_journey_request_yields_one_span_one_data_point_and_one_log(
        self, telemetry_on: Callable[..., Captured]
    ) -> None:
        captured = telemetry_on()
        steps = _run_journey(captured.client)
        assert all(r.status_code == 200 for r in steps.values()), {
            k: r.status_code for k, r in steps.items()
        }

        spans = captured.span_list()
        logs = [r for r in captured.log_list() if r.log_record.body == "request completed"]
        # The journey makes seven API calls (the draws lookup is one of them).
        assert len(spans) == len(logs) == 7
        assert len({s.get_span_context().span_id for s in spans}) == 7
        points = captured.data_points()
        assert sum(p.count for p in points) == 7
        assert {s.name for s in spans} >= {
            "POST /api/auth/login",
            "GET /api/tournaments",
            "GET /api/tournaments/{tournament_id}",
            "PUT /api/tournaments/{tournament_id}/questions/{question_id}/prediction",
        }

    def test_the_log_record_carries_the_spans_ids_and_the_response_header(
        self, telemetry_on: Callable[..., Captured]
    ) -> None:
        captured = telemetry_on()
        _login(captured.client)
        response = captured.client.get(f"/api/tournaments/{TOURNAMENT_ID}")

        span = next(
            s for s in captured.span_list() if s.name == "GET /api/tournaments/{tournament_id}"
        )
        record = next(
            r
            for r in captured.log_list()
            if r.log_record.attributes.get("http.route") == "/api/tournaments/{tournament_id}"
        ).log_record
        context = span.get_span_context()
        assert record.trace_id == context.trace_id
        assert record.span_id == context.span_id
        assert response.headers["x-trace-id"] == format(context.trace_id, "032x")
        assert record.attributes["http.response.status_code"] == 200
        assert record.attributes["http.request.method"] == "GET"
        assert set(record.attributes) == {
            "http.request.method",
            "http.route",
            "http.response.status_code",
            "duration_ms",
        }

    def test_probes_and_the_static_frontend_yield_nothing(
        self, telemetry_on: Callable[..., Captured], tmp_path: Path
    ) -> None:
        (tmp_path / "assets").mkdir()
        (tmp_path / "index.html").write_text("<html>app shell</html>")
        (tmp_path / "assets" / "app.js").write_text("console.log(1)")
        captured = telemetry_on(frontend_dir=tmp_path)

        for path in ("/health", "/ready", "/", "/some/client/route", "/assets/app.js", "/docs"):
            captured.client.get(path)

        assert captured.span_list() == []
        assert captured.log_list() == []
        assert captured.data_points() == []
        assert "x-trace-id" not in captured.client.get("/health").headers
        # And an API call still is traced, on the same app.
        assert captured.client.get("/api/tournaments").headers["x-trace-id"]
        assert len(captured.span_list()) == 1

    def test_resource_keys_are_allowlisted(
        self, telemetry_on: Callable[..., Captured], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "OTEL_RESOURCE_ATTRIBUTES",
            "deployment.environment.name=local-demo,host.name=somebox,owner.email=a@b.example",
        )
        captured = telemetry_on()
        captured.client.get("/api/tournaments")

        resource = captured.span_list()[0].resource.attributes
        assert resource["service.name"] == "tennis-test"
        assert resource["deployment.environment.name"] == "local-demo"
        assert "host.name" not in resource
        assert "owner.email" not in resource


class TestStdoutJson:
    def test_one_json_object_per_request_with_the_trace_id(
        self,
        telemetry_on: Callable[..., Captured],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("LOG_FORMAT", "json")
        captured = telemetry_on()
        _login(captured.client)
        capsys.readouterr()

        response = captured.client.get("/api/tournaments")

        lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
        assert len(lines) == 1
        line = lines[0]
        assert line["message"] == "request completed"
        assert line["trace_id"] == response.headers["x-trace-id"]
        assert re.fullmatch(r"[0-9a-f]{16}", line["span_id"])
        assert line["http.route"] == "/api/tournaments"
        assert line["service"] == "tennis-test"
        assert set(line) == {
            "timestamp",
            "level",
            "message",
            "service",
            "trace_id",
            "span_id",
            "http.route",
            "http.request.method",
            "http.response.status_code",
            "duration_ms",
        }
        span = captured.span_list()[-1]
        assert line["trace_id"] == format(span.get_span_context().trace_id, "032x")


class TestPersonalData:
    def test_nothing_personal_is_exported(
        self, telemetry_on: Callable[..., Captured], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EMAIL_PROVIDER", "console")
        tag = uuid.uuid4().hex
        sentinels = {
            "email": f"sentinel-{tag}@example.org",
            "password": f"pw-{tag}-long-enough",
            "name": f"Name-{tag}",
            "probe": f"probe-{tag}",
            "bearer": f"bearer-{tag}",
            "body": f"body-{tag}",
        }
        captured = telemetry_on()
        client = captured.client

        register = client.post(
            "/api/auth/register",
            json={
                "email": sentinels["email"],
                "password": sentinels["password"],
                "displayName": sentinels["name"],
            },
            headers={"Authorization": f"Bearer {sentinels['bearer']}"},
        )
        assert register.status_code == 201, register.text
        steps = _run_journey(client, probe=sentinels["probe"])
        assert steps["put"].status_code == 200
        # A prediction body with a sentinel in a field the server rejects.
        client.put(
            f"/api/tournaments/{TOURNAMENT_ID}/questions/q-1/prediction",
            json={"payload": {"kind": "GENERIC_MATCH_RESULT", "winnerId": sentinels["body"]}},
        )
        session_cookie = next(iter(client.cookies.values()))
        sentinels["cookie"] = session_cookie
        # A failed sign-in with the password in the body.
        client.post(
            "/api/auth/login",
            json={"email": sentinels["email"], "password": sentinels["password"] + "x"},
        )

        text = captured.everything_exported()
        assert captured.span_list(), "the control: something was exported"
        for name, value in sentinels.items():
            assert value not in text, f"{name} sentinel leaked into telemetry"
        assert "203.0.113.9" not in text  # the forwarded client address
        keys = captured.every_attribute_key()
        for part in FORBIDDEN_KEY_PARTS:
            assert not [key for key in keys if part in key.lower()], (part, keys)
        allowed = (
            allowlist.SPAN_KEYS
            | allowlist.METRIC_KEYS
            | allowlist.LOG_KEYS
            | allowlist.RESOURCE_KEYS
        )
        assert keys <= allowed, keys - allowed

    def test_an_unhandled_exception_exports_its_type_and_nothing_else(
        self, telemetry_on: Callable[..., Captured]
    ) -> None:
        sentinel = f"boom-{uuid.uuid4().hex}"
        captured = telemetry_on()

        @captured.app.get("/api/boom")
        def boom() -> None:
            raise RuntimeError(sentinel)

        response = captured.client.get("/api/boom")

        assert response.status_code == 500
        text = captured.everything_exported()
        assert sentinel not in text
        assert "Traceback" not in text
        assert "boom.py" not in text
        span = next(
            s for s in captured.span_list() if "boom" in (s.attributes or {}).get("url.path", "")
        )
        assert span.status.description is None
        events = [e for e in span.events if e.name == "exception"]
        assert events
        assert all(dict(e.attributes) == {"exception.type": "RuntimeError"} for e in events)
        errors = [r for r in captured.log_list() if r.log_record.severity_text == "ERROR"]
        assert len(errors) == 1
        assert dict(errors[0].log_record.attributes) == {"exception.type": "RuntimeError"}
        completed = next(r for r in captured.log_list() if r.log_record.body == "request completed")
        assert completed.log_record.attributes["http.response.status_code"] == 500

    def test_the_console_email_line_is_not_exported(
        self,
        telemetry_on: Callable[..., Captured],
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("EMAIL_PROVIDER", "console")
        address = f"mail-{uuid.uuid4().hex}@example.org"
        captured = telemetry_on()
        capfd.readouterr()

        response = captured.client.post(
            "/api/auth/register",
            json={"email": address, "password": "a-long-enough-password", "displayName": "Probe"},
        )

        assert response.status_code == 201
        # The control: the line is written, to stderr, and it names the address.
        assert address in capfd.readouterr().err
        text = captured.everything_exported()
        assert "[email]" not in text
        assert address not in text
        assert not re.search(r"token\W", text)
        # Even a log call on the root logger stays out of telemetry.
        logging.getLogger().warning("root-%s", address)
        assert address not in captured.everything_exported()

    def test_an_unmatched_route_puts_no_raw_path_in_a_metric_label(
        self, telemetry_on: Callable[..., Captured]
    ) -> None:
        random_part = uuid.uuid4().hex
        captured = telemetry_on()
        _login(captured.client)

        unknown = captured.client.get(f"/api/no-such-route-{random_part}")
        with_id = captured.client.get(f"/api/tournaments/id-{random_part}")

        assert unknown.status_code == 404
        assert with_id.status_code == 404
        points = captured.data_points()
        label_values = {
            str(value) for point in points for value in (point.attributes or {}).values()
        }
        assert not [v for v in label_values if random_part in v]
        routes = {(p.attributes or {}).get("http.route") for p in points}
        assert "/api/tournaments/{tournament_id}" in routes
        assert routes <= {
            None,
            "/api/auth/login",
            "/api/tournaments/{tournament_id}",
        }
        for record in captured.log_list():
            assert random_part not in json.dumps(dict(record.log_record.attributes))
            assert record.log_record.attributes.get("http.route") in routes


class TestUnreachableCollector:
    def test_the_journey_is_unchanged_and_not_slowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Nothing listens on the discard port: a real OTLP exporter, a dead end.
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9")
        monkeypatch.setenv("OTEL_BSP_SCHEDULE_DELAY", "200")
        monkeypatch.setenv("OTEL_METRIC_EXPORT_INTERVAL", "200")
        client = TestClient(create_app(repositories=MemoryRepositories()))

        started = time.perf_counter()
        steps = _run_journey(client)
        elapsed = time.perf_counter() - started

        assert [r.status_code for r in steps.values()] == [200] * 6
        assert "x-trace-id" in steps["login"].headers
        assert elapsed < 10  # generous: the exporters run on their own threads


class TestLayering:
    def test_domain_and_services_do_not_mention_opentelemetry(self) -> None:
        for folder in ("domain", "services", "providers"):
            for path in (REPO / "backend" / "app" / folder).rglob("*.py"):
                assert "opentelemetry" not in path.read_text(), path


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that reads Compose's `!override` and `!reset` tags as plain values."""


def _plain(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_ComposeLoader.add_multi_constructor("!", _plain)


def _yaml(relative: str) -> Any:
    return yaml.load((REPO / relative).read_text(), Loader=_ComposeLoader)


class TestConfiguration:
    def test_collector_pipelines_reference_only_what_is_defined(self) -> None:
        config = _yaml("telemetry/otel-collector.yaml")
        pipelines = config["service"]["pipelines"]
        assert set(pipelines) == {"traces", "metrics", "logs"}
        for name, pipeline in pipelines.items():
            for receiver in pipeline["receivers"]:
                assert receiver in config["receivers"], (name, receiver)
            for processor in pipeline["processors"]:
                assert processor in config["processors"], (name, processor)
            for exporter in pipeline["exporters"]:
                assert exporter in config["exporters"], (name, exporter)
            # Both guard processors, before the batch.
            assert pipeline["processors"][:2] == ["transform/guard", "redaction"], name
            assert pipeline["processors"][-1] == "batch", name
            assert not [e for e in pipeline["exporters"] if e.startswith("debug")], name
        assert "debug" not in config["exporters"]
        assert config["processors"]["redaction"]["blocked_values"]

    def test_the_collector_allowlists_equal_the_apps(self) -> None:
        guard = _yaml("telemetry/otel-collector.yaml")["processors"]["transform/guard"]
        found: dict[tuple[str, str], set[str]] = {}
        for signal in ("trace", "metric", "log"):
            for block in guard[f"{signal}_statements"]:
                for statement in block["statements"]:
                    match = re.fullmatch(r"keep_keys\((\w+)\.attributes, (\[.*\])\)", statement)
                    if match:
                        found[(signal, match.group(1))] = set(json.loads(match.group(2)))
        assert found == {
            ("trace", "resource"): set(allowlist.RESOURCE_KEYS),
            ("trace", "span"): set(allowlist.SPAN_KEYS),
            ("trace", "spanevent"): set(allowlist.SPAN_KEYS),
            ("metric", "resource"): set(allowlist.RESOURCE_KEYS),
            ("metric", "datapoint"): set(allowlist.METRIC_KEYS),
            ("log", "resource"): set(allowlist.RESOURCE_KEYS),
            ("log", "log"): set(allowlist.LOG_KEYS),
        }

    def test_the_overlay_binds_loopback_only_and_pins_images(self) -> None:
        overlay = _yaml("docker-compose.telemetry.yml")
        for name, service in overlay["services"].items():
            for port in service.get("ports", []):
                assert str(port).startswith("127.0.0.1:"), (name, port)
            image = service.get("image")
            if image:
                assert "@sha256:" in image and ":latest" not in image, (name, image)
        assert overlay["services"]["app"]["environment"]["OTEL_EXPORTER_OTLP_ENDPOINT"]

    def test_the_base_compose_file_has_no_telemetry_variable(self) -> None:
        assert "OTEL_" not in (REPO / "docker-compose.yml").read_text()

    def test_prometheus_loki_and_tempo_configs_parse(self) -> None:
        for relative in (
            "telemetry/prometheus.yml",
            "telemetry/loki.yaml",
            "telemetry/tempo.yaml",
        ):
            assert isinstance(_yaml(relative), dict), relative

    def test_the_dashboard_uses_provisioned_datasources(self) -> None:
        datasources = _yaml("telemetry/grafana/provisioning/datasources/datasources.yaml")
        known = {d["uid"] for d in datasources["datasources"]}
        provider = _yaml("telemetry/grafana/provisioning/dashboards/dashboards.yaml")
        assert provider["providers"][0]["options"]["path"]
        dashboards = sorted((REPO / "telemetry/grafana/dashboards").glob("*.json"))
        assert [d.name for d in dashboards] == ["place-a-prediction.json"]
        used: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                datasource = node.get("datasource")
                if isinstance(datasource, dict) and "uid" in datasource:
                    used.add(datasource["uid"])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        board = json.loads(dashboards[0].read_text())
        walk(board)
        assert used
        assert used <= known, used - known
        assert board["title"] == "Place a prediction"

    def test_the_derived_field_and_trace_link_point_at_provisioned_uids(self) -> None:
        datasources = _yaml("telemetry/grafana/provisioning/datasources/datasources.yaml")
        by_uid = {d["uid"]: d for d in datasources["datasources"]}
        assert by_uid["loki"]["jsonData"]["derivedFields"][0]["datasourceUid"] in by_uid
        assert by_uid["tempo"]["jsonData"]["tracesToLogsV2"]["datasourceUid"] in by_uid
