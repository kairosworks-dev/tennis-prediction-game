"""A stand-in for the coding agent CLI, started by the responder in the tests.

Records its argv, cwd, environment and stdin to --record, then behaves as told:
prints a stream-json result carrying --result, sleeps --sleep seconds, exits
with --exit. Every other argument (the real CLI's flags) is accepted and kept
in the record. It never touches the network or a repository.
"""

import json
import os
import sys
import time


def main() -> int:
    args = sys.argv[1:]

    def value(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    record = value("--record")
    result = value("--result", "")
    sleep = float(value("--sleep", "0"))
    code = int(value("--exit", "0"))
    form = value("--form", "stream")
    stdin = sys.stdin.read()

    incident_dir = value("--add-dir")
    write_refused = None
    if incident_dir:
        try:
            with open(os.path.join(incident_dir, "agent-was-here.txt"), "w") as handle:
                handle.write("x")
            write_refused = False
        except OSError:
            write_refused = True
        try:
            with open(os.path.join(incident_dir, "prompt.txt"), "a") as handle:
                handle.write("x")
            prompt_write_refused = False
        except OSError:
            prompt_write_refused = True
    else:
        prompt_write_refused = None

    child_pid = None
    if "--spawn-child" in args:
        import subprocess

        child_pid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]).pid

    if record:
        with open(record, "w") as handle:
            json.dump(
                {
                    "argv": sys.argv,
                    "cwd": os.getcwd(),
                    "env": dict(os.environ),
                    "stdin": stdin,
                    "pid": os.getpid(),
                    "child_pid": child_pid,
                    "incident_write_refused": write_refused,
                    "prompt_write_refused": prompt_write_refused,
                },
                handle,
            )

    if form == "stream":
        print(json.dumps({"type": "system", "subtype": "init"}), flush=True)
        print(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "Looking at the traceback."}]},
                }
            ),
            flush=True,
        )
    for index, arg in enumerate(args):
        if arg == "--extra-line" and index + 1 < len(args):
            print(args[index + 1], flush=True)
    if sleep:
        time.sleep(sleep)
    if form == "stream":
        print(
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "result": f"I wrote a test and fixed it.\n{result}" if result else "Done.",
                    "permission_denials": [
                        {"tool_name": "Bash", "tool_use_id": "t1", "tool_input": {"command": "git log"}}
                    ],
                }
            ),
            flush=True,
        )
    else:
        print(f"Plain text output.\n{result}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
