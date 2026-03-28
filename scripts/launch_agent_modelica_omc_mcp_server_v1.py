from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _protocol_trace_path(argv: list[str]) -> Path | None:
    for index, token in enumerate(argv):
        if token == "--protocol-trace-path" and index + 1 < len(argv):
            return Path(argv[index + 1])
    return None


def _append_event(path: Path | None, event: str, **extra: object) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "event": str(event),
        **extra,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def main() -> None:
    trace_path = _protocol_trace_path(sys.argv[1:])
    _append_event(trace_path, "launcher_start", argv=sys.argv[1:], cwd=str(Path.cwd()))
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    try:
        from gateforge.agent_modelica_omc_mcp_server_v1 import main as server_main

        _append_event(trace_path, "launcher_import_ok")
        server_main()
    except Exception as exc:
        _append_event(trace_path, "launcher_error", error=f"{type(exc).__name__}:{exc}")
        raise


if __name__ == "__main__":
    main()
