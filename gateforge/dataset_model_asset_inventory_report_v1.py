from __future__ import annotations

import argparse
import glob
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _scale_by_lines(line_count: int) -> str:
    if line_count <= 40:
        return "small"
    if line_count <= 120:
        return "medium"
    return "large"


def _origin_for_path(path: Path) -> str:
    txt = str(path).replace("\\", "/")
    if "/artifacts/dataset_real_model_intake_pipeline_v1_demo/" in txt:
        return "real_intake_demo"
    if "/data/" in txt:
        return "external_data"
    if "/examples/" in txt:
        return "curated_example"
    return "other"


def _fingerprint(paths: list[str]) -> str:
    digest = hashlib.sha256("|".join(sorted(paths)).encode("utf-8")).hexdigest()
    return digest[:12]


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    by_scale = payload.get("by_scale") if isinstance(payload.get("by_scale"), dict) else {}
    by_origin = payload.get("by_origin") if isinstance(payload.get("by_origin"), dict) else {}
    lines = [
        "# GateForge Model Asset Inventory Report v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_models: `{payload.get('total_models')}`",
        f"- inventory_fingerprint: `{payload.get('inventory_fingerprint')}`",
        "",
        "## By Scale",
        "",
        f"- small: `{by_scale.get('small', 0)}`",
        f"- medium: `{by_scale.get('medium', 0)}`",
        f"- large: `{by_scale.get('large', 0)}`",
        "",
        "## By Origin",
        "",
    ]
    for key in sorted(by_origin.keys()):
        lines.append(f"- {key}: `{by_origin.get(key)}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reproducible inventory report for Modelica model assets")
    parser.add_argument(
        "--model-glob",
        action="append",
        default=[],
        help="Glob for Modelica .mo files (repeatable). If omitted, defaults are used.",
    )
    parser.add_argument("--out", default="artifacts/dataset_model_asset_inventory_report_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    roots = args.model_glob or [
        "examples/openmodelica/**/*.mo",
        "artifacts/dataset_real_model_intake_pipeline_v1_demo/*.mo",
    ]
    files: list[Path] = []
    for pattern in roots:
        files.extend(Path(x) for x in glob.glob(pattern, recursive=True))

    uniq = sorted({p.resolve() for p in files if p.is_file() and p.suffix == ".mo"}, key=lambda p: str(p))
    reasons: list[str] = []
    if not uniq:
        reasons.append("no_modelica_models_found")

    by_scale = {"small": 0, "medium": 0, "large": 0}
    by_origin: dict[str, int] = {}
    rows: list[dict] = []
    for p in uniq:
        txt = p.read_text(encoding="utf-8")
        line_count = len(txt.splitlines())
        scale = _scale_by_lines(line_count)
        origin = _origin_for_path(p)
        by_scale[scale] += 1
        by_origin[origin] = by_origin.get(origin, 0) + 1
        rows.append(
            {
                "path": str(p),
                "line_count": line_count,
                "scale": scale,
                "origin": origin,
            }
        )

    total_models = len(uniq)
    status = "PASS"
    if reasons:
        status = "FAIL"
    elif by_scale["large"] == 0:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_models": total_models,
        "by_scale": by_scale,
        "by_origin": by_origin,
        "inventory_fingerprint": _fingerprint([str(p) for p in uniq]),
        "models": rows,
        "source_globs": roots,
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_models": total_models}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
