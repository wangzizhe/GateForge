#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_asset_discovery_v1_demo"
MODEL_DIR="$OUT_DIR/private_models"
mkdir -p "$MODEL_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$MODEL_DIR"/*.mo

cat > "$MODEL_DIR/MediumThermalPlant.mo" <<'MO'
model MediumThermalPlant
  parameter Real k1=1;
  parameter Real k2=2;
  parameter Real k3=3;
  parameter Real k4=4;
  parameter Real k5=5;
  parameter Real k6=6;
  parameter Real k7=7;
  parameter Real k8=8;
  parameter Real k9=9;
  parameter Real k10=10;
  parameter Real k11=11;
  parameter Real k12=12;
  parameter Real k13=13;
  parameter Real k14=14;
  parameter Real k15=15;
  parameter Real k16=16;
  Real x;
  Real y;
  Real z;
  Real w;
  Real q;
  Real p;
  Real r;
  Real s;
  Real t;
  Real u;
  Real v;
  Real m;
  Real n;
  Real a;
  Real b;
  Real c;
  Real d;
  Real e;
  Real f;
  Real g;
  Real h;
  Real i;
  Real j;
  Real o;
  Real l;
  Real aa;
  Real bb;
  Real cc;
  Real dd;
  Real ee;
  Real ff;
  Real gg;
  Real hh;
  Real ii;
  Real jj;
  Real kk;
  Real ll;
  Real mm;
  Real nn;
  Real oo;
  Real pp;
  Real qq;
  Real rr;
  Real ss;
  Real tt;
  Real uu;
  Real vv;
  Real ww;
  Real xx;
  Real yy;
  Real zz;
equation
  der(x)=k1*x-k2*y+k3;
  der(y)=k4*x-k5*y+k6;
  der(z)=k7*y-k8*z+k9;
  der(w)=k10*z-k11*w+k12;
  der(q)=k13*w-k14*q+k15;
  der(p)=k16*q-k1*p+k2;
end MediumThermalPlant;
MO

cat > "$MODEL_DIR/LargeHydraulicGrid.mo" <<'MO'
model LargeHydraulicGrid
  parameter Real p1=1;
  parameter Real p2=2;
  parameter Real p3=3;
  parameter Real p4=4;
  parameter Real p5=5;
  parameter Real p6=6;
  parameter Real p7=7;
  parameter Real p8=8;
  parameter Real p9=9;
  parameter Real p10=10;
  parameter Real p11=11;
  parameter Real p12=12;
  parameter Real p13=13;
  parameter Real p14=14;
  parameter Real p15=15;
  parameter Real p16=16;
  parameter Real p17=17;
  parameter Real p18=18;
  parameter Real p19=19;
  parameter Real p20=20;
  Real s1; Real s2; Real s3; Real s4; Real s5; Real s6; Real s7; Real s8;
  Real s9; Real s10; Real s11; Real s12; Real s13; Real s14; Real s15; Real s16;
  Real s17; Real s18; Real s19; Real s20; Real s21; Real s22; Real s23; Real s24;
  Real s25; Real s26; Real s27; Real s28; Real s29; Real s30; Real s31; Real s32;
  Real s33; Real s34; Real s35; Real s36; Real s37; Real s38; Real s39; Real s40;
  Real s41; Real s42; Real s43; Real s44; Real s45; Real s46; Real s47; Real s48;
  Real s49; Real s50; Real s51; Real s52; Real s53; Real s54; Real s55; Real s56;
  Real s57; Real s58; Real s59; Real s60; Real s61; Real s62; Real s63; Real s64;
  Real s65; Real s66; Real s67; Real s68; Real s69; Real s70; Real s71; Real s72;
  Real s73; Real s74; Real s75; Real s76; Real s77; Real s78; Real s79; Real s80;
  Real s81; Real s82; Real s83; Real s84; Real s85; Real s86; Real s87; Real s88;
  Real s89; Real s90; Real s91; Real s92; Real s93; Real s94; Real s95; Real s96;
  Real s97; Real s98; Real s99; Real s100;
equation
  der(s1)=p1*s2-p2*s3+p3;
  der(s2)=p4*s3-p5*s4+p6;
  der(s3)=p7*s4-p8*s5+p9;
  der(s4)=p10*s5-p11*s6+p12;
  der(s5)=p13*s6-p14*s7+p15;
  der(s6)=p16*s7-p17*s8+p18;
  der(s7)=p19*s8-p20*s9+p1;
  der(s8)=p2*s9-p3*s10+p4;
  der(s9)=p5*s10-p6*s11+p7;
  der(s10)=p8*s11-p9*s12+p10;
  der(s11)=p11*s12-p12*s13+p13;
  der(s12)=p14*s13-p15*s14+p16;
  der(s13)=p17*s14-p18*s15+p19;
  der(s14)=p20*s15-p1*s16+p2;
  der(s15)=p3*s16-p4*s17+p5;
  der(s16)=p6*s17-p7*s18+p8;
  der(s17)=p9*s18-p10*s19+p11;
  der(s18)=p12*s19-p13*s20+p14;
  der(s19)=p15*s20-p16*s21+p17;
  der(s20)=p18*s21-p19*s22+p20;
end LargeHydraulicGrid;
MO

python3 -m gateforge.dataset_real_model_asset_discovery_v1 \
  --model-root "$MODEL_DIR" \
  --source-name "private_asset_demo" \
  --source-domain "energy" \
  --license-tag "Apache-2.0" \
  --catalog-out "$OUT_DIR/candidate_catalog.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_real_model_asset_discovery_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "candidates_present": "PASS" if int(summary.get("total_candidates", 0)) >= 2 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "discovery_status": summary.get("status"),
    "total_candidates": summary.get("total_candidates"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "discovery_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
