---
name: review-api-change
description: Review the current branch's API change against openapi.yaml with the read-only api-reviewer subagent. Use before opening a PR that touches the contract, the backend routers or the frontend service layer.
---

Launch the `api-reviewer` subagent on the current branch and relay its report verbatim, with its final `API review: PASS` or `FAIL` line. Do not review yourself, and do not edit anything on the strength of the report: a `FAIL` goes back to the engineer as input, exactly like a QA `FAIL` in `docs/process.md`.
