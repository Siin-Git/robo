# Free-Tier Checklist ($0 target)

```text
[ ] Vercel Hobby (frontend)
[ ] Render Free (backend, sleeps when idle — scheduler is independent)
[ ] Neon Free (PostgreSQL mirror until cutover)
[ ] GitHub Actions free allowance (scheduled + CI minutes)
[ ] No paid add-ons
[ ] No custom domain required (provider subdomains)
[ ] No payment method attached anywhere
```

Known free-tier behaviors (not hidden):

- Render free sleeps on idle: first API response may take ~30–60s; the
  frontend shows a loading state and retries (no infinite spinner).
- Neon free suspends when idle: `pool_pre_ping` + small pool (3+2) reconnect.
- GitHub Actions cron may lag several minutes; job timeliness is
  best-effort, financial correctness is never sacrificed for punctuality
  (price-availability engine decides execution, not wall-clock).
- `pg_dump` needs a client in the backup job (installed per-run, free).
