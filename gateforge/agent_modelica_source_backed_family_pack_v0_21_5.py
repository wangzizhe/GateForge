from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAMILY_CANDIDATE_PATH = (
    REPO_ROOT / "artifacts" / "early_compile_family_v0_21_1" / "family_candidates.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "source_backed_family_pack_v0_21_5"
DEFAULT_ADMITTED_CASE_GLOBS = [
    REPO_ROOT / "artifacts" / "underdetermined_mutations_v0_19_12" / "admitted_cases.jsonl",
    REPO_ROOT / "artifacts" / "non_ground_connect_deletion_mutations_v0_19_26" / "admitted_cases.jsonl",
    REPO_ROOT / "artifacts" / "component_instance_deletion_mutations_v0_19_27" / "admitted_cases.jsonl",
    REPO_ROOT / "artifacts" / "benchmark_v0_19_1" / "admitted_cases.jsonl",
]

TARGET_BUCKETS = ("ET01", "ET02", "ET03")
MODEL_NAME_RE = re.compile(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)\b")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def extract_model_name(model_text: str) -> str:
    match = MODEL_NAME_RE.search(str(model_text or ""))
    return "" if not match else match.group(1)


def has_source_viability_evidence(row: dict[str, Any]) -> bool:
    return bool(
        row.get("source_check_pass")
        or row.get("source_simulate_pass")
        or row.get("benchmark_admission")
        or row.get("admission_status") == "PASS"
    )


def build_source_inventory(paths: Iterable[Path] = DEFAULT_ADMITTED_CASE_GLOBS) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for path in paths:
        for row in load_jsonl(path):
            source_path = str(row.get("source_model_path") or "")
            if not source_path or source_path in seen_paths:
                continue
            source = Path(source_path)
            if not source.exists() or not has_source_viability_evidence(row):
                continue
            model_text = source.read_text(encoding="utf-8")
            model_name = extract_model_name(model_text)
            if not model_name:
                continue
            seen_paths.add(source_path)
            inventory.append(
                {
                    "source_model_path": source_path,
                    "source_model_name": model_name,
                    "source_evidence_artifact": str(path),
                    "source_evidence_case_id": str(row.get("candidate_id") or row.get("task_id") or ""),
                    "source_viability_status": "historically_verified_clean_source",
                }
            )
    return inventory


def mutate_source_for_bucket(model_text: str, bucket_id: str) -> str:
    if bucket_id == "ET01":
        return "{\n" + model_text
    if bucket_id == "ET02":
        replaced = re.sub(
            r"\bModelica\.Electrical\.Analog\.Basic\.Resistor\b",
            "Modelica.Electrical.Analog.Basic.DoesNotExistResistor",
            model_text,
            count=1,
        )
        if replaced != model_text:
            return replaced
        return re.sub(r"\bequation\b", "  MissingLibrary.DoesNotExist missingComponent;\nequation", model_text, count=1)
    if bucket_id == "ET03":
        return re.sub(r"\bequation\b", "equation\n  missingIdentifier = time;", model_text, count=1)
    return model_text


def build_source_backed_candidate(
    family_candidate: dict[str, Any],
    source_row: dict[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    source_path = Path(str(source_row["source_model_path"]))
    source_text = source_path.read_text(encoding="utf-8")
    bucket_id = str(family_candidate.get("bucket_id") or "")
    mutated_model_name = str(source_row.get("source_model_name") or f"SourceBacked{index}")
    return {
        "source_backed_candidate_id": f"v0215_{bucket_id.lower()}_{index:03d}_{mutated_model_name}",
        "family_candidate_id": family_candidate.get("family_candidate_id"),
        "bucket_id": bucket_id,
        "family_id": family_candidate.get("family_id"),
        "source_task_id": family_candidate.get("source_task_id"),
        "source_model_path": str(source_path),
        "source_model_name": mutated_model_name,
        "source_viability_status": source_row.get("source_viability_status"),
        "source_evidence_artifact": source_row.get("source_evidence_artifact"),
        "source_evidence_case_id": source_row.get("source_evidence_case_id"),
        "target_model_name": mutated_model_name,
        "target_model_text": mutate_source_for_bucket(source_text, bucket_id),
        "target_failure_status": "pending_omc_validation",
        "benchmark_admission_status": "isolated_source_backed_candidate_only",
    }


def build_source_backed_candidates(
    *,
    family_candidates: list[dict[str, Any]],
    source_inventory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target_family_candidates = [
        row for row in family_candidates if str(row.get("bucket_id") or "") in TARGET_BUCKETS
    ]
    rows: list[dict[str, Any]] = []
    if not source_inventory:
        return rows
    for index, family_candidate in enumerate(target_family_candidates, start=1):
        source_row = source_inventory[(index - 1) % len(source_inventory)]
        rows.append(build_source_backed_candidate(family_candidate, source_row, index=index))
    return rows


def summarize_source_backed_pack(rows: list[dict[str, Any]], source_inventory: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket = Counter(str(row.get("bucket_id") or "") for row in rows)
    target_covered = all(by_bucket.get(bucket, 0) > 0 for bucket in TARGET_BUCKETS)
    return {
        "version": "v0.21.5",
        "status": "PASS" if rows and target_covered else "REVIEW",
        "source_inventory_count": len(source_inventory),
        "source_backed_candidate_count": len(rows),
        "candidate_count_by_bucket": dict(sorted(by_bucket.items())),
        "source_viability_status": "historically_verified_clean_source",
        "target_failure_status": "pending_omc_validation",
        "benchmark_admission_status": "isolated_source_backed_candidate_only",
        "next_action": "run_omc_target_failure_admission",
        "conclusion": (
            "source_backed_family_pack_ready_for_target_validation"
            if rows and target_covered
            else "source_backed_family_pack_needs_review"
        ),
    }


def write_outputs(
    out_dir: Path,
    rows: list[dict[str, Any]],
    source_inventory: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    serializable_rows: list[dict[str, Any]] = []
    for row in rows:
        model_text = str(row.get("target_model_text") or "")
        model_path = models_dir / f"{row['source_backed_candidate_id']}.mo"
        model_path.write_text(model_text, encoding="utf-8")
        public_row = dict(row)
        public_row.pop("target_model_text", None)
        public_row["target_model_path"] = str(model_path)
        serializable_rows.append(public_row)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "source_backed_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in serializable_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "source_inventory.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in source_inventory),
        encoding="utf-8",
    )


def run_source_backed_family_pack(
    *,
    family_candidate_path: Path = DEFAULT_FAMILY_CANDIDATE_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    source_inventory_paths: Iterable[Path] = DEFAULT_ADMITTED_CASE_GLOBS,
) -> dict[str, Any]:
    family_candidates = load_jsonl(family_candidate_path)
    source_inventory = build_source_inventory(source_inventory_paths)
    rows = build_source_backed_candidates(
        family_candidates=family_candidates,
        source_inventory=source_inventory,
    )
    summary = summarize_source_backed_pack(rows, source_inventory)
    write_outputs(out_dir, rows, source_inventory, summary)
    return summary
