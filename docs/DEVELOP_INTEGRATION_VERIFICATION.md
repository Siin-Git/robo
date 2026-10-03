# Develop integration verification — 2026-10-03

## Scope and acceptance

The user requested integrating completed work into develop and testing it before
starting the broader graph/ledger data-source unification. The baseline is
origin/develop 0366279 (PR #13 already merged); local operation commits 4b791c5,
24ed042 and 3e02c26 are integrated without rewriting their history.

Acceptance: the combined code passes backend, frontend and browser checks; the
completed local-operation changes become available on develop. Existing working
copies, running local operation, its data and scheduler remain in place.
Main, provider deployments, remote operating databases and separately owned
backup PR #12 are outside this action. Graph/ranking data-source unification is
the next feature, not part of this merge.

## Integration and test correction

A separate disposable checkout merged develop with feat/local-forward-operation
without conflicts. It reuses the existing dependency versions with unchanged
requirements and frontend lockfile.

The first whole-suite PostgreSQL run exposed a test-order problem: the API test
created an unversioned schema with metadata.create_all(), so the later Alembic
test failed on existing tables. The API test now initializes its disposable
database through Alembic, matching the deployment path. No product schema or
financial calculation was changed by this correction.

## Executed verification

| Check | Result |
| --- | --- |
| Python 3.11 complete suite, three freshly created disposable PostgreSQL 14 databases | **477 passed**, no skipped tests, 16 dependency deprecation warnings |
| Frontend unit tests | **59 passed / 12 files** |
| Next production build | Passed, including lint and type validation |
| Standalone TypeScript check | Passed |
| Chrome Monday scenario | Passed: current/pending decisions, two observations retained, truthful new-history shortage, previous history, aligned contribution/reference periods, mobile width and no page errors |
| Chrome complete operation flow | Passed: login, setup/Frontier, confirm, KEEP, ADJUST/new version, synthetic fixture ledger/history, review and second-user isolation |
| Diff whitespace check | Passed |

Commands used were python -m pytest -q (with the three TEST_*DATABASE_URL values
pointing only to a newly created loopback PostgreSQL server), npm test,
npm run build, tsc --noEmit and the repository's Playwright operations config
for monday-demo and operations-review. Browser servers used fresh isolated
SQLite directories and unused ports. The full operation browser check used
the new local-operation launcher but no LaunchAgent was installed for tests.

Test-generated DB reports, covariance caches and Next configuration edits are
excluded from the integration commit. Disposable PostgreSQL and browser servers
are stopped after checking. Operating data and the existing user's scheduler
were not used for tests or reconfigured.

## Meaning and remaining work

These checks establish the combined implementation and local integration state.
The browser series are explicitly synthetic fixtures. They do not establish
production deployment, real future scheduled execution or realized long-term
returns. The existing ranking/participant replay paths, expected/actual
comparison limits and benchmark-definition gaps remain documented in the
previous handoffs. Backup PR #12 follow-up remains independently required
before treating the scheduled production backup as verified.

Codex performed the isolated integration, reproduced and corrected the
PostgreSQL test setup conflict, executed the checks above and prepared the
develop delivery. GitHub CI and final merge identifiers are recorded on the PR.

