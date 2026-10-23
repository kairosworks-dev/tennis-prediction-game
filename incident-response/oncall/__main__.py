"""`make responder`: python3 -m oncall, from incident-response/."""

from __future__ import annotations

import sys

from . import config
from .receiver import make_server
from .runner import Responder


def main() -> int:
    try:
        settings = config.load()
    except config.ConfigError as error:
        print(f"responder: {error}", file=sys.stderr)
        return 2
    for required in (settings.settings_file, settings.mandate_file, settings.pr_template):
        if not required.is_file():
            print(f"responder: {required.name} is missing next to the responder", file=sys.stderr)
            return 2

    responder = Responder(settings)
    try:
        server = make_server(settings, responder)
    except OSError as error:
        print(f"responder: cannot listen on {config.HOST}:{settings.port}: {error}", file=sys.stderr)
        return 2

    responder.log(f"listening on http://{config.HOST}:{settings.port}/alerts (loopback only)")
    responder.log(f"base ref {settings.base_ref}; worktrees under {settings.worktree_dir}")
    responder.log(f"incidents under {settings.incidents_dir}")
    responder.log(f"Loki {settings.loki_url}, Tempo {settings.tempo_url}; time limit {settings.timeout_min:g} min")
    responder.log(f"agent: {settings.agent_cmd.split()[0]} (RESPONDER_AGENT_CMD)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        responder.log("stopping")
        if responder.current:
            responder.log(f"a run ({responder.current}) is still in progress; the agent is stopped")
            responder.agent.stop()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
