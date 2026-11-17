# Phase 26 — base-image remediation plan

## Verified current state

- App remediation is not applied: `Dockerfile` still uses mutable `python:3.12-slim`.
- Redis remediation is not applied: only the scanned `redis:7-alpine` local image exists.
- Promotion is blocked by the unapproved Phase 25 policy.
- Phase 24 raw reports remain evidence for their exact image IDs only.

## Required controlled change

1. Select and record a reviewed Python 3.12 slim **manifest digest**, then pin it in `Dockerfile`.
2. Build under a new tag; run container smoke; create fresh Trivy JSON and hashes; compare findings without treating a lower count as approval.
3. Select Redis major version and supported Alpine digest only after compatibility review; run Redis smoke and fresh scan separately.

Do not replace either tag automatically. Docker digest pinning is reproducible, but a digest choice is a compatibility/security decision.
