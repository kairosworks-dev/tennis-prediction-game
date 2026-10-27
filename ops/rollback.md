# Rollback drill and game day (#10)

What was done, when, and the measured result. Dates are 2026, times are UTC.

## 1. Summary

On 27 Oct a deliberately broken commit was promoted to production. The platform's health check passed, so traffic moved to the broken container and `/ready` returned 503. The external uptime check alerted the author's phone **66 s** after the first error. Production was rolled back by promoting the previous commit and served 200 again **7 min 25 s** after the first error. Dev and production ended where they started; the fault was reverted.

## 2. How the fault was made

- **Commit** `e63a8a5` (PR #79, merged as `b6ecd49`): `/ready` returns 503 when the environment variable `DRILL_READY_FAIL` is `1`. `/health` is unchanged.
- **Set on production only**, in the deployment platform, without a redeploy. A running container keeps the environment it started with, so production did not change until the next deploy.
- **Why production only:** `promote` refuses a commit without a successful dev deployment. Dev never had the variable, so dev deployed `b6ecd49` green (`/ready` 200 on the first check) and `verify` accepted it.
- **Why `/health` untouched:** the platform's health check probes `/health`, so it passes and the platform swaps traffic. This is the case the drill is about: healthy, not ready.
- **Cleanup:** variable deleted; fault reverted by PR #80 (`4ced157`), which redeployed dev.

## 3. Timeline (UTC)

Requests were sent to production's `/ready` every 5 s from the author's machine throughout.

| Time | Event |
|---|---|
| 13:08:11 | Promote of `b6ecd49` dispatched |
| 13:09:43 | Production deployment approved |
| 13:09:45 – 13:10:31 | Deploy step's SSH call. The server script exits **0**: the platform reported the deployment finished, the new container healthy |
| 13:10:16 / **13:10:21** | Last 200 / **first 503** |
| **13:11:27** | **Down alert** on the phone |
| 13:10:31 – 13:14:30 | The deploy action's own readiness check: 24 × `/ready`, 10 s apart, all 503 |
| 13:14:33 | Promote job fails: `/ready did not return 200 after 24 attempts` |
| 13:15:08 | Rollback: promote of `1fcda3d` dispatched (`verify` green 13:15:15) |
| 13:17:12 | Production deployment approved |
| 13:17:16 – 13:17:51 | Deploy step's SSH call, exit 0 |
| 13:17:40 / **13:17:46** | Last 503 / **first 200** |
| 13:17:53 | Promote job green. Its log: commit `1fcda3dd64d8…`, digest `sha256:257ef2c6a8b7…` — the baseline read before the drill |
| 13:18:26 | Up alert on the phone |

## 4. Measured

- **Time to detect: 66 s** (first 503 → down alert).
- **Time to recover: 7 min 25 s** (first 503 → first 200):

  | Part | Time |
  |---|---|
  | Detection | 1:06 |
  | Down alert → rollback dispatched | 3:41 |
  | Dispatch → approval | 2:04 |
  | Approval → serving | 0:34 |

  The machines took 1:40, people 5:45 — part of that is the drill's own step-by-step protocol.
- **Deploy time on the server:** the bad image ~38 s from approval to traffic; the rollback 34 s. *Inferred:* the previous image was still on the server, so nothing was pulled.
- The alert channel showed production down for 8 min 59 s.

## 5. Procedure: roll back production

1. **Find the last good commit** in the `promote` job summary of the last successful promote before the bad one. **Not** the repository's Deployments list: it records every production deployment under `main`'s tip — the commit the run started from — so after a rollback it still shows the tip.
2. Dispatch: `gh workflow run promote.yml --ref main -f sha=<last good sha>`.
3. **If a promote is still running, the rollback waits** (one concurrency group, `cancel-in-progress: false`). To skip the wait, cancel the running one with `gh run cancel <run id>` — only once its deploy step's SSH call has returned, so the server script is never cut off. In this drill the stuck run had already failed by itself; no cancel was needed.
4. Approve the production deployment.
5. Confirm: the job summary shows the good commit and digest, `/ready` answers 200, the up alert arrives.

**Dev:** re-run `deploy-dev` from the older CI run; it deploys that run's image digest. A dispatch from `main` redeploys the tip and is not a rollback.

**Not undone by a rollback:** database migrations. A migration runs when the new container starts; the old code then runs against the new schema. There was none between `1fcda3d` and `b6ecd49`.

## 6. What the drill showed

- **A red promote job does not say which version production serves.** Healthy-not-ready: the server script exits 0, traffic has moved, the job fails later on its own readiness checks — the bad version is serving. Never healthy: the job fails and the old version keeps serving. Check production, not the job.
- **Detection covers only what `/ready` sees.** A fault in one route, with `/health` and `/ready` at 200, would not alert at all (known gap, [monitoring.md](monitoring.md)).
- **The uptime check's one-minute cycle** puts detection between ~1 and ~2 min after a fault.

## 7. Actions

- **Rollback command ready in `RUNBOOK.md`**, with where to read the last good commit (#11).
- **Approve from the terminal** — GitHub's pending-deployments API keeps the human approval and removes the browser round trip. *To verify before relying on it* (#11).
- **Candidate, not now:** roll back automatically when `/ready` fails after the swap. Worth it for an app with users and traffic; not for this demo.
