# Phase 25 — image vulnerability promotion policy

The repository supplies only an unapproved policy template. It cannot open promotion.
`promotion_gate` remains fail-closed until a reviewed policy supplies an owner, expiry, DB freshness limit, hash, and approved flag, alongside a normalized measured attestation bound to the resolved image ID and raw-report hash.

The validator now requires the attestation schema/origin, resolved image ID, exact raw-report bytes matching `source_report.sha256`, database update time, severity findings, and policy bytes matching its declared hash. It blocks expired or stale-policy evidence, configured blocked severities, and unfixed findings when the reviewed policy disallows them. A `passed` result only means the supplied evidence matches the supplied approved policy at evaluation time; it is not a release, security, or operational approval.

Severity thresholds, unfixed-CVE handling, waivers, scope, and report retention remain decisions for the future reviewed policy; this repository does not make them automatically.

Once those decisions are approved, run the deterministic gate against the exact three inputs:

```powershell
python -m scripts.check_promotion_gate <attestation.json> <approved-policy.json> <raw-trivy.json>
```

Exit `0` means the supplied evidence matches the supplied policy at that moment; exit `2` is a normal fail-closed block. The bundled example policy must continue to exit `2`.
