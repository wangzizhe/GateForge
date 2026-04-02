from __future__ import annotations


SOURCE_SPECS: list[dict[str, object]] = [
    {
        "source_id": "init_log_sqrt",
        "model_name": "V0313InitLogSqrt",
        "source_library": "GateForge_v0_3_13_init",
        "source_model_path": "gateforge/source_models/v0_3_13_init/v0313_init_log_sqrt.mo",
        "target_lhs_names": ["y", "x"],
        "model_text": """\
model V0313InitLogSqrt
  Real y(start = 2.0);
  Real x(start = 10.0);
initial equation
  y = 2.0;
  x = 10.0;
equation
  der(y) = -log(y) * y;
  der(x) = 1.0 - sqrt(x);
end V0313InitLogSqrt;""",
    },
    {
        "source_id": "init_tank_growth",
        "model_name": "V0313InitTankGrowth",
        "source_library": "GateForge_v0_3_13_init",
        "source_model_path": "gateforge/source_models/v0_3_13_init/v0313_init_tank_growth.mo",
        "target_lhs_names": ["h", "x"],
        "model_text": """\
model V0313InitTankGrowth
  parameter Real A = 1.0;
  Real h(start = 4.0);
  Real x(start = 4.0);
initial equation
  h = 4.0;
  x = 4.0;
equation
  A * der(h) = 1.0 - sqrt(h);
  der(x) = sqrt(x) * (1.0 - x / 9.0);
end V0313InitTankGrowth;""",
    },
    {
        "source_id": "init_dual_sqrt",
        "model_name": "V0313InitDualSqrt",
        "source_library": "GateForge_v0_3_13_init",
        "source_model_path": "gateforge/source_models/v0_3_13_init/v0313_init_dual_sqrt.mo",
        "target_lhs_names": ["x_fast", "x_slow"],
        "model_text": """\
model V0313InitDualSqrt
  Real x_fast(start = 10.0);
  Real x_slow(start = 4.0);
initial equation
  x_fast = 10.0;
  x_slow = 4.0;
equation
  der(x_fast) = 1.0 - sqrt(x_fast);
  der(x_slow) = 0.5 * sqrt(x_slow) * (1.0 - x_slow / 9.0);
end V0313InitDualSqrt;""",
    },
    {
        "source_id": "init_log_tank",
        "model_name": "V0313InitLogTank",
        "source_library": "GateForge_v0_3_13_init",
        "source_model_path": "gateforge/source_models/v0_3_13_init/v0313_init_log_tank.mo",
        "target_lhs_names": ["y", "h"],
        "model_text": """\
model V0313InitLogTank
  parameter Real A = 1.0;
  Real y(start = 2.0);
  Real h(start = 4.0);
initial equation
  y = 2.0;
  h = 4.0;
equation
  der(y) = -log(y) * y;
  A * der(h) = 1.0 - sqrt(h);
end V0313InitLogTank;""",
    },
    {
        "source_id": "init_log_growth",
        "model_name": "V0313InitLogGrowth",
        "source_library": "GateForge_v0_3_13_init",
        "source_model_path": "gateforge/source_models/v0_3_13_init/v0313_init_log_growth.mo",
        "target_lhs_names": ["y", "x"],
        "model_text": """\
model V0313InitLogGrowth
  Real y(start = 2.0);
  Real x(start = 4.0);
initial equation
  y = 2.0;
  x = 4.0;
equation
  der(y) = -log(y) * y;
  der(x) = sqrt(x) * (1.0 - x / 9.0);
end V0313InitLogGrowth;""",
    },
]
