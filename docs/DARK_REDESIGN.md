# Unified dark interface preview

## Delivery brief
Make the entire existing Robo Advisor journey consistent with the approved dark dashboard: sign in → risk/Frontier → themes → review/confirm → portfolio → performance/comparison → decision review. Administrators get the same visual language with a distinct internal navigation area.

Scope: semantic dark tokens, accessible controls, navigation, auth presentation, tables, charts, empty/error/loading states and responsive layouts. Existing financial engines, API contracts, requests, permissions, portfolio save/confirmation, stored prices, evaluation and source provenance stay unchanged. No production data migration or automatic rebalance implementation.

## Decisions
- One token system serves all existing CSS modules and shared components; no second application or replacement financial model.
- Dashboard becomes the concise overview; existing detailed analytics remain reachable through `view=details`, including existing period/common/demo modes.
- Historic reconstruction and forward operation remain distinct with their existing labels and disclosure.
- Category series retain meaningful colors; chart axes/tooltips use the shared dark surface and readable text.

## Acceptance and rollout
Run the existing frontend regression suite and production build. Inspect authenticated preview routes at desktop and narrow widths, including navigation, detail disclosures, existing error/empty states and administrator access denial. Do not change saved portfolios to perform visual checks. Publish to the isolated preview branch/Draft PR; production promotion is separate.

Verification results are recorded in INTEGRATION_EXECUTION.md after checks complete.
