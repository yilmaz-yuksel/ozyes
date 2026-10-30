"""Check the descriptors added by the author (province, NUTS-1 region, unit type).

1. Province: some ÖSYM tables print the province in parentheses after the university name
   (parse.py stores it as "sehir"). Every such value is compared with dataset/lookups.py.
2. NUTS-1: the province-to-region table is compared with Eurostat's NUTS 2024 classification.
   The NUTS-3 regions of Türkiye are the 81 provinces, and the first three characters of a
   NUTS-3 code give its NUTS-1 region. The reference file is Eurostat's own export
   (github.com/eurostat/Nuts2json); it is downloaded once into research_validation/official_sources/
   and its SHA-256 checksum is recorded.
3. Sport management programs per table, and the panels that bridge a missing year.

Writes research_validation/descriptor_audit.json. Run from the repository root after parse.py
and release/build_release.py.
"""
import hashlib
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dataset"))
from lookups import IL_IBBS1, UNI_IL  # noqa: E402

NUTS_URL = "https://raw.githubusercontent.com/eurostat/Nuts2json/master/pub/v2/2024/4326/20M/nutsrg_3.json"
NUTS_FILE = ROOT / "research_validation" / "official_sources" / "nuts2024_nutsrg_3.json"


def norm(s):
    s = s.replace("-KIRGIZİSTAN", "").replace(" (Kırgızistan)", "")
    return s.replace("İ", "i").replace("I", "ı").lower().strip()


data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
universities = {r["uni"] for rows in data.values() for r in rows}
printed = defaultdict(set)
for year, rows in data.items():
    for r in rows:
        if r.get("sehir"):
            printed[r["uni"]].add(r["sehir"])
province_mismatches = [
    {"university": u, "printed": sorted(v), "lookup": UNI_IL[u]}
    for u, v in sorted(printed.items()) if any(norm(x) != norm(UNI_IL[u]) for x in v)
]

if not NUTS_FILE.exists():
    NUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(NUTS_URL, timeout=60) as r:
        NUTS_FILE.write_bytes(r.read())
nuts_bytes = NUTS_FILE.read_bytes()
features = json.loads(nuts_bytes)["features"]
tr3 = {f["properties"]["id"]: f["properties"]["na"] for f in features if f["properties"]["id"].startswith("TR")}
ref = {norm(name): code[:3] for code, name in tr3.items()}
nuts_mismatches = [
    {"province": il, "lookup": IL_IBBS1.get(il), "eurostat_nuts1": ref.get(norm(il))}
    for il in sorted(IL_IBBS1) if ref.get(norm(il)) != (IL_IBBS1.get(il) or "").split(" ")[0]
]
nuts_extra = sorted(norm(n) for n in tr3.values() if norm(n) not in {norm(il) for il in IL_IBBS1})

import pandas as pd  # noqa: E402

g = pd.read_csv(ROOT / "release" / "out" / "ozyes_placement_groups.csv", dtype={"osym_program_code": str})
tables = g.drop_duplicates(["year", "placement_round", "osym_program_code"])
sport_mgmt = (tables[tables.program_type == "Sport Management"]
              .groupby(["year", "placement_round"]).size().to_dict())
p = pd.read_csv(ROOT / "release" / "out" / "ozyes_programs.csv", dtype=str)
gap = p[p.osym_code_2024.notna() & p.osym_code_2025.isna() & p.osym_code_2026.notna()]

report = {
    "universities": len(universities),
    "universities_with_printed_province": len(printed),
    "province_mismatches": province_mismatches,
    "nuts_reference": {"source": NUTS_URL, "version": "NUTS 2024", "sha256": hashlib.sha256(nuts_bytes).hexdigest(),
                       "turkiye_nuts3_regions": len(tr3)},
    "nuts1_provinces_compared": len(IL_IBBS1),
    "nuts1_mismatches": nuts_mismatches,
    "eurostat_provinces_missing_from_lookup": nuts_extra,
    "sport_management_programs_by_table": {f"{y} {r}": n for (y, r), n in sorted(sport_mgmt.items())},
    "panels_absent_in_2025_only": int(len(gap)),
    "of_which_sport_management": int((gap.program_type == "Sport Management").sum()),
}
out = ROOT / "research_validation" / "descriptor_audit.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
