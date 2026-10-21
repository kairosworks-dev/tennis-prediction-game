# Monitoring and alerting (#8)

What was done, when, and the measured result. Dates are 2026, times are UTC.

## 1. Container health check

- **Done:** the deployment platform runs the app's probe `python -m app.healthcheck` (GET `/health`, exit 0 only on 200) every 5 s, on dev and production. A deploy now waits for the new container to report healthy before it replaces the old one. The image's own `HEALTHCHECK` runs the same module every 30 s. Why a module rather than an inline command: PR #71.
- **When:** 21 Oct.
- **Measured:** before, about 30–50 s of 503 per deploy. After, with requests sent throughout one deploy on each environment: dev answered 267 × 200 and one 502 at the swap; production 272 × 200 and one request without an answer. The new container was healthy after 32 s (dev) and 20 s (production).

## 2. External uptime check

- **Done:** an external service polls production's `/ready` (which includes the database) every minute from 4 locations on 3 continents. "Down" means 3 of 4 locations agree after 2 tries. The certificate and hostname are verified.
- **When:** 21 Oct.
- **Measured:** up since 21 Oct, apart from the deliberate failure in section 3.

## 3. Phone alert and the deliberate failure test

- **Done:** one channel, a messaging app on the author's phone, receives the uptime alerts and the platform's failure events (deployment, backup, disk). Policy: only events that need action now reach it; reminders go elsewhere. Tested by stopping production on purpose.
- **When:** 21 Oct.
- **Measured:** production stopped at 19:16:44 → down alert at 19:17:42 → redeployed, serving at 19:18:49 → up alert at 19:19:34. About 2 min down; the down alert arrived 58 s after the stop.
- **Test messages**, as received on the phone (monitor name and host replaced; the messages show local time, UTC+02:00):

  ```text
  🔴 <monitor> is now DOWN
  Target: <production host>/ready
  Noticed at: 2026-10-21 21:17:42 (UTC+02:00)
  Encountered errors:
  New York: HTTP code 503
  London: HTTP code 503
  Frankfurt: HTTP code 503
  Singapore: HTTP code 503
  ```

  ```text
  🟢 <monitor> is now UP
  Downtime: 2 min
  Target: <production host>/ready
  Noticed at: 2026-10-21 21:19:34 (UTC+02:00)
  ```

## 4. Known gaps

As of 22 Oct:

- The monitor itself can fail: its own dashboard was offline for hours on 21 Oct.
- The backup-failure alert is proven by a test message only, not by a real failure.
- Certificate expiry is caught on the day it happens, not before.
- Nothing alerts if a backup stops being scheduled: there is no success heartbeat.
