from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_external_agent_mcp_surface_v0_3_1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_external_agent_mcp_surface_v0_3_1"


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _probe_row(summary_path: str) -> dict:
    summary = _load_json(summary_path)
    root = Path(summary_path).resolve().parent
    trace_rows = _load_jsonl(root / "mcp_protocol_trace.jsonl")
    provider_stderr = (root / "provider_stderr.txt").read_text(encoding="utf-8") if (root / "provider_stderr.txt").exists() else ""
    provider_name = _norm(summary.get("provider_name")) or root.name
    started = any(_norm(row.get("event")) == "launcher_start" for row in trace_rows)
    imported = any(_norm(row.get("event")) == "launcher_import_ok" for row in trace_rows)
    jsonrpc_seen = any(_norm(row.get("direction")) in {"in", "out"} for row in trace_rows)
    shared_tool_plane_reached = bool(summary.get("shared_tool_plane_reached"))
    resource_listing_only = "list_mcp_resources" in provider_stderr or "list_mcp_resource_templates" in provider_stderr
    classification = "tool_plane_unreachable"
    if shared_tool_plane_reached:
        classification = "reachable"
    elif started and imported and not jsonrpc_seen:
        classification = "external_cli_no_jsonrpc_handshake"
    elif started and not imported:
        classification = "server_import_failed"
    elif not started:
        classification = "server_process_not_started"
    return {
        "provider_name": provider_name,
        "summary_path": str(Path(summary_path).resolve()) if Path(summary_path).exists() else str(summary_path),
        "shared_tool_plane_reached": shared_tool_plane_reached,
        "server_process_started": started,
        "server_import_ok": imported,
        "jsonrpc_message_seen": jsonrpc_seen,
        "resource_listing_only_hint": resource_listing_only,
        "classification": classification,
    }


def build_external_agent_mcp_surface_summary(*, probe_summary_paths: list[str], out_dir: str = DEFAULT_OUT_DIR) -> dict:
    rows = [_probe_row(path) for path in probe_summary_paths if _norm(path)]
    live_comparison_ready = bool(rows) and all(bool(row.get("shared_tool_plane_reached")) for row in rows)
    classifications = {str(row.get("classification")) for row in rows}
    overall_classification = "insufficient_probe_data"
    if rows:
        if live_comparison_ready:
            overall_classification = "ready"
        elif classifications == {"external_cli_no_jsonrpc_handshake"}:
            overall_classification = "blocked_external_cli_mcp_tool_plane"
        else:
            overall_classification = "tool_plane_unreachable"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if rows else "FAIL",
        "probe_count": len(rows),
        "live_comparison_ready": live_comparison_ready,
        "classification": overall_classification,
        "providers": rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    (out_root / "summary.md").write_text(
        "\n".join(
            [
                "# External Agent MCP Surface Summary",
                "",
                f"- status: `{payload.get('status')}`",
                f"- classification: `{payload.get('classification')}`",
                f"- live_comparison_ready: `{bool(payload.get('live_comparison_ready'))}`",
                "",
                *[
                    (
                        f"- {row.get('provider_name')}: `{row.get('classification')}`"
                        f" (started=`{bool(row.get('server_process_started'))}`,"
                        f" import_ok=`{bool(row.get('server_import_ok'))}`,"
                        f" jsonrpc_seen=`{bool(row.get('jsonrpc_message_seen'))}`,"
                        f" shared_tool_plane_reached=`{bool(row.get('shared_tool_plane_reached'))}`)"
                    )
                    for row in rows
                ],
            ]
        ),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize external-agent MCP surface reachability for v0.3.1.")
    parser.add_argument("--probe-summary", action="append", default=[])
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_external_agent_mcp_surface_summary(
        probe_summary_paths=[str(x) for x in (args.probe_summary or []) if _norm(x)],
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
