#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_connector_flow_submit_checkpoint_attribution_v0_34_16 import (
    build_connector_flow_submit_checkpoint_attribution,
)


def main() -> int:
    summary = build_connector_flow_submit_checkpoint_attribution()
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
