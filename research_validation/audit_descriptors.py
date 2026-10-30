"""Check the descriptors added by the author (province, NUTS-1 region, unit type).

1. Province: some ÖSYM tables print the province in parentheses after the university name
   (parse.py stores it as "sehir"). Every such value is compared with dataset/lookups.py.
2. NUTS-1: the province-to-region table is compared with the NUTS-1 classification of Türkiye
   (12 regions, 81 provinces; Eurostat, https://ec.europa.eu/eurostat/web/nuts).
3. Sport management programs per table, and the panels that bridge a missing year.

Writes research_validation/descriptor_audit.json. Run from the repository root after parse.py
and release/build_release.py.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dataset"))
from lookups import IL_IBBS1, UNI_IL  # noqa: E402

NUTS1 = {
    "TR1": ["İstanbul"],
    "TR2": ["Tekirdağ", "Edirne", "Kırklareli", "Balıkesir", "Çanakkale"],
    "TR3": ["İzmir", "Aydın", "Denizli", "Muğla", "Manisa", "Afyonkarahisar", "Kütahya", "Uşak"],
    "TR4": ["Bursa", "Eskişehir", "Bilecik", "Kocaeli", "Sakarya", "Düzce", "Bolu", "Yalova"],
    "TR5": ["Ankara", "Konya", "Karaman"],
    "TR6": ["Antalya", "Isparta", "Burdur", "Adana", "Mersin", "Hatay", "Kahramanmaraş", "Osmaniye"],
    "TR7": ["Kırıkkale", "Aksaray", "Niğde", "Nevşehir", "Kırşehir", "Kayseri", "Sivas", "Yozgat"],
    "TR8": ["Zonguldak", "Karabük", "Bartın", "Kastamonu", "Çankırı", "Sinop", "Samsun", "Tokat", "Çorum", "Amasya"],
    "TR9": ["Trabzon", "Ordu", "Giresun", "Rize", "Artvin", "Gümüşhane"],
    "TRA": ["Erzurum", "Erzincan", "Bayburt", "Ağrı", "Kars", "Iğdır", "Ardahan"],
    "TRB": ["Malatya", "Elazığ", "Bingöl", "Tunceli", "Van", "Muş", "Bitlis", "Hakkari"],
    "TRC": ["Gaziantep", "Adıyaman", "Kilis", "Şanlıurfa", "Diyarbakır", "Mardin", "Batman", "Şırnak", "Siirt"],
}


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

ref = {il: code for code, provinces in NUTS1.items() for il in provinces}
nuts_mismatches = [
    {"province": il, "lookup": IL_IBBS1.get(il), "reference": code}
    for il, code in sorted(ref.items()) if (IL_IBBS1.get(il) or "").split(" ")[0] != code
]
nuts_extra = sorted(set(IL_IBBS1) - set(ref))

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
    "nuts1_provinces_compared": len(ref),
    "nuts1_mismatches": nuts_mismatches,
    "nuts1_extra_provinces_in_lookup": nuts_extra,
    "sport_management_programs_by_table": {f"{y} {r}": n for (y, r), n in sorted(sport_mgmt.items())},
    "panels_absent_in_2025_only": int(len(gap)),
    "of_which_sport_management": int((gap.program_type == "Sport Management").sum()),
}
out = ROOT / "research_validation" / "descriptor_audit.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
