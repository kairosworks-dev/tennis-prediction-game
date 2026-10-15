# Extension pack demo

The six-step demo script from the course's Module 5, run for real in this repository. Each step is filled in from an actual session, with the date; nothing here is invented. Steps still marked *pending* arrive with the issue named.

| Step | What is shown | Status |
|---|---|---|
| 1 | The agent reads the project instructions (`AGENTS.md`) | pending, recorded with #17 |
| 2 | A reusable workflow is invoked (`implement-issue`) | pending, first real issue run |
| 3 | The API reviewer subagent reviews an API change | pending, first contract-touching PR |
| 4 | The agent calls an MCP tool | pending, #15 |
| 5 | A hook blocks an action | **done 15 Oct 2026**, below |
| 6 | The author reviews the final diff | pending, recorded with #17 |

## Step 5 — the commit gate blocks a commit (15 Oct 2026)

A throwaway file with three things that must never be committed was staged: a public IP address, a private key header and one name from the author's private pattern list. Then `git commit` was run.

```
$ git commit -m "test: should be blocked"
commit-gate: docs/throwaway.md  (ipv4 address)
commit-gate: docs/throwaway.md  (private key block)
commit-gate: docs/throwaway.md  (private pattern)
commit-gate: blocked. Remove the content above (or move it out of the public repo) and commit again.
$ echo $?
1
```

No commit was created. The same gate, called through the coding agent's pre-tool hook with a fake `git commit --no-verify`, answered:

```
commit-gate: --no-verify is not allowed in this repository.
exit 2
```

The real changes of the day, staged together, passed the gate without a hit. Mechanism: `agent-hooks/README.md`; what it does and does not cover: `docs/permissions.md`.
