from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: Path) -> Path:
    if out_json.suffix == ".json":
        return out_json.with_suffix(".md")
    return Path(str(out_json) + ".md")


def _write_markdown(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Core Scope Snapshot v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- core_path_count: `{payload.get('core_path_count')}`",
        f"- core_existing_count: `{payload.get('core_existing_count')}`",
        f"- optional_private_path_count: `{payload.get('optional_private_path_count')}`",
        f"- optional_private_available_count: `{payload.get('optional_private_available_count')}`",
        f"- demo_script_count: `{payload.get('demo_script_count')}`",
        f"- demo_test_count: `{payload.get('demo_test_count')}`",
        "",
        "## Missing Core Paths",
        "",
    ]
    missing = payload.get("missing_core_paths") if isinstance(payload.get("missing_core_paths"), list) else []
    if missing:
        for item in missing:
            lines.append(f"- `{item}`")
    else:
        lines.append("- `none`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _exists_map(repo_root: Path, rel_paths: list[str]) -> tuple[int, list[str]]:
    existing = 0
    missing: list[str] = []
    for rel in rel_paths:
        p = repo_root / rel
        if p.exists():
            existing += 1
        else:
            missing.append(rel)
    return existing, missing


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a compact snapshot for Agent Modelica core-only scope")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--scope", default="core/agent_modelica/core_scope_v1.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_core_view_v1/snapshot.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    scope_path = Path(args.scope)
    if not scope_path.is_absolute():
        scope_path = repo_root / scope_path
    scope = _load_json(scope_path)

    core_paths = scope.get("core_paths") if isinstance(scope.get("core_paths"), list) else []
    core_paths = [str(x) for x in core_paths if isinstance(x, str) and str(x).strip()]
    core_existing_count, missing_core_paths = _exists_map(repo_root, core_paths)
    optional_private_paths = (
        scope.get("optional_private_paths") if isinstance(scope.get("optional_private_paths"), list) else []
    )
    optional_private_paths = [str(x) for x in optional_private_paths if isinstance(x, str) and str(x).strip()]
    optional_private_available_count, missing_optional_private_paths = _exists_map(repo_root, optional_private_paths)

    demo_script_count = len(list((repo_root / "scripts").glob("demo_*.sh")))
    demo_test_count = len(list((repo_root / "tests").glob("*_demo.py")))

    status = "PASS" if not missing_core_paths else "FAIL"
    payload = {
        "schema_version": "agent_modelica_core_scope_snapshot_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scope_path": str(scope_path),
        "repo_root": str(repo_root),
        "core_path_count": len(core_paths),
        "core_existing_count": core_existing_count,
        "missing_core_paths": missing_core_paths,
        "optional_private_path_count": len(optional_private_paths),
        "optional_private_available_count": optional_private_available_count,
        "missing_optional_private_paths": missing_optional_private_paths,
        "demo_script_count": demo_script_count,
        "demo_test_count": demo_test_count,
        "scope_version": scope.get("scope_version"),
        "scope_name": scope.get("scope_name"),
    }

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = repo_root / out_path
    report_path = Path(args.report_out) if args.report_out else _default_md_path(out_path)
    if not report_path.is_absolute():
        report_path = repo_root / report_path

    _write_json(out_path, payload)
    _write_markdown(report_path, payload)
    print(json.dumps({"status": status, "core_existing_count": core_existing_count, "core_path_count": len(core_paths)}))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
