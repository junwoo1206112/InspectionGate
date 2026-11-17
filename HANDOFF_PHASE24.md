# Phase 24 handoff — measured image vulnerability evidence

## What was measured

On 2026-11-10, Docker Desktop local images were scanned with Trivy 0.76.2 using `--image-src docker`. The first run downloaded Trivy vulnerability DB from its configured mirror. Raw results are immutable inputs for follow-up review:

| Image | Resolved local image ID | Critical | High | Medium | Low | Raw report |
|---|---|---:|---:|---:|---:|---|
| `inspectiongate:phase18` | `sha256:80f772181f1f…` | 0 | 49 | 81 | 66 | `artifacts/phase24-trivy/inspectiongate-phase18.json` |
| `redis:7-alpine` | `sha256:c5d34a98396a…` | 0 | 0 | 1 | 0 | `artifacts/phase24-trivy/redis-7-alpine.json` |

## Interpretation boundary

This is a local Docker image vulnerability measurement, not a security certification, remediation, release approval, SBOM, image signature verification, secret-management assessment, TLS/authentication assessment, or HA test. Promotion remains blocked: there is no approved severity, unfixed-CVE, DB-freshness, waiver, or signed policy.

## Next owner actions

1. Review HIGH findings in the application raw JSON, grouping by fixed version and direct versus base-image dependency.
2. Decide a supported base-image upgrade strategy; rebuild under a new immutable image ID and rescan.
3. Decide policy thresholds, DB freshness, unfixed-CVE handling, exception owner/expiry, and report retention.
4. Feed only a real, current report plus approved policy to `inspection_gate.promotion_gate`; test fixtures and `not_measured` reports are rejected.

## Phase 27 remediation follow-up

`inspectiongate:phase27` retained the pinned Python base and applied the available Debian upgrade layer in a new image only. Docker smoke passed. Fresh Trivy evidence at `artifacts/phase27-trivy/inspectiongate-phase27.json` changed the app count from HIGH 49 / MEDIUM 81 / LOW 66 to HIGH 47 / MEDIUM 80 / LOW 66. This is a measured reduction, not approval; remaining findings without a vendor fixed version remain unresolved.

## Reproduction

Use the installed Trivy binary with local Docker input. A future scan must create a new output directory and record its report hashes. Do not reuse these findings for a rebuilt image.
