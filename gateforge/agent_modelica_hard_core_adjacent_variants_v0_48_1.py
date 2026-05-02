from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_adjacent_plan_v0_48_0 import ANCHOR_CASE_IDS


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_variants_v0_48_1"


def _sem13_model(model_name: str, count: int, resistors: tuple[int, ...]) -> str:
    r_values = ",".join(str(value) for value in resistors)
    return f"""model {model_name}
  connector Pin
    Real v;
    flow Real i;
  end Pin;
  partial model ProbeBase
    Pin p;
    Pin n;
    output Real y;
  end ProbeBase;
  model VoltageProbe
    extends ProbeBase;
  equation
    y = p.v - n.v;
  end VoltageProbe;
  model CurrentProbe
    extends ProbeBase;
  equation
    y = p.i;
  end CurrentProbe;
  replaceable model Probe = VoltageProbe constrainedby ProbeBase;
  model Branch
    Pin a;
    Pin b;
    parameter Real R=10;
  equation
    a.i = (a.v - b.v) / R;
    b.i = -a.i;
  end Branch;
  Pin supply;
  Pin ground;
  Branch branch[{count}](R={{{r_values}}});
  Probe probe[{count}];
  Real readings[{count}];
equation
  supply.v = 5;
  ground.v = 0;
  for i in 1:{count} loop
    connect(supply, branch[i].a);
    connect(branch[i].b, ground);
    connect(probe[i].p, branch[i].a);
    connect(probe[i].n, branch[i].b);
    readings[i] = probe[i].y;
  end for;
end {model_name};
"""


def _sem26_model(model_name: str, count: int, resistors: tuple[int, ...], source_v: int) -> str:
    r_values = ",".join(str(value) for value in resistors)
    node_decls = "\n  ".join(f"Pin mid{i};" for i in range(1, count))
    low_node = lambda idx: "sink" if idx == count else f"mid{idx}"  # noqa: E731
    high_node = lambda idx: "source" if idx == 1 else f"mid{idx - 1}"  # noqa: E731
    segment_connections = "\n  ".join(
        [
            f"connect({high_node(i)}, seg[{i}].left);\n  connect(seg[{i}].right, {low_node(i)});"
            for i in range(1, count + 1)
        ]
    )
    adapter_connections = "\n  ".join(
        [
            f"connect(adapter.high[{i}], {high_node(i)});\n  connect(adapter.low[{i}], {low_node(i)});"
            for i in range(1, count + 1)
        ]
    )
    total = " + ".join(f"adapter.y[{i}]" for i in range(1, count + 1))
    return f"""model {model_name}
  connector Pin
    Real v;
    flow Real i;
  end Pin;
  partial model AdapterBase
    Pin high[{count}];
    Pin low[{count}];
    output Real y[{count}];
  end AdapterBase;
  model VoltageAdapter
    extends AdapterBase;
  equation
    for i in 1:{count} loop
      y[i] = high[i].v - low[i].v;
    end for;
  end VoltageAdapter;
  model Segment
    Pin left;
    Pin right;
    parameter Real R=10;
  equation
    left.i = (left.v - right.v) / R;
    right.i = -left.i;
  end Segment;
  replaceable model Adapter = VoltageAdapter constrainedby AdapterBase;
  Pin source;
  {node_decls}
  Pin sink;
  Segment seg[{count}](R={{{r_values}}});
  Adapter adapter;
  Real yTotal;
equation
  source.v = {source_v};
  sink.v = 0;
  {segment_connections}
  {adapter_connections}
  yTotal = {total};
end {model_name};
"""


def _singleroot_model(model_name: str, count: int, resistors: tuple[int, ...], capacitors: tuple[float, ...]) -> str:
    r_values = ", ".join(str(value) for value in resistors)
    c_values = ", ".join(str(value) for value in capacitors)
    return f"""model {model_name}
  partial model ProbeBase
    Modelica.Electrical.Analog.Interfaces.PositivePin p;
    Modelica.Electrical.Analog.Interfaces.NegativePin n;
    output Real v;
  equation
    v = p.v - n.v;
  end ProbeBase;

  model BranchProbe
    extends ProbeBase;
  equation
    0 = p.i + n.i;
  end BranchProbe;

  replaceable model Probe = BranchProbe constrainedby ProbeBase;
  parameter Integer n = {count};
  Modelica.Electrical.Analog.Sources.StepVoltage V1(V=5, startTime=0.01);
  Modelica.Electrical.Analog.Basic.Resistor R[n](R={{{r_values}}});
  Modelica.Electrical.Analog.Basic.Capacitor C[n](C={{{c_values}}});
  Modelica.Electrical.Analog.Basic.Ground G;
  Probe probe[n];
  Real observed[n];
equation
  connect(V1.n, G.p);
  for i in 1:n loop
    connect(V1.p, R[i].p);
    connect(R[i].n, C[i].p);
    connect(C[i].n, V1.n);
    connect(probe[i].p, C[i].p);
    connect(probe[i].n, C[i].n);
    observed[i] = probe[i].v;
  end for;
end {model_name};
"""


def _task(
    *,
    case_id: str,
    title: str,
    description: str,
    model_name: str,
    initial_model: str,
    anchor_case_id: str,
    variant_axis: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "task_type": "repair",
        "title": title,
        "difficulty": "complex",
        "source_backed": True,
        "benchmark_focus": "model_check_structural",
        "description": description,
        "initial_model": initial_model,
        "constraints": [
            "Keep model name unchanged.",
            "Preserve the declared abstraction and reported measurement variables.",
            "Do not replace the network with a trivial equation-only model.",
        ],
        "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
        "lineage": {
            "anchor_case_id": anchor_case_id,
            "variant_axis": variant_axis,
            "generation": "hard_core_adjacent_v0_48",
        },
    }


def build_hard_core_adjacent_variants(*, version: str = "v0.48.1") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    variants = [
        _task(
            case_id="sem_28_four_branch_probe_bus",
            title="Repair four-branch arrayed probe bus",
            description="A branch measurement refactor moved four measurements behind an arrayed replaceable probe interface. Repair the measurement contract while preserving the branch topology and readings.",
            model_name="SemFourBranchProbeBus",
            initial_model=_sem13_model("SemFourBranchProbeBus", 4, (10, 20, 30, 40)),
            anchor_case_id="sem_13_arrayed_connector_bus_refactor",
            variant_axis="branch_count_plus_one",
        ),
        _task(
            case_id="sem_29_two_branch_probe_bus",
            title="Repair two-branch arrayed probe bus",
            description="A compact branch measurement refactor moved two measurements behind an arrayed replaceable probe interface. Repair the measurement contract while preserving the topology and readings.",
            model_name="SemTwoBranchProbeBus",
            initial_model=_sem13_model("SemTwoBranchProbeBus", 2, (12, 33)),
            anchor_case_id="sem_13_arrayed_connector_bus_refactor",
            variant_axis="branch_count_minus_one",
        ),
        _task(
            case_id="sem_30_wide_probe_bus",
            title="Repair wide arrayed probe bus",
            description="A wider branch measurement workflow moved five branch readings behind an arrayed replaceable probe interface. Repair the measurement contract without flattening the network.",
            model_name="SemWideProbeBus",
            initial_model=_sem13_model("SemWideProbeBus", 5, (8, 13, 21, 34, 55)),
            anchor_case_id="sem_13_arrayed_connector_bus_refactor",
            variant_axis="wider_bus",
        ),
        _task(
            case_id="sem_31_probe_bus_resistance_shift",
            title="Repair shifted-resistance probe bus",
            description="A branch measurement refactor changed the branch resistance profile while keeping the arrayed replaceable probe interface. Repair the measurement contract and preserve all readings.",
            model_name="SemProbeBusResistanceShift",
            initial_model=_sem13_model("SemProbeBusResistanceShift", 3, (15, 47, 82)),
            anchor_case_id="sem_13_arrayed_connector_bus_refactor",
            variant_axis="parameter_profile_shift",
        ),
        _task(
            case_id="sem_32_four_segment_adapter_cross_node",
            title="Repair four-segment arrayed adapter",
            description="A segment measurement migration introduced an arrayed adapter across four shared nodes. Repair the model while preserving the segment network, adapter abstraction, and total measurement.",
            model_name="SemFourSegmentAdapterCrossNode",
            initial_model=_sem26_model("SemFourSegmentAdapterCrossNode", 4, (20, 30, 50, 70), 20),
            anchor_case_id="sem_26_three_segment_adapter_cross_node",
            variant_axis="segment_count_plus_one",
        ),
        _task(
            case_id="sem_33_two_segment_adapter_cross_node",
            title="Repair two-segment arrayed adapter",
            description="A compact segment measurement migration introduced an arrayed adapter across two shared nodes. Repair the model while preserving the adapter abstraction and total measurement.",
            model_name="SemTwoSegmentAdapterCrossNode",
            initial_model=_sem26_model("SemTwoSegmentAdapterCrossNode", 2, (25, 75), 10),
            anchor_case_id="sem_26_three_segment_adapter_cross_node",
            variant_axis="segment_count_minus_one",
        ),
        _task(
            case_id="sem_34_ladder_adapter_cross_node",
            title="Repair ladder adapter cross-node measurement",
            description="A ladder-style segment workflow moved measurements into an arrayed adapter across shared nodes. Repair the model while preserving the adapter abstraction and aggregate measurement.",
            model_name="SemLadderAdapterCrossNode",
            initial_model=_sem26_model("SemLadderAdapterCrossNode", 5, (10, 20, 30, 40, 50), 25),
            anchor_case_id="sem_26_three_segment_adapter_cross_node",
            variant_axis="wider_segment_ladder",
        ),
        _task(
            case_id="sem_35_adapter_resistance_shift",
            title="Repair shifted adapter cross-node measurement",
            description="A segment measurement migration changed the resistance profile while preserving an arrayed adapter across shared nodes. Repair the model and keep the total measurement.",
            model_name="SemAdapterResistanceShift",
            initial_model=_sem26_model("SemAdapterResistanceShift", 3, (18, 56, 91), 15),
            anchor_case_id="sem_26_three_segment_adapter_cross_node",
            variant_axis="parameter_profile_shift",
        ),
        _task(
            case_id="singleroot2_03_three_branch_replaceable_probe_array",
            title="Repair three-branch replaceable probe array",
            description="A reusable probe abstraction was migrated into a replaceable array component for a three-branch RC workflow. Restore a structurally valid Modelica model while preserving the probe-array abstraction.",
            model_name="SingleRootThreeBranchReplaceableProbeArray",
            initial_model=_singleroot_model("SingleRootThreeBranchReplaceableProbeArray", 3, (100, 220, 330), (0.001, 0.0022, 0.0033)),
            anchor_case_id="singleroot2_02_replaceable_probe_array",
            variant_axis="branch_count_plus_one",
        ),
        _task(
            case_id="singleroot2_04_four_branch_replaceable_probe_array",
            title="Repair four-branch replaceable probe array",
            description="A reusable probe abstraction was migrated into a replaceable array component for a four-branch RC workflow. Restore a structurally valid Modelica model while preserving the arrayed workflow.",
            model_name="SingleRootFourBranchReplaceableProbeArray",
            initial_model=_singleroot_model("SingleRootFourBranchReplaceableProbeArray", 4, (68, 100, 150, 220), (0.00068, 0.001, 0.0015, 0.0022)),
            anchor_case_id="singleroot2_02_replaceable_probe_array",
            variant_axis="wider_branch_array",
        ),
        _task(
            case_id="singleroot2_05_probe_array_parameter_shift",
            title="Repair shifted replaceable probe array",
            description="A replaceable probe-array migration changed branch parameters in a parallel RC workflow. Restore a structurally valid Modelica model while preserving the probe-array abstraction.",
            model_name="SingleRootProbeArrayParameterShift",
            initial_model=_singleroot_model("SingleRootProbeArrayParameterShift", 2, (47, 680), (0.00047, 0.0068)),
            anchor_case_id="singleroot2_02_replaceable_probe_array",
            variant_axis="parameter_profile_shift",
        ),
        _task(
            case_id="singleroot2_06_wide_probe_array",
            title="Repair wide replaceable probe array",
            description="A reusable probe abstraction was migrated into a wider replaceable array component for a multi-branch RC workflow. Restore a structurally valid Modelica model without deleting the arrayed workflow.",
            model_name="SingleRootWideProbeArray",
            initial_model=_singleroot_model("SingleRootWideProbeArray", 5, (33, 68, 100, 220, 470), (0.00033, 0.00068, 0.001, 0.0022, 0.0047)),
            anchor_case_id="singleroot2_02_replaceable_probe_array",
            variant_axis="wide_branch_array",
        ),
    ]
    anchor_counts: dict[str, int] = {}
    for variant in variants:
        anchor = str(variant["lineage"]["anchor_case_id"])
        anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1
    return (
        {
            "version": version,
            "analysis_scope": "hard_core_adjacent_variants",
            "status": "PASS" if set(anchor_counts) == set(ANCHOR_CASE_IDS) and len(variants) >= 12 else "REVIEW",
            "evidence_role": "debug",
            "conclusion_allowed": False,
            "variant_count": len(variants),
            "anchor_counts": dict(sorted(anchor_counts.items())),
            "case_ids": [str(variant["case_id"]) for variant in variants],
            "scope_note": "These are adjacent benchmark candidates, not admitted hard negatives.",
        },
        variants,
    )


def write_hard_core_adjacent_variants_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    variants: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "tasks.jsonl").open("w", encoding="utf-8") as fh:
        for variant in variants:
            fh.write(json.dumps(variant, sort_keys=True) + "\n")
    task_dir = out_dir / "task_files"
    task_dir.mkdir(parents=True, exist_ok=True)
    for variant in variants:
        (task_dir / f"{variant['case_id']}.json").write_text(
            json.dumps(variant, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def run_hard_core_adjacent_variants(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary, variants = build_hard_core_adjacent_variants()
    write_hard_core_adjacent_variants_outputs(out_dir=out_dir, summary=summary, variants=variants)
    return summary
