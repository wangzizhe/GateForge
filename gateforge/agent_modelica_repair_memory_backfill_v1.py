from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Repair Memory Backfill v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{payload.get('total_rows')}`",
        f"- updated_rows: `{payload.get('updated_rows')}`",
        f"- filled_error_signature: `{payload.get('filled_error_signature')}`",
        f"- filled_gate_break_reason: `{payload.get('filled_gate_break_reason')}`",
        f"- filled_split: `{payload.get('filled_split')}`",
        f"- holdout_rows: `{payload.get('holdout_rows')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _infer_gate_break_reason(row: dict) -> str:
    if bool(row.get("success")):
        return "none"
    text = " ".join(
        [
            _norm(row.get("error_excerpt")),
            _norm(row.get("patch_diff_summary")),
            _norm(row.get("failure_type")),
        ]
    ).lower()
    if "regression" in text:
        return "regression_fail"
    if "physics" in text:
        return "physics_contract_fail"
    if "simulate" in text or "integrator" in text:
        return "simulate_fail"
    if "compile" in text or "checkmodel" in text or "model_check" in text:
        return "check_model_fail"
    return "unknown_fail"


def _build_signature(row: dict) -> str:
    failure_type = _norm(row.get("failure_type")).lower() or "unknown"
    basis = "|".join(
        [
            failure_type,
            _norm(row.get("task_id")).lower(),
            _norm(row.get("used_strategy")).lower(),
            _norm(row.get("error_excerpt")).lower(),
            _norm(row.get("patch_diff_summary")).lower(),
            "pass" if bool(row.get("success")) else "fail",
        ]
    )
    return f"{failure_type}:{_short_hash(basis)}"


def _assign_split(signature: str, holdout_ratio: float) -> str:
    h = int(hashlib.sha256(signature.encode("utf-8")).hexdigest()[:8], 16)
    bucket = h % 10000
    threshold = int(max(0.0, min(1.0, holdout_ratio)) * 10000)
    return "holdout" if bucket < threshold else "train"


def backfill_memory(memory_payload: dict, holdout_ratio: float) -> tuple[dict, dict]:
    rows = memory_payload.get("rows") if isinstance(memory_payload.get("rows"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]
    updated_rows = 0
    filled_error_signature = 0
    filled_gate_reason = 0
    filled_split = 0
    now = datetime.now(timezone.utc).isoformat()

    signature_to_split: dict[str, str] = {}
    holdout_signature_count = 0
    seen_signatures: set[str] = set()

    for row in rows:
        changed = False
        sig = _norm(row.get("error_signature"))
        if not sig:
            sig = _build_signature(row)
            row["error_signature"] = sig
            filled_error_signature += 1
            changed = True

        reason = _norm(row.get("gate_break_reason"))
        if not reason:
            row["gate_break_reason"] = _infer_gate_break_reason(row)
            filled_gate_reason += 1
            changed = True

        split = _norm(row.get("split")).lower()
        if not split:
            assigned = signature_to_split.get(sig)
            if not assigned:
                assigned = _assign_split(sig, holdout_ratio=holdout_ratio)
                signature_to_split[sig] = assigned
            row["split"] = assigned
            filled_split += 1
            changed = True
        else:
            signature_to_split.setdefault(sig, split)

        if changed:
            row["last_seen_at_utc"] = now
            updated_rows += 1
        seen_signatures.add(sig)

    # Ensure holdout exists when rows exist.
    holdout_signatures = {sig for sig, split in signature_to_split.items() if split == "holdout"}
    if rows and not holdout_signatures:
        first_sig = sorted(seen_signatures)[0]
        signature_to_split[first_sig] = "holdout"
        for row in rows:
            if _norm(row.get("error_signature")) == first_sig:
                if _norm(row.get("split")).lower() != "holdout":
                    row["split"] = "holdout"
                    row["last_seen_at_utc"] = now
                    updated_rows += 1
                    filled_split += 1
        holdout_signatures.add(first_sig)

    holdout_rows = sum(1 for row in rows if _norm(row.get("split")).lower() == "holdout")
    payload = dict(memory_payload)
    payload["schema_version"] = str(payload.get("schema_version") or "agent_modelica_repair_memory_v1")
    payload["generated_at_utc"] = now
    payload["rows"] = rows

    summary = {
        "schema_version": "agent_modelica_repair_memory_backfill_v1",
        "status": "PASS",
        "total_rows": len(rows),
        "updated_rows": updated_rows,
        "filled_error_signature": filled_error_signature,
        "filled_gate_break_reason": filled_gate_reason,
        "filled_split": filled_split,
        "holdout_rows": holdout_rows,
        "holdout_signature_count": len(holdout_signatures),
    }
    return payload, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill repair memory fields required by learning readiness gate")
    parser.add_argument("--memory", default="data/private_failure_corpus/agent_modelica_repair_memory_v1.json")
    parser.add_argument("--memory-out", default="")
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_memory_backfill_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    memory_payload = _load_json(args.memory)
    filled_payload, summary = backfill_memory(memory_payload, holdout_ratio=float(args.holdout_ratio))
    memory_out = _norm(args.memory_out) or args.memory
    _write_json(memory_out, filled_payload)
    _write_json(args.out, summary)
    report_out = args.report_out or _default_md_path(args.out)
    _write_markdown(report_out, summary)
    print(json.dumps({"status": summary.get("status"), "updated_rows": summary.get("updated_rows")}))


if __name__ == "__main__":
    main()
