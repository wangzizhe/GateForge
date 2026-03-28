from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_c_claim_gate_v0_3_1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_claim_gate_v0_3_1"


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def build_claim_gate(*, matrix_summary_path: str, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    matrix = _load_json(matrix_summary_path)
    rows = matrix.get("grouped_rows") if isinstance(matrix.get("grouped_rows"), list) else []
    gateforge_rows = [row for row in rows if isinstance(row, dict) and _norm(row.get("provider_name")) == "gateforge"]
    external_rows = [row for row in rows if isinstance(row, dict) and _norm(row.get("provider_name")) != "gateforge"]
    gateforge_best = max([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in gateforge_rows], default=0.0)
    external_best = max([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in external_rows], default=0.0)
    max_infra = max([float(row.get("infra_failure_rate_pct") or 0.0) for row in rows], default=0.0)
    classification = "inconclusive"
    if gateforge_rows and external_rows and max_infra < 20.0:
        if gateforge_best >= external_best + 5.0:
            classification = "advantage"
        elif abs(gateforge_best - external_best) < 5.0:
            classification = "match"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if rows else "FAIL",
        "matrix_summary_path": str(Path(matrix_summary_path).resolve()) if Path(matrix_summary_path).exists() else str(matrix_summary_path),
        "gateforge_best_infra_normalized_success_rate_pct": round(gateforge_best, 2),
        "external_best_infra_normalized_success_rate_pct": round(external_best, 2),
        "max_infra_failure_rate_pct": round(max_infra, 2),
        "classification": classification,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the v0.3.1 Track C claim gate to a matrix summary.")
    parser.add_argument("--matrix-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_claim_gate(matrix_summary_path=str(args.matrix_summary), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
