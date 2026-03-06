# Agent Modelica Core-Only View

This directory provides a compact view of the minimum files required for the
current MVP objective:

- improve real Modelica repair capability in live workflow
- prove capability changes with reproducible benchmark evidence

Scope file:

- `core_scope_v1.json`: machine-readable core path list

Snapshot command:

```bash
bash scripts/run_agent_modelica_core_view_v1.sh
```

Output:

- `artifacts/agent_modelica_core_view_v1/snapshot.json`
- `artifacts/agent_modelica_core_view_v1/snapshot.md`
