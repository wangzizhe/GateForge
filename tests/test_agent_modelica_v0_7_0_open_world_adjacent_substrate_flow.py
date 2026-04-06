from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_7_0_closeout import build_v070_closeout
from gateforge.agent_modelica_v0_7_0_handoff_integrity import build_v070_handoff_integrity
from gateforge.agent_modelica_v0_7_0_legacy_bucket_audit import build_v070_legacy_bucket_audit
from gateforge.agent_modelica_v0_7_0_open_world_adjacent_substrate import (
    build_v070_open_world_adjacent_substrate,
)
from gateforge.agent_modelica_v0_7_0_substrate_admission import build_v070_substrate_admission


class AgentModelicaV070OpenWorldAdjacentSubstrateFlowTests(unittest.TestCase):
    def _write_upstream(self, root: Path, *, invalid: bool = False) -> None:
        payloads = {
            "v060.json": {"conclusion": {"version_decision": "v0_6_0_representative_substrate_ready"}, "block_a_substrate": {"case_count": 24}},
            "v061.json": {"conclusion": {"version_decision": "v0_6_1_authority_profile_ready"}},
            "v062.json": {"conclusion": {"version_decision": "v0_6_2_authority_profile_stable"}},
            "v066.json": {
                "conclusion": {
                    "version_decision": "v0_6_6_phase_closeout_supported" if not invalid else "v0_6_6_phase_decision_partial",
                    "do_not_reopen_v0_5_boundary_pressure_by_default": True,
                    "remaining_gap_still_single": True,
                }
            },
        }
        for name, payload in payloads.items():
            (root / name).write_text(json.dumps(payload), encoding="utf-8")

    def test_v070_reaches_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_upstream(root)
            build_v070_handoff_integrity(
                v060_closeout_path=str(root / "v060.json"),
                v061_closeout_path=str(root / "v061.json"),
                v062_closeout_path=str(root / "v062.json"),
                v066_closeout_path=str(root / "v066.json"),
                out_dir=str(root / "integrity"),
            )
            build_v070_open_world_adjacent_substrate(
                v060_closeout_path=str(root / "v060.json"),
                out_dir=str(root / "substrate"),
            )
            build_v070_legacy_bucket_audit(
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            build_v070_substrate_admission(
                substrate_path=str(root / "substrate" / "summary.json"),
                audit_path=str(root / "audit" / "summary.json"),
                out_dir=str(root / "admission"),
            )
            payload = build_v070_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                audit_path=str(root / "audit" / "summary.json"),
                admission_path=str(root / "admission" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_0_open_world_adjacent_substrate_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("dispatch_cleanliness_level"), "promoted")

    def test_v070_partial_when_spillover_is_above_ready_but_below_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_upstream(root)
            build_v070_handoff_integrity(
                v060_closeout_path=str(root / "v060.json"),
                v061_closeout_path=str(root / "v061.json"),
                v062_closeout_path=str(root / "v062.json"),
                v066_closeout_path=str(root / "v066.json"),
                out_dir=str(root / "integrity"),
            )
            build_v070_open_world_adjacent_substrate(
                v060_closeout_path=str(root / "v060.json"),
                out_dir=str(root / "substrate"),
            )
            audit = build_v070_legacy_bucket_audit(
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            audit["spillover_share_pct"] = 25.0
            (root / "audit" / "summary.json").write_text(json.dumps(audit), encoding="utf-8")
            build_v070_substrate_admission(
                substrate_path=str(root / "substrate" / "summary.json"),
                audit_path=str(root / "audit" / "summary.json"),
                out_dir=str(root / "admission"),
            )
            payload = build_v070_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                audit_path=str(root / "audit" / "summary.json"),
                admission_path=str(root / "admission" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_0_open_world_adjacent_substrate_partial")

    def test_v070_invalid_when_upstream_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_upstream(root, invalid=True)
            build_v070_handoff_integrity(
                v060_closeout_path=str(root / "v060.json"),
                v061_closeout_path=str(root / "v061.json"),
                v062_closeout_path=str(root / "v062.json"),
                v066_closeout_path=str(root / "v066.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v070_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                audit_path=str(root / "audit" / "summary.json"),
                admission_path=str(root / "admission" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_0_handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
