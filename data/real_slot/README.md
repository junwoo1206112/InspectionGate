# Real data slot

1. Put licensed images under `images/` (PNG/JPEG/BMP, single frame).
2. Fill `reviewed.json`: provenance, license, reviewer, label definitions, group/cluster policy, items.
3. Run readiness check:

```powershell
python -m scripts.check_real_data_ready .
```

4. Then ingest and train with origin `real_reviewed_input`:

```powershell
python -m scripts.ingest_local_dataset .\reviewed.json .\images ..\..\artifacts\real-run-001 --near-duplicate-hamming 6
python -m scripts.reference_pipeline train .\images ..\..\artifacts\real-run-001\bundle ..\..\artifacts\real-run-001\model --origin real_reviewed_input
```

Do not commit real images or `reviewed.json`; they are ignored by git.
