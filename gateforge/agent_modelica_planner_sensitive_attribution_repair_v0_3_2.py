from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_experience_writer_v1 import build_experience_payload


SCHEMA_VERSION = "agent_modelica_planner_sensitive_attribution_repair_v0_3_2"
DEFAULT_SOURCE_DIR = "artifacts/agent_modelica_planner_sensitive_eval_v1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_planner_sensitive_attribution_repair_v0_3_2"
DEFAULT_VARIANTS = ("baseline", "planner_only", "replay_only", "replay_plus_planner")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _count_success(records: list[dict]) -> int:
    count = 0
    for row in records:
        if not isinstance(row, dict):
            continue
        hard_checks = row.get("hard_checks") if isinstance(row.get("hard_checks"), dict) else {}
        if bool(row.get("passed")):
            count += 1
            continue
        if hard_checks and bool(
            hard_checks.get("check_model_pass")
            and hard_checks.get("simulate_pass")
            and hard_checks.get("physics_contract_pass", True)
            and hard_checks.get("regression_pass", True)
        ):
            count += 1
    return count


def _render_variant_markdown(summary: dict) -> str:
    lines = [
        f"# Planner-Sensitive Attribution Repair v0.3.2 ({summary.get('variant')})",
        "",
        f"- status: `{summary.get('status')}`",
        f"- source_results_path: `{summary.get('source_results_path')}`",
        f"- total_tasks: `{summary.get('total_tasks')}`",
        f"- success_count: `{summary.get('success_count')}`",
        f"- success_at_k_pct: `{summary.get('success_at_k_pct')}`",
        f"- resolution_path_distribution: `{json.dumps(summary.get('resolution_path_distribution') or {}, sort_keys=True)}`",
        f"- planner_invoked_rate_pct: `{summary.get('planner_invoked_rate_pct')}`",
        f"- planner_decisive_rate_pct: `{summary.get('planner_decisive_rate_pct')}`",
    ]
    notes = summary.get("notes") if isinstance(summary.get("notes"), list) else []
    if notes:
        lines.append(f"- notes: `{'; '.join(str(note) for note in notes)}`")
    return "\n".join(lines).strip() + "\n"


def repair_variant(*, variant: str, source_dir: str = DEFAULT_SOURCE_DIR, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    source_root = Path(source_dir)
    out_root = Path(out_dir)
    results_path = source_root / f"results_{variant}.json"
    legacy_summary_path = source_root / f"summary_{variant}.json"
    results_payload = _load_json(results_path)
    legacy_summary = _load_json(legacy_summary_path)
    experience_payload = build_experience_payload(results_payload)
    records = results_payload.get("records") if isinstance(results_payload.get("records"), list) else []
    success_count = _count_success([row for row in records if isinstance(row, dict)])
    total_tasks = len([row for row in records if isinstance(row, dict)])
    rebuilt_summary = experience_payload.get("summary") if isinstance(experience_payload.get("summary"), dict) else {}
    legacy_resolution = legacy_summary.get("resolution_path_distribution") if isinstance(legacy_summary.get("resolution_path_distribution"), dict) else {}
    rebuilt_resolution = rebuilt_summary.get("resolution_path_distribution") if isinstance(rebuilt_summary.get("resolution_path_distribution"), dict) else {}
    notes = [
        "rebuilt from raw results payload because bundled planner-sensitive experience attribution was stale",
    ]
    if legacy_resolution and legacy_resolution != rebuilt_resolution:
        notes.append(
            f"legacy resolution_path_distribution {json.dumps(legacy_resolution, sort_keys=True)} replaced with {json.dumps(rebuilt_resolution, sort_keys=True)}"
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total_tasks > 0 else "MISSING_RESULTS",
        "variant": variant,
        "source_results_path": str(results_path),
        "source_legacy_summary_path": str(legacy_summary_path),
        "total_tasks": total_tasks,
        "success_count": success_count,
        "success_at_k_pct": _ratio(success_count, total_tasks),
        "resolution_path_distribution": dict(sorted((str(k), int(v or 0)) for k, v in rebuilt_resolution.items())),
        "dominant_stage_subtype_distribution": dict(
            sorted((str(k), int(v or 0)) for k, v in ((rebuilt_summary.get("dominant_stage_subtype_distribution") or {}).items()))
        ),
        "planner_invoked_rate_pct": float(rebuilt_summary.get("planner_invoked_rate_pct") or 0.0),
        "planner_used_rate_pct": float(rebuilt_summary.get("planner_used_rate_pct") or 0.0),
        "planner_decisive_rate_pct": float(rebuilt_summary.get("planner_decisive_rate_pct") or 0.0),
        "notes": notes,
    }
    _write_json(out_root / f"experience_{variant}.json", experience_payload)
    _write_json(out_root / f"summary_{variant}.json", payload)
    _write_text(out_root / f"summary_{variant}.md", _render_variant_markdown(payload))
    return payload


def _render_report_markdown(payload: dict) -> str:
    lines = [
        "# Planner-Sensitive Attribution Repair v0.3.2",
        "",
        f"- generated_at_utc: `{payload.get('generated_at_utc')}`",
        "",
        "## Variants",
        "",
    ]
    for row in payload.get("variants") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"### {row.get('variant')}")
        lines.append("")
        lines.append(f"- status: `{row.get('status')}`")
        lines.append(f"- success_count: `{row.get('success_count')}/{row.get('total_tasks')}`")
        lines.append(f"- resolution_path_distribution: `{json.dumps(row.get('resolution_path_distribution') or {}, sort_keys=True)}`")
        lines.append(f"- planner_decisive_rate_pct: `{row.get('planner_decisive_rate_pct')}`")
        notes = row.get("notes") if isinstance(row.get("notes"), list) else []
        if notes:
            lines.append(f"- notes: `{'; '.join(str(note) for note in notes)}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_repair(
    *,
    source_dir: str = DEFAULT_SOURCE_DIR,
    out_dir: str = DEFAULT_OUT_DIR,
    variants: tuple[str, ...] = DEFAULT_VARIANTS,
) -> dict:
    variant_rows = [repair_variant(variant=variant, source_dir=source_dir, out_dir=out_dir) for variant in variants]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "source_dir": str(source_dir),
        "out_dir": str(out_dir),
        "variants": variant_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "repair_report.json", payload)
    _write_text(out_root / "repair_report.md", _render_report_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair stale planner-sensitive attribution artifacts from raw results")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--variant", action="append", default=[])
    args = parser.parse_args()
    variants = tuple(str(row) for row in (args.variant or []) if str(row).strip()) or DEFAULT_VARIANTS
    payload = run_repair(source_dir=str(args.source_dir), out_dir=str(args.out_dir), variants=variants)
    print(json.dumps({"variant_count": len(payload.get("variants") or [])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
