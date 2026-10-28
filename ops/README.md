# Operations evidence

What was done to run this app in production, when, and what was measured. Dates are 2026, times are UTC. Infrastructure details (hosts, addresses, storage names, credentials) are left out on purpose: this repository is public.

| Area | Where | Done | Measured |
|---|---|---|---|
| **Deployment** | [README → Deploy](../README.md#deploy), the [`Promote`](../.github/workflows/promote.yml) runs in Actions | Dev on every push to `main` since 20 Oct; production by hand with an approval since 20 Oct | Production at **https://deuce.kairosworks.dev** · a deploy swaps with about one failed request ([monitoring.md](monitoring.md) §1) |
| **Monitoring and alerting** | [monitoring.md](monitoring.md) (#8) | Container health check, external uptime check, phone alert; production stopped on purpose | Down alert **58 s** after the stop |
| **Backups** | [backups.md](backups.md) (#9) | Nightly dumps off the server; newest one restored without the server (27 Oct) and over the running production database (28 Oct) | Restore in **about 6 min** of work, row counts equal to production · into production: **about 4 min** down, no data lost |
| **Rollback** | [rollback.md](rollback.md) (#10) | Broken commit promoted on purpose, detected, rolled back (27 Oct); rollback approved from the terminal (28 Oct) | Detected in **66 s**, serving again after **7 min 25 s** · terminal approval: dispatch to green in **2 min 56 s** |
| **Diagnosis** | [incident-response/](../incident-response/README.md) (#58), [docs/observability.md](../docs/observability.md) (#56), [docs/alerting.md](../docs/alerting.md) (#57) | Local demo: a 5xx alert starts an on-call agent with logs, traces and the container's output; it opens a pull request with a regression test | Two recorded runs, 23 Oct, in `incident-response/incidents/` |

## Deployment, in more detail

- **Dev** is deployed by the `deploy-dev` job of `CI` on every push to `main` that passes the checks, with the image digest CI built.
- **Production** changes only through `Promote`, for a commit that passed CI and ran on dev, after a human approval. First successful promote: 20 Oct. Production has run commit `1fcda3d` since 21 Oct, apart from the 27 Oct drill ([rollback.md](rollback.md)).
- **Which commit production runs:** the `promote` job's log or summary of the last successful run — not the repository's *Deployments* list ([rollback.md](rollback.md) §5).

## Known gaps, across the files

- Detection covers what `/ready` sees: a fault in one route, with `/ready` at 200, does not alert.
- Nothing alerts if a backup stops being scheduled.
- Diagnosis by the on-call agent is a local demo on the author's machine; it is not wired to production.
