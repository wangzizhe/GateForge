from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _sha256_file(path: str) -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
        "# GateForge Agent Modelica Run Snapshot v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- run_id: `{payload.get('run_id')}`",
        f"- git_commit: `{payload.get('git', {}).get('commit')}`",
        f"- profile_path: `{payload.get('inputs', {}).get('profile_path')}`",
        f"- hardpack_path: `{payload.get('inputs', {}).get('hardpack_path')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _git_info(repo_root: str) -> dict:
    def _run(args: list[str]) -> str:
        try:
            proc = subprocess.run(
                args,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if proc.returncode != 0:
                return ""
            return str(proc.stdout or "").strip()
        except Exception:
            return ""

    commit = _run(["git", "rev-parse", "HEAD"])
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = _run(["git", "status", "--porcelain"])
    return {"commit": commit, "branch": branch, "dirty": bool(dirty)}


def _file_entry(path: str) -> dict:
    p = Path(path)
    return {
        "path": path,
        "exists": p.exists(),
        "sha256": _sha256_file(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze run snapshot metadata for reproducibility")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--hardpack-path", default="")
    parser.add_argument("--physics-contract-path", default="")
    parser.add_argument("--repair-playbook-path", default="")
    parser.add_argument("--repair-history-path", default="")
    parser.add_argument("--patch-template-adaptations-path", default="")
    parser.add_argument("--retrieval-policy-path", default="")
    parser.add_argument("--taskset-path", default="")
    parser.add_argument("--extra-file", action="append", default=[])
    parser.add_argument("--config-json", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_run_snapshot_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    input_paths = [
        args.profile_path,
        args.hardpack_path,
        args.physics_contract_path,
        args.repair_playbook_path,
        args.repair_history_path,
        args.patch_template_adaptations_path,
        args.retrieval_policy_path,
        args.taskset_path,
    ]
    input_paths.extend([str(x) for x in (args.extra_file or []) if str(x).strip()])
    input_paths = [str(x).strip() for x in input_paths if str(x).strip()]

    files = [_file_entry(path) for path in input_paths]
    missing = [x["path"] for x in files if not bool(x.get("exists"))]

    config = _load_json(args.config_json) if str(args.config_json).strip() else {}
    git_info = _git_info(repo_root=str(args.repo_root))
    payload = {
        "schema_version": "agent_modelica_run_snapshot_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not missing else "NEEDS_REVIEW",
        "run_id": str(args.run_id),
        "git": git_info,
        "inputs": {
            "profile_path": args.profile_path,
            "hardpack_path": args.hardpack_path,
            "physics_contract_path": args.physics_contract_path,
            "repair_playbook_path": args.repair_playbook_path,
            "repair_history_path": args.repair_history_path,
            "patch_template_adaptations_path": args.patch_template_adaptations_path,
            "retrieval_policy_path": args.retrieval_policy_path,
            "taskset_path": args.taskset_path,
        },
        "files": files,
        "config": config,
        "missing_files": missing,
        "reasons": ["missing_input_files"] if missing else [],
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "missing_files": len(missing)}))


if __name__ == "__main__":
    main()
