"""Reading a Grafana webhook body into an Incident."""

from __future__ import annotations

import unittest
from datetime import timedelta

from oncall.alerts import BadPayload, Ignored, classify, parse_duration, parse_time
from oncall.incident import BRANCH_PATTERN, Incident, slugify

from .fakes import FIXED_NOW, fixture


class TestClassify(unittest.TestCase):
    def test_a_firing_alert_becomes_an_incident_with_endpoint_and_window(self) -> None:
        incident = classify(fixture("firing.json"), FIXED_NOW)
        self.assertIsInstance(incident, Incident)
        assert isinstance(incident, Incident)
        self.assertEqual(incident.source, "alert")
        self.assertEqual(incident.title, "5xx on the place-a-prediction journey")
        self.assertEqual(
            incident.endpoint, "/api/tournaments/{tournament_id}/questions/{question_id}/prediction"
        )
        start, end = incident.window
        # startsAt 10:14:20 minus the 2m window minus a minute; now plus a minute.
        self.assertEqual(start.isoformat(), "2026-10-23T10:11:20+00:00")
        self.assertEqual(end, FIXED_NOW + timedelta(minutes=1))
        self.assertEqual(incident.key, "23ce3e9960198439@2026-10-23T10:14:20Z")

    def test_facts_are_the_allow_listed_fields_only(self) -> None:
        incident = classify(fixture("firing.json"), FIXED_NOW)
        assert isinstance(incident, Incident)
        names = {name for name, _ in incident.facts}
        self.assertIn("annotation.summary", names)
        self.assertIn("label.http_route", names)
        for absent in ("label.grafana_folder", "annotation.dashboardUid", "valueString", "generatorURL"):
            self.assertNotIn(absent, names)

    def test_names_are_safe_for_folders_and_branches(self) -> None:
        incident = classify(fixture("firing.json"), FIXED_NOW)
        assert isinstance(incident, Incident)
        self.assertEqual(incident.id, "20261023T101500Z-5xx-on-the-place-a-prediction-journey")
        self.assertEqual(incident.branch, "oncall/5xx-on-the-place-a-prediction-journey-20261023T101500Z")
        self.assertRegex(incident.branch, BRANCH_PATTERN)
        self.assertEqual(slugify("../../etc; rm -rf /"), "etc-rm-rf")
        self.assertEqual(slugify("!!!"), "incident")

    def test_ignore_rules(self) -> None:
        self.assertEqual(classify(fixture("hw4-test.json"), FIXED_NOW), Ignored("test notification"))
        self.assertEqual(classify(fixture("grafana-test-button.json"), FIXED_NOW), Ignored("test notification"))
        self.assertIsInstance(classify(fixture("resolved.json"), FIXED_NOW), Ignored)
        self.assertIsInstance(classify(fixture("datasource-error.json"), FIXED_NOW), Ignored)

    def test_a_mixed_notification_takes_the_first_real_firing_alert(self) -> None:
        payload = fixture("firing.json")
        resolved = fixture("resolved.json")["alerts"][0]
        datasource = fixture("datasource-error.json")["alerts"][0]
        payload["alerts"] = [resolved, datasource] + payload["alerts"]
        incident = classify(payload, FIXED_NOW)
        assert isinstance(incident, Incident)
        self.assertEqual(incident.title, "5xx on the place-a-prediction journey")

    def test_bad_bodies(self) -> None:
        for bad in (None, [], "x", {"alerts": None}, {"alerts": [{"labels": "x"}]}):
            with self.assertRaises(BadPayload):
                classify(bad, FIXED_NOW)

    def test_a_missing_window_or_start_falls_back(self) -> None:
        payload = fixture("firing.json")
        del payload["alerts"][0]["annotations"]["window"]
        del payload["alerts"][0]["startsAt"]
        incident = classify(payload, FIXED_NOW)
        assert isinstance(incident, Incident)
        self.assertEqual(incident.window[0], FIXED_NOW - timedelta(minutes=6))

    def test_the_recorded_alert_of_57_gives_its_facts(self) -> None:
        incident = classify(fixture("firing.json"), FIXED_NOW)
        assert isinstance(incident, Incident)
        facts = dict(incident.facts)
        self.assertEqual(facts["label.journey"], "place-a-prediction")
        self.assertEqual(facts["label.kind"], "http-5xx")
        self.assertEqual(facts["annotation.window"], "2m")
        self.assertIn("docs/alerting.md#runbook", facts["annotation.runbook_url"])

    def test_a_start_after_receipt_does_not_invert_the_window(self) -> None:
        payload = fixture("firing.json")
        payload["alerts"][0]["startsAt"] = "2026-10-23T10:20:00Z"  # five minutes after FIXED_NOW
        incident = classify(payload, FIXED_NOW)
        assert isinstance(incident, Incident)
        start, end = incident.window
        self.assertLess(start, end)
        self.assertEqual(start, FIXED_NOW - timedelta(minutes=3))

    def test_an_old_start_is_capped_at_an_hour(self) -> None:
        payload = fixture("firing.json")
        payload["alerts"][0]["startsAt"] = "2026-10-01T00:00:00Z"
        incident = classify(payload, FIXED_NOW)
        assert isinstance(incident, Incident)
        self.assertEqual(incident.window[1] - incident.window[0], timedelta(hours=1))


class TestParsing(unittest.TestCase):
    def test_times(self) -> None:
        self.assertEqual(parse_time("2026-10-22T17:37:50Z").isoformat(), "2026-10-22T17:37:50+00:00")
        self.assertEqual(
            parse_time("2026-10-22T19:37:50.123456789+02:00").isoformat(),
            "2026-10-22T17:37:50.123456+00:00",
        )
        self.assertIsNone(parse_time("0001-01-01T00:00:00Z"))
        self.assertIsNone(parse_time("yesterday"))

    def test_durations(self) -> None:
        self.assertEqual(parse_duration("2m"), timedelta(minutes=2))
        self.assertEqual(parse_duration("1h30m"), timedelta(minutes=90))
        self.assertIsNone(parse_duration("2 minutes"))
        self.assertIsNone(parse_duration(""))


if __name__ == "__main__":
    unittest.main()
