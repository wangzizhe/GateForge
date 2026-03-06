from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PRIVATE_PATHS = [
    "data/private_failure_corpus",
    "benchmarks/private",
    "policies/private",
]


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _path_key(path: str) -> str:
    token = str(path or "").strip().lower().replace("/", "_").replace("\\", "_").replace("-", "_")
    token = "_".join([x for x in token.split("_") if x])
    return token or "unknown_path"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    paths = payload.get("private_paths") if isinstance(payload.get("private_paths"), list) else []
    tracked = payload.get("tracked_files") if isinstance(payload.get("tracked_files"), list) else []
    lines = [
        "# GateForge Agent Modelica Private Asset Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_private_paths: `{len(paths)}`",
        f"- tracked_private_file_count: `{len(tracked)}`",
        "",
    ]
    if tracked:
        lines.append("## Tracked Private Files")
        lines.append("")
        for item in tracked:
            lines.append(f"- `{item}`")
    else:
        lines.append("No tracked private files detected.")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _git_tracked_files(repo_root: str, path: str) -> tuple[list[str], str]:
    proc = subprocess.run(
        ["git", "-C", repo_root, "ls-files", "--", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if int(proc.returncode) != 0:
        return [], str(proc.stderr or "").strip()
    tracked = [str(x).strip() for x in str(proc.stdout or "").splitlines() if str(x).strip()]
    return tracked, ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard that private moat assets are not tracked in git")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--private-path", action="append", default=[])
    parser.add_argument("--out", default="artifacts/agent_modelica_private_asset_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    private_paths = [str(x).strip() for x in (args.private_path or []) if str(x).strip()]
    if not private_paths:
        private_paths = list(DEFAULT_PRIVATE_PATHS)

    repo_root = str(Path(args.repo_root).resolve())
    checks: dict[str, str] = {}
    tracked_files: list[str] = []
    reasons: list[str] = []

    for item in private_paths:
        tracked, err = _git_tracked_files(repo_root=repo_root, path=item)
        key = f"tracked_count_{_path_key(item)}"
        if err:
            checks[key] = "FAIL"
            reasons.append(f"git_ls_files_failed:{item}:{err}")
            continue
        checks[key] = "PASS" if not tracked else "FAIL"
        tracked_files.extend(tracked)

    status = "PASS"
    if reasons or tracked_files:
        status = "FAIL"
        if tracked_files:
            reasons.append("tracked_private_files_detected")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "repo_root": repo_root,
        "private_paths": private_paths,
        "tracked_files": sorted(set(tracked_files)),
        "tracked_private_file_count": len(sorted(set(tracked_files))),
        "checks": checks,
        "reasons": reasons,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "tracked_private_file_count": payload.get("tracked_private_file_count", 0),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
