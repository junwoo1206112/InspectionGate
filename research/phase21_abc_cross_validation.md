# Phase 21 — image scan readiness advisory

## A: repository evidence

The existing Docker smoke records build/run behavior only; it has no scanner, database, findings, or policy contract. `docs/STATUS.md` records the current Docker API connection failure, so the old smoke image ID cannot prove a current image scan.

## B: external evidence

Docker image tags are mutable, while inspect can expose a local image ID and repo digests. Trivy supports several input sources; this runner deliberately accepts only a local Docker image and never falls through to a remote registry, OCI archive, or SBOM. Sources: [Docker image inspect](https://docs.docker.com/reference/cli/docker/image/inspect/), [Trivy container image scanning](https://trivy.dev/docs/latest/guide/target/container_image/).

## C: adversarial review

`not_measured` must never be represented as clean, passed, or security-approved. Readiness implementation can be complete while deployment promotion remains blocked until a later actual measurement is bound to a resolved identity and evaluated against a separately chosen policy.

## Recommendation implemented

`scripts/image_scan.py` writes a fresh, atomic JSON report for each requested local image. It records only observed state, uses `not_measured` for unavailable prerequisites, preserves a hash of raw Trivy JSON only after an actual scan, and leaves `policy_verdict=not_evaluated`. It does not auto-install tools, pull images, download a DB, or transmit artifacts.
