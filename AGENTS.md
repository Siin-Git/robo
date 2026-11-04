# Integration workspace

Preserve original root and nested checkouts. Work only on the isolated integration branch.
Reuse backend financial engines; the frontend displays server contracts and never invents financial rules.
Keep immutable decision history and user ownership boundaries. Do not backfill missing historical estimates.
Run Python 3.11+ backend tests and frontend tests/build after relevant changes.
Never use production DBs for tests. Generated DB reports are test artifacts, not migration evidence.
Do not merge main/develop, push, deploy, or change external settings without explicit final authorization.
Backup PR #12 is separately owned: do not edit its workflow.
Record functional changes with focused commits and maintain docs/INTEGRATION_EXECUTION.md.
