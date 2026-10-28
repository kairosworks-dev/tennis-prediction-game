# Database backups and a timed restore (#9)

What was done, when, and the measured result. Dates are 2026, times are UTC.

## 1. Summary

Production's and dev's Postgres are dumped every night at 02:00 and uploaded to S3-compatible object storage, off the server. On 27 Oct the newest production dump was restored from that storage into an empty Postgres on the author's machine, without the server or the deployment platform. It took **about 6 min** of work from opening the storage console to a checked database, and the restored row counts matched production's.

## 2. The schedule

- **Done:** the deployment platform runs `pg_dump` in Postgres's custom format (a compressed file read by `pg_restore`) for each database, daily at 02:00. Each dump is kept on the server and uploaded to object storage. Retention in object storage: 30 dumps, 30 days or 5 GB.
- **When:** schedules created 19 Oct (dev) and 20 Oct (production). **The upload was off until 21 Oct**: the storage destination was selected but the upload switch was not, so the first dumps existed on the server only and would have been lost with it. Nothing failed, so nothing alerted. Fixed 21 Oct, then one manual backup per database confirmed the upload.
- **Measured:** the production folder in object storage, listed 27 Oct:

  | Dump | Time | Size |
  |---|---|---|
  | `pg-dump-postgres-1792590609.dmp` | 21 Oct 13:50 (manual, after the fix) | 40.17 KB |
  | `pg-dump-postgres-1792634411.dmp` | 22 Oct 02:00 | 40.17 KB |
  | `pg-dump-postgres-1792720808.dmp` | 23 Oct 02:00 | 40.17 KB |
  | `pg-dump-postgres-1792807211.dmp` | 24 Oct 02:00 | 40.17 KB |
  | `pg-dump-postgres-1792893608.dmp` | 25 Oct 02:00 | 40.17 KB |
  | `pg-dump-postgres-1792980010.dmp` | 26 Oct 02:00 | 40.17 KB |
  | `pg-dump-postgres-1793066409.dmp` | 27 Oct 02:00 | 40.16 KB |

  One dump every night since the fix, none missing. The number in the file name is the Unix time of the dump.

## 3. The restore, timed

**Scenario:** the server is gone. Only the copy in object storage is used, restored into a new, empty Postgres 16 (the same major version as production) in a container on the author's machine.

| Time | Step |
|---|---|
| 15:26:18 | Start: storage console opened |
| ~15:30 | Newest production dump (27 Oct 02:00) downloaded |
| 15:32:35 | File checked: 41,128 bytes, starts with `PGDMP` (the custom format's signature) |
| 15:33:09 | Empty Postgres container ready |
| 15:34:19 | `pg_restore` finished without an error |
| **15:34:27** | **Checked: schema and row counts** |

- **Total: 8 min 09 s by the clock, of which about 2.5 min was waiting between steps** (the author was following written instructions). The work itself took about 6 min: about 4 min to find and download the dump, under 2 min for the database steps.
- **Restore command**, into the empty database:

  ```bash
  docker exec -i <container> pg_restore -U postgres -d postgres --no-owner --no-acl --exit-on-error --verbose < pg-dump-postgres-<unix-time>.dmp
  ```

  `--no-owner --no-acl`: a new server does not have production's database roles, so the restore does not try to assign ownership or permissions to them. `--exit-on-error`: stop at the first error instead of finishing with a partial database.
- **Checked:** 14 tables (the app's 13 and `alembic_version`); `alembic_version` is `d2befc9e6a43`, the project's only migration, so the schema is current.
- **Compared with production right after the restore, read-only:**

  | | users | tournaments | predictions |
  |---|---|---|---|
  | Restored (27 Oct 02:00 dump) | 15 | 2 | 169 |
  | Production, at the restore | 15 | 2 | 169 |

  Equal, because nothing was written between 02:00 and the restore. A restore loses every write made after the dump it uses. With one dump a night, that is **up to about 24 h of data** (the recovery point objective, RPO).
- **Cleanup:** the container and the downloaded dump were deleted. The dump holds user data (email addresses, password hashes); no copy was kept outside the backup system.

## 4. What this does not prove

- **Equal counts are not equal content.** Only three tables were counted, and no values were compared. The 27 Oct dump is 10 bytes smaller than the 26 Oct one with the same counts, so some data changed in between.
- ~~**Restoring into the production server**, over the running database, was not done here.~~ Done 28 Oct, section 6.
- **Rebuilding the server itself** is not covered: this restore needs a running Postgres to restore into.

## 5. Known gaps

As of 27 Oct:

- **Nothing alerts if a backup stops being scheduled.** The platform alerts on a failed backup, but a backup that never runs does not fail. A success heartbeat (an alert when the expected "backup done" signal does not arrive) would catch that; it is planned for when the app holds real user data.
- **The backup-failure alert is proven by a test message only**, not by a real failure.
- **The server, its storage keys and the backups are in one account.** Whoever controls the server can delete the backups; object lock (storage that refuses deletes for a set time) is off.

## 6. Restore into the running production database

**Scenario:** data in production is lost or broken, the server is fine. On 28 Oct the newest dump was restored over production's running database by following the written procedure literally, step by step.

| Time | Step |
|---|---|
| 10:34 | Safety dump of the current database (41,128 bytes); row counts read |
| **10:37:10** | App stopped, so nothing writes during the restore |
| 10:38:44 | Down alert on the phone, **94 s** after the stop |
| **10:39:48** | `pg_restore --clean --if-exists --exit-on-error` of the 28 Oct 02:00 dump finished without an error |
| ~10:40 | Schema and counts checked; app started, healthy after 30 s |
| **10:41:40** | Up alert on the phone |

- **Downtime: about 4 min** (stop to up alert, 4 min 30 s, an upper bound: the up alert lags by up to a minute).
- **Checked:** `alembic_version` `d2befc9e6a43`; users / tournaments / predictions **15 / 2 / 169**, before and after; `/ready` 200; a demo login works, which `/ready` does not test.
- **Data lost: none**, because nothing was written after 02:00. The safety dump would have held any later writes.
- **What went wrong:** only typing. A placeholder left in a command, and a character copied with the container name, made three attempts at the safety dump fail before the fourth worked; a failed dump left an empty file behind. The procedure now prints the bare name and warns about both.
- **Cleanup:** the downloaded dump, its copy on the server and the safety dump were deleted after the checks.
