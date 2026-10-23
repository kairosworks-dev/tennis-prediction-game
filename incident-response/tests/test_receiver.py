"""POST /alerts over real HTTP on an ephemeral loopback port, with fake seams.

Each "changes nothing" case asserts: no incident folder, no worktree, no
branch, no agent process (the fake agent writes its record only when run).
"""

from __future__ import annotations

import copy
import http.client
import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

from oncall.receiver import make_server
from oncall.runner import Responder

from .fakes import FIXED_NOW, RESPONDER, TEST_BEARER, FakeCommands, FakeHttp, Layout, fixture


class ReceiverCase(Layout):
    def start(self, agent_extra: str = "", **settings_overrides: Any) -> None:
        if agent_extra:
            settings_overrides["agent_cmd"] = self.agent_cmd(extra=agent_extra)
        self.cfg = self.settings(**settings_overrides)
        self.commands = FakeCommands(self.main)
        self.http = FakeHttp()
        self.log = open(self.tmp / "responder.log", "w+")
        self.addCleanup(self.log.close)
        self.responder = Responder(
            self.cfg, http=self.http, commands=self.commands, clock=lambda: FIXED_NOW, out=self.log
        )
        self.server = make_server(self.cfg, self.responder, port=0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(
        self,
        body: Any,
        token: Optional[str] = TEST_BEARER,
        content_type: str = "application/json",
        raw: Optional[bytes] = None,
        path: str = "/alerts",
    ) -> Tuple[int, Dict[str, Any]]:
        host, port = self.server.server_address[:2]
        connection = http.client.HTTPConnection(host, port, timeout=10)
        headers = {"Content-Type": content_type}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        data = raw if raw is not None else json.dumps(body).encode()
        connection.request("POST", path, body=data, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read() or b"{}")
        connection.close()
        return response.status, payload

    def log_text(self) -> str:
        self.log.flush()
        return (self.tmp / "responder.log").read_text()


class TestRefusals(ReceiverCase):
    def setUp(self) -> None:
        super().setUp()
        self.start()

    def test_it_listens_on_loopback_only(self) -> None:
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_a_body_that_is_not_json_by_content_type_is_415(self) -> None:
        status, body = self.post(fixture("firing.json"), content_type="text/plain")
        self.assertEqual(status, 415)
        self.assert_nothing_started(self.commands)

    def test_415_comes_before_the_token_check(self) -> None:
        status, _ = self.post(fixture("firing.json"), token=None, content_type="application/x-www-form-urlencoded")
        self.assertEqual(status, 415)

    def test_a_missing_token_is_401(self) -> None:
        status, _ = self.post(fixture("firing.json"), token=None)
        self.assertEqual(status, 401)
        self.assert_nothing_started(self.commands)

    def test_a_wrong_token_is_401(self) -> None:
        status, _ = self.post(fixture("firing.json"), token=TEST_BEARER + "-not")
        self.assertEqual(status, 401)
        self.assert_nothing_started(self.commands)

    def test_401_comes_before_the_body_is_read(self) -> None:
        status, _ = self.post(None, token="wrong", raw=b"{not json")
        self.assertEqual(status, 401)

    def test_invalid_json_is_400(self) -> None:
        status, body = self.post(None, raw=b"{not json")
        self.assertEqual(status, 400)
        self.assertIn("not valid JSON", body["message"])
        self.assert_nothing_started(self.commands)

    def test_a_body_without_an_alerts_list_is_400(self) -> None:
        for bad in ({"status": "firing"}, {"alerts": "nope"}, [1, 2], {"alerts": [1]}):
            status, _ = self.post(bad)
            self.assertEqual(status, 400, bad)
        self.assert_nothing_started(self.commands)

    def test_another_path_is_404_and_a_get_is_405(self) -> None:
        status, _ = self.post(fixture("firing.json"), path="/other")
        self.assertEqual(status, 404)
        host, port = self.server.server_address[:2]
        connection = http.client.HTTPConnection(host, port, timeout=10)
        connection.request("GET", "/alerts")
        self.assertEqual(connection.getresponse().status, 405)
        connection.close()

    def test_the_log_names_the_method_and_path_actually_sent(self) -> None:
        self.post(fixture("firing.json"), path="/other?x=1")
        host, port = self.server.server_address[:2]
        connection = http.client.HTTPConnection(host, port, timeout=10)
        connection.request("GET", "/alerts")
        connection.getresponse().read()
        connection.close()
        log = self.log_text()
        self.assertIn("POST /other -> 404", log)
        self.assertIn("GET /alerts -> 405", log)
        self.assertNotIn("x=1", log)

    def test_no_header_is_saved_or_logged(self) -> None:
        self.post(fixture("firing.json"), token=TEST_BEARER + "-not")
        self.post(fixture("firing.json"))
        self.responder.join(30)
        self.assertNotIn(TEST_BEARER, self.log_text())
        for folder in self.incident_folders():
            for item in folder.iterdir():
                text = item.read_text(errors="replace")
                self.assertNotIn(TEST_BEARER, text, item.name)
                self.assertNotIn("Authorization", text, item.name)


class TestIgnored(ReceiverCase):
    def setUp(self) -> None:
        super().setUp()
        self.start()

    def test_the_homework_4_test_notification_changes_nothing(self) -> None:
        status, body = self.post(fixture("hw4-test.json"))
        self.assertEqual(status, 200)
        self.assertEqual(body["message"], "ignored: test notification")
        self.assert_nothing_started(self.commands)

    def test_grafanas_test_button_changes_nothing(self) -> None:
        # PROVISIONAL fixture: Grafana's documented test notification, to be
        # replaced by the body captured from the contact point's Test button.
        status, body = self.post(fixture("grafana-test-button.json"))
        self.assertEqual(status, 200)
        self.assertEqual(body["message"], "ignored: test notification")
        self.assert_nothing_started(self.commands)

    def test_a_test_label_on_a_real_looking_alert_is_still_a_test(self) -> None:
        payload = fixture("firing.json")
        payload["alerts"][0]["labels"]["test"] = "true"
        status, body = self.post(payload)
        self.assertEqual((status, body["reason"]), (200, "test notification"))
        self.assert_nothing_started(self.commands)

    def test_a_resolved_only_notification_changes_nothing(self) -> None:
        status, body = self.post(fixture("resolved.json"))
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ignored")
        self.assertIn("resolved", body["reason"])
        self.assert_nothing_started(self.commands)

    def test_a_datasource_error_changes_nothing(self) -> None:
        status, body = self.post(fixture("datasource-error.json"))
        self.assertEqual(status, 200)
        self.assertIn("datasource", body["reason"])
        self.assert_nothing_started(self.commands)

    def test_datasource_no_data_and_the_state_reason_label_are_ignored(self) -> None:
        for change in ({"alertname": "DatasourceNoData"}, {"grafana_state_reason": "Error"}):
            payload = fixture("firing.json")
            payload["alerts"][0]["labels"].update(change)
            status, body = self.post(payload)
            self.assertEqual((status, body["status"]), (200, "ignored"), change)
        self.assert_nothing_started(self.commands)

    def test_an_empty_alerts_list_changes_nothing(self) -> None:
        status, body = self.post({"alerts": []})
        self.assertEqual((status, body["status"]), (200, "ignored"))
        self.assert_nothing_started(self.commands)


class TestAccepted(ReceiverCase):
    def test_a_firing_alert_is_answered_202_at_once_and_runs_in_the_background(self) -> None:
        self.start(agent_extra="--sleep 2")
        began = time.monotonic()
        status, body = self.post(fixture("firing.json"))
        elapsed = time.monotonic() - began
        self.assertEqual(status, 202)
        self.assertEqual(body["status"], "accepted")
        self.assertLess(elapsed, 1.5, "the webhook must not wait for the agent")
        self.assertEqual(body["incident"], "20261022T173830Z-prediction-submit-5xx")
        self.responder.join(30)
        self.assertEqual(self.responder.last_result.outcome, "published")
        self.assertIsNotNone(self.agent_record())

    def test_a_second_alert_while_a_run_is_in_progress_is_busy_and_logged(self) -> None:
        self.start(agent_extra="--sleep 3")
        first, _ = self.post(fixture("firing.json"))
        other = fixture("firing.json")
        other["alerts"][0]["fingerprint"] = "another-incident"
        status, body = self.post(other)
        self.assertEqual(first, 202)
        self.assertEqual((status, body["status"]), (200, "busy"))
        self.assertIn("busy", self.log_text())
        self.responder.join(30)
        self.assertEqual(len(self.incident_folders()), 1)
        self.assertEqual(sum(1 for a in self.commands.argvs() if a[3:5] == ["worktree", "add"]), 1)

    def test_a_repeat_of_the_same_incident_after_its_run_is_a_duplicate(self) -> None:
        self.start()
        self.post(fixture("firing.json"))
        self.responder.join(30)
        os.remove(self.record)
        status, body = self.post(fixture("firing.json"))
        self.assertEqual((status, body["status"]), (200, "duplicate"))
        self.assertEqual(len(self.incident_folders()), 1)
        self.assertIsNone(self.agent_record())

    def test_a_new_startsat_is_a_new_incident(self) -> None:
        self.start()
        self.post(fixture("firing.json"))
        self.responder.join(30)
        later = copy.deepcopy(fixture("firing.json"))
        later["alerts"][0]["startsAt"] = "2026-10-22T19:00:00Z"
        status, _ = self.post(later)
        self.responder.join(30)
        self.assertEqual(status, 202)
        self.assertEqual(len(self.incident_folders()), 2)

    def test_the_saved_payload_is_the_body_and_nothing_else(self) -> None:
        self.start()
        payload = fixture("firing.json")
        self.post(payload)
        self.responder.join(30)
        folder = self.incident_folders()[0]
        self.assertEqual(json.loads((folder / "alert.json").read_text()), payload)


class TestStartup(Layout):
    def run_module(self, environ: Dict[str, str]) -> subprocess.CompletedProcess:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.tmp)}
        env.update(environ)
        return subprocess.run(
            [sys.executable, "-m", "oncall"], cwd=str(RESPONDER), env=env,
            capture_output=True, text=True, timeout=30,
        )

    def test_it_refuses_to_start_without_a_token(self) -> None:
        done = self.run_module({})
        self.assertEqual(done.returncode, 2)
        self.assertIn("RESPONDER_TOKEN is not set", done.stderr)

    def test_it_refuses_a_short_token(self) -> None:
        done = self.run_module({"RESPONDER_TOKEN": "short"})
        self.assertEqual(done.returncode, 2)

    def test_it_refuses_an_agent_command_that_switches_a_guardrail_off(self) -> None:
        for flag in ("--bare", "--dangerously-skip-permissions", "--safe-mode", "--restricted",
                     "--permission-mode=bypassPermissions"):
            done = self.run_module({"RESPONDER_TOKEN": TEST_BEARER, "RESPONDER_AGENT_CMD": f"claude -p {flag}"})
            self.assertEqual(done.returncode, 2, flag)
            self.assertIn("Refusing to start", done.stderr)


class TestSettingsFileCheck(Layout):
    """14b: a broken agent-settings.json stops the start, loudly."""

    def start_with(self, content: Optional[str]) -> Tuple[int, str]:
        import io
        from contextlib import redirect_stderr
        from unittest import mock

        from oncall import __main__ as entry

        path = self.main / "incident-response" / "agent-settings.json"
        if content is None:
            path.unlink()
        else:
            path.write_text(content)
        err = io.StringIO()
        with mock.patch.object(entry.config, "load", return_value=self.settings()), \
                mock.patch.object(entry, "make_server", side_effect=AssertionError("must not listen")), \
                redirect_stderr(err):
            code = entry.main()
        return code, err.getvalue()

    def test_a_missing_file_refuses_the_start(self) -> None:
        code, err = self.start_with(None)
        self.assertEqual(code, 2)
        self.assertIn("missing", err)

    def test_invalid_json_refuses_the_start(self) -> None:
        code, err = self.start_with('{"permissions": {"allow": [}')
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_missing_rule_lists_refuse_the_start(self) -> None:
        for content in ("[]", "{}", '{"permissions": {"allow": []}}',
                        '{"permissions": {"allow": "Read", "deny": []}}',
                        '{"permissions": {"allow": [], "deny": [1]}}'):
            code, err = self.start_with(content)
            self.assertEqual(code, 2, content)
            self.assertIn("Refusing to start", err)

    def test_the_shipped_file_passes(self) -> None:
        from oncall import config as cfg

        cfg.check_agent_settings(RESPONDER / "agent-settings.json")
