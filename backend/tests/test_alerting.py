"""The alert on user impact (#57) is configuration; these tests keep its files
consistent with each other and with the code they refer to.

They read the provisioning files, the dashboard, the compose overlay and the
docs, and check that the rule, the dashboard and the app agree on the same six
routes, the same panel and the same uid. The behaviour (4xx quiet, one 5xx
fires, it resolves) is proven by `make telemetry-alert-demo`, which needs Docker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.main import create_app
from app.repositories.memory import MemoryRepositories

REPO = Path(__file__).resolve().parents[2]
ALERTING = "telemetry/grafana/provisioning/alerting"


class _Loader(yaml.SafeLoader):
    """SafeLoader that reads Compose's `!override` and `!reset` tags as plain values."""


def _plain(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_Loader.add_multi_constructor("!", _plain)


def _yaml(relative: str) -> Any:
    return yaml.load((REPO / relative).read_text(), Loader=_Loader)


@pytest.fixture(scope="module")
def rule() -> dict[str, Any]:
    groups = _yaml(f"{ALERTING}/rules.yaml")["groups"]
    assert len(groups) == 1 and len(groups[0]["rules"]) == 1
    return groups[0]


@pytest.fixture(scope="module")
def dashboard() -> dict[str, Any]:
    return json.loads((REPO / "telemetry/grafana/dashboards/place-a-prediction.json").read_text())


def _query(group: dict[str, Any]) -> str:
    (query,) = [d for d in group["rules"][0]["data"] if d["refId"] == "A"]
    return query["model"]["expr"]


def _route_selector(expr: str) -> str:
    """The journey's route regex: the `http_route=~"..."` that is not `$route`."""
    selectors = [s for s in re.findall(r'http_route=~"([^"]*)"', expr) if s != "$route"]
    assert len(selectors) == 1, selectors
    return selectors[0]


def _panel(dashboard: dict[str, Any], panel_id: int) -> dict[str, Any]:
    return next(p for p in dashboard["panels"] if p["id"] == panel_id)


def _journey_routes() -> list[str]:
    text = (REPO / "docs/observability.md").read_text()
    section = text.split("## The journey", 1)[1].split("\n## ", 1)[0]
    routes = re.findall(r"^\d+\. `(?:GET|POST|PUT) (/api/\S+)`", section, flags=re.MULTILINE)
    assert len(routes) == 6, routes
    return routes


class TestRule:
    def test_timings_and_states_are_in_the_file(self, rule: dict[str, Any]) -> None:
        assert rule["interval"] == "10s"
        body = rule["rules"][0]
        assert body["for"] == "0s"
        assert body["noDataState"] == "OK"
        assert body["execErrState"] == "Error"
        assert body["isPaused"] is False

    def test_labels_and_annotations(self, rule: dict[str, Any]) -> None:
        body = rule["rules"][0]
        assert body["labels"] == {
            "journey": "place-a-prediction",
            "service": "tennis-prediction-game",
            "kind": "http-5xx",
            "severity": "page",
        }
        annotations = body["annotations"]
        for key in ("summary", "description", "window", "runbook_url"):
            assert annotations[key], key
        assert annotations["window"] == "2m"
        assert "{{ $labels.http_route }}" in annotations["description"]

    def test_the_expression_counts_5xx_per_route_in_the_window(self, rule: dict[str, Any]) -> None:
        expr = _query(rule)
        assert expr.startswith("sum by (http_route) (increase(")
        assert 'http_response_status_code=~"5.."' in expr
        assert expr.rstrip().endswith("[2m]))")
        assert "http_server_request_duration_seconds_count" in expr

    def test_the_condition_is_any_above_zero(self, rule: dict[str, Any]) -> None:
        body = rule["rules"][0]
        assert body["condition"] == "C"
        (threshold,) = [d for d in body["data"] if d["refId"] == "C"]
        (condition,) = threshold["model"]["conditions"]
        assert condition["evaluator"] == {"type": "gt", "params": [0]}

    def test_the_datasource_is_the_provisioned_prometheus(self, rule: dict[str, Any]) -> None:
        datasources = _yaml("telemetry/grafana/provisioning/datasources/datasources.yaml")
        known = {d["uid"]: d["type"] for d in datasources["datasources"]}
        (query,) = [d for d in rule["rules"][0]["data"] if d["refId"] == "A"]
        assert known[query["datasourceUid"]] == "prometheus"
        assert query["model"]["datasource"]["uid"] == query["datasourceUid"]

    def test_the_links_point_at_the_errors_panel_of_the_dashboard(
        self, rule: dict[str, Any], dashboard: dict[str, Any]
    ) -> None:
        annotations = rule["rules"][0]["annotations"]
        assert annotations["__dashboardUid__"] == dashboard["uid"]
        panel = _panel(dashboard, int(annotations["__panelId__"]))
        assert panel["title"] == "Errors by route and status"

    def test_the_runbook_link_names_a_section_that_exists(self, rule: dict[str, Any]) -> None:
        url = rule["rules"][0]["annotations"]["runbook_url"]
        assert url.endswith("/blob/main/docs/alerting.md#runbook")
        headings = re.findall(r"^## (.+)$", (REPO / "docs/alerting.md").read_text(), re.MULTILINE)
        assert "Runbook" in headings


class TestRouteSelector:
    def test_rule_and_dashboard_panel_use_the_same_expression(
        self, rule: dict[str, Any], dashboard: dict[str, Any]
    ) -> None:
        panel_expr = _panel(dashboard, 3)["targets"][0]["expr"]
        assert _route_selector(_query(rule)) == _route_selector(panel_expr)

    def test_the_selector_is_the_six_routes_of_the_docs(self, rule: dict[str, Any]) -> None:
        # Prometheus anchors a regex match, so a full match is what it does.
        pattern = re.compile(_route_selector(_query(rule)))
        routes = _journey_routes()
        assert all(pattern.fullmatch(route) for route in routes)
        assert set(pattern.pattern.split("|")) == set(routes)
        # Routes next to the journey are not part of it.
        assert not pattern.fullmatch("/api/tournaments/{tournament_id}/draws")
        assert not pattern.fullmatch("/api/auth/register")

    def test_the_selector_uses_the_code_templates_which_exist(self, rule: dict[str, Any]) -> None:
        app = create_app(seed=False, repositories=MemoryRepositories())
        paths = set(app.openapi()["paths"])  # the code's templates, as the metric labels them
        for route in _route_selector(_query(rule)).split("|"):
            assert route in paths, route
        assert "{questionId}" not in _query(rule)


class TestNotification:
    def test_the_contact_point_is_a_webhook_to_responder_url(self) -> None:
        (point,) = _yaml(f"{ALERTING}/contact-points.yaml")["contactPoints"]
        (receiver,) = point["receivers"]
        assert receiver["type"] == "webhook"
        assert receiver["settings"]["url"] == "${RESPONDER_URL}"
        assert receiver["settings"]["httpMethod"] == "POST"
        assert receiver["disableResolveMessage"] is False

    def test_the_policy_sends_everything_there_without_waiting(self) -> None:
        (point,) = _yaml(f"{ALERTING}/contact-points.yaml")["contactPoints"]
        (policy,) = _yaml(f"{ALERTING}/policies.yaml")["policies"]
        assert policy["receiver"] == point["name"]
        assert policy["group_wait"] == "0s"
        assert policy["group_interval"] == "1m"
        assert policy["repeat_interval"] == "12h"
        assert "http_route" in policy["group_by"]

    def test_the_grafana_service_is_wired_for_it(self) -> None:
        grafana = _yaml("docker-compose.telemetry.yml")["services"]["grafana"]
        env = grafana["environment"]
        assert env["GF_SERVER_ROOT_URL"] == "http://localhost:3000"
        assert env["RESPONDER_URL"] == "${RESPONDER_URL:-http://host.docker.internal:8001/alerts}"
        assert "host.docker.internal:host-gateway" in grafana["extra_hosts"]
        mount = f"./{ALERTING}:/etc/grafana/provisioning/alerting:ro"
        assert mount in grafana["volumes"]

    def test_prometheus_injects_a_zero_so_the_first_5xx_counts(self) -> None:
        # Without it a brand-new 5xx series has one sample and increase() says 0.
        command = _yaml("docker-compose.telemetry.yml")["services"]["prometheus"]["command"]
        assert "--enable-feature=created-timestamp-zero-ingestion" in command
        assert "--web.enable-otlp-receiver" in command

    def test_the_alerting_files_are_not_in_the_default_stack(self) -> None:
        text = (REPO / "docker-compose.yml").read_text()
        assert "RESPONDER_URL" not in text and "alerting" not in text
