"""Normalize a real local Trivy JSON report; never grants promotion."""
from __future__ import annotations
import argparse, hashlib, json, os
from datetime import UTC, datetime
from pathlib import Path

def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument("report",type=Path); p.add_argument("out",type=Path); p.add_argument("--image-id",required=True); p.add_argument("--scanner-version",required=True); p.add_argument("--scanner-path",type=Path,required=True); p.add_argument("--db-metadata",type=Path,required=True); a=p.parse_args()
 raw=a.report.read_bytes(); x=json.loads(raw); vs=[v for r in x.get("Results",[]) for v in (r.get("Vulnerabilities") or [])]
 db=a.db_metadata
 db_value=None
 if db.is_file() and a.scanner_path.is_file():
  content=db.read_bytes(); db_value={"sha256":hashlib.sha256(content).hexdigest(),"metadata":json.loads(content)}
 out={"schema":"inspection-gate.image-scan-attestation.v1","origin":"measured_local","generated_at":datetime.now(UTC).isoformat(),"resolved_image_id":a.image_id,"scanner":{"name":"trivy","version":a.scanner_version,"sha256":hashlib.sha256(a.scanner_path.read_bytes()).hexdigest()},"source_report":{"path":a.report.name,"sha256":hashlib.sha256(raw).hexdigest()},"database_metadata":db_value,"findings":{"total":len(vs),"by_severity":{s:sum(v.get("Severity")==s for v in vs) for s in ["CRITICAL","HIGH","MEDIUM","LOW","UNKNOWN"]},"unfixed":sum(not v.get("FixedVersion") for v in vs)},"claim_boundary":"Measured local evidence only; policy, DB freshness, waiver, and promotion verdict are not evaluated."}
 a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2)+"\n"); print(json.dumps({"attestation":str(a.out),"findings":out["findings"]})); return 0
if __name__=="__main__": raise SystemExit(main())
