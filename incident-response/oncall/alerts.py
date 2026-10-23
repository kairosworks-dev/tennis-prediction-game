"""The alert entry point: a Grafana webhook body in, an Incident or a reason out.

The body is Grafana's standard webhook JSON (#57): {"status", "alerts": [{
"status", "labels", "annotations", "startsAt", "endsAt", "fingerprint",
"dashboardURL", "panelURL", ...}], ...}. Only the fields named below are read
into facts; the rest is kept in the saved raw payload and nowhere else.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .incident import Incident

#: A test notification: the Homework 4 command (label test="true", alertname
#: ResponderTest) and Grafana's contact-point Test button (alertname TestAlert).
TEST_LABEL = ("test", "true")
TEST_ALERTNAMES = ("ResponderTest", "TestAlert")
#: Grafana's own notifications about a rule it cannot evaluate. Not an
#: application incident (#57: execErrState Error). Ignored.
DATASOURCE_ALERTNAMES = ("DatasourceError", "DatasourceNoData")
DATASOURCE_LABELS = ("grafana_state_reason",)

#: The label that names the endpoint (route template), first match wins.
ROUTE_LABELS = ("http_route", "route", "endpoint")
FACT_LABELS = ("alertname", "journey", "service", "kind", "severity") + ROUTE_LABELS
FACT_ANNOTATIONS = ("summary", "description", "window", "runbook_url")
FACT_MAX = 300

DEFAULT_WINDOW = timedelta(minutes=5)
MARGIN = timedelta(minutes=1)
MAX_WINDOW = timedelta(hours=1)


class BadPayload(Exception):
    """Answered 400: the body is not a webhook this responder understands."""


@dataclass(frozen=True)
class Ignored:
    reason: str


def _alertname(alert: Dict[str, Any]) -> str:
    return str(alert.get("labels", {}).get("alertname", ""))


def is_test(alert: Dict[str, Any]) -> bool:
    labels = alert.get("labels", {})
    return str(labels.get(TEST_LABEL[0], "")).lower() == TEST_LABEL[1] or (
        _alertname(alert) in TEST_ALERTNAMES
    )


def is_datasource_problem(alert: Dict[str, Any]) -> bool:
    labels = alert.get("labels", {})
    return _alertname(alert) in DATASOURCE_ALERTNAMES or any(k in labels for k in DATASOURCE_LABELS)


def _alerts(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
        raise BadPayload("the body has no 'alerts' list")
    alerts = payload["alerts"]
    for alert in alerts:
        if not isinstance(alert, dict):
            raise BadPayload("every entry of 'alerts' must be an object")
        for name in ("labels", "annotations"):
            if name in alert and not isinstance(alert[name], dict):
                raise BadPayload(f"'{name}' must be an object")
    return alerts


_TIME = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)$")


def parse_time(value: Any) -> Optional[datetime]:
    """RFC 3339 as Grafana writes it (Z, an offset, up to nanoseconds)."""
    match = _TIME.match(str(value or "").strip())
    if not match:
        return None
    base, fraction, zone = match.groups()
    text = base + ("." + (fraction + "000000")[:6] if fraction else "")
    text += "+00:00" if zone == "Z" else zone
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.year < 1970:  # Grafana's "0001-01-01T00:00:00Z" means unset
        return None
    return moment.astimezone(timezone.utc)


_DURATION = re.compile(r"(\d+)(h|m|s)")


def parse_duration(value: Any) -> Optional[timedelta]:
    """`2m`, `90s`, `1h30m`, Go-style. None if it is not one."""
    text = str(value or "").strip()
    if not text or _DURATION.sub("", text):
        return None
    seconds = 0
    for amount, unit in _DURATION.findall(text):
        seconds += int(amount) * {"h": 3600, "m": 60, "s": 1}[unit]
    return timedelta(seconds=seconds) if seconds else None


def _short(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= FACT_MAX else text[: FACT_MAX - 3] + "..."


def _key(alert: Dict[str, Any]) -> str:
    fingerprint = str(alert.get("fingerprint") or "")
    if not fingerprint:
        labels = json.dumps(alert.get("labels", {}), sort_keys=True)
        fingerprint = "labels-" + hashlib.sha256(labels.encode()).hexdigest()[:16]
    return f"{fingerprint}@{alert.get('startsAt', '')}"


def classify(payload: Any, now: datetime) -> Union[Ignored, Incident]:
    """Decide what a webhook body is. Raises BadPayload for a 400."""
    alerts = _alerts(payload)
    if not alerts:
        return Ignored("no alerts in the notification")
    if any(is_test(a) for a in alerts):
        return Ignored("test notification")

    default_status = str(payload.get("status", "")).lower()
    firing = [a for a in alerts if str(a.get("status", default_status)).lower() == "firing"]
    if not firing:
        return Ignored("no firing alerts (resolved notification)")

    real = [a for a in firing if not is_datasource_problem(a)]
    if not real:
        return Ignored("datasource error or no data: not an application incident")

    return incident_from_alert(real[0], now, others=len(real) - 1, raw=payload)


def incident_from_alert(
    alert: Dict[str, Any], now: datetime, others: int = 0, raw: Optional[Dict[str, Any]] = None
) -> Incident:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    alertname = _alertname(alert) or "alert"

    endpoint = next((str(labels[k]) for k in ROUTE_LABELS if labels.get(k)), None)
    width = parse_duration(annotations.get("window")) or DEFAULT_WINDOW
    starts_at = parse_time(alert.get("startsAt"))
    end = now + MARGIN
    # A startsAt later than receipt (clock skew) must not invert the window.
    start = min(starts_at or now, now) - width - MARGIN
    if end - start > MAX_WINDOW:
        start = end - MAX_WINDOW

    facts: List[Tuple[str, str]] = [("alertname", _short(alertname))]
    facts += [(f"label.{k}", _short(labels[k])) for k in FACT_LABELS if k in labels and k != "alertname"]
    facts += [(f"annotation.{k}", _short(annotations[k])) for k in FACT_ANNOTATIONS if k in annotations]
    if starts_at:
        facts.append(("startsAt", starts_at.strftime("%Y-%m-%dT%H:%M:%SZ")))
    if alert.get("fingerprint"):
        facts.append(("fingerprint", _short(alert["fingerprint"])))
    if others:
        facts.append(("other firing alerts in the same notification", str(others)))

    return Incident(
        key=_key(alert),
        source="alert",
        title=alertname,
        received_at=now,
        endpoint=endpoint,
        window=(start, end),
        facts=tuple(facts),
        raw=raw if raw is not None else {"alerts": [alert]},
    )
