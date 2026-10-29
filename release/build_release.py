"""Build the English-language public release of the ÖZYES placement dataset.

Input : the Turkish research dataset written by dataset/build_dataset.py
        (ozyes_veriseti.csv and ozyes_veriseti.xlsx), plus dataset/osym_ozet.py.
Output: release/out/
          ozyes_placement_groups.csv   one row per year x round x program x quota type x sex
          ozyes_programs.csv           one row per program tracking panel
          ozyes_universities.csv       one row per university
          ozyes_official_totals.csv    dataset totals next to the published ÖSYM summary totals
          ozyes_quota_transfer.csv     one row per year x round x program x sex (transfer check)
          codebook.csv                 variable definitions for all files
          SHA256SUMS.txt               checksums of the files above

The script only renames, recodes and re-aggregates; it never changes a value of the
Turkish dataset. It stops with an error if any check fails.

Usage (from the project root):
    python release/build_release.py [path/to/dataset/out]
"""
import csv
import hashlib
import sys
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dataset"))
from osym_ozet import OSYM, TERCIH  # noqa: E402

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dataset" / "out"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

# ------------------------------------------------------------------ code tables
ROUND = {"İlk yerleştirme": "initial", "Ek yerleştirme": "supplementary"}
UNI_TYPE = {"Devlet": "public", "Vakıf": "foundation"}
UNIT_TYPE = {"Fakülte": "faculty", "Yüksekokul": "school"}
PROGRAM_TYPE = {
    "Antrenörlük Eğitimi": "Coaching Education",
    "Beden Eğitimi ve Spor Öğretmenliği": "Physical Education and Sports Teaching",
    "Spor Yöneticiliği": "Sport Management",
    "Rekreasyon": "Recreation",
    "Egzersiz ve Spor Bilimleri": "Exercise and Sport Sciences",
    "Engellilerde Egzersiz ve Spor Bilimleri": "Exercise and Sport Sciences for People with Disabilities",
    "Engellilerde Beden Eğitimi ve Spor Öğretmenliği": "Physical Education and Sports Teaching for People with Disabilities",
}
TUITION = {
    "Ücret ayrımı yok": "no_distinction",
    "Burslu": "full_scholarship",
    "%50 İndirimli": "discount_50",
    "%25 İndirimli": "discount_25",
    "Ücretli": "fee_paying",
}
LANGUAGE = {"Türkçe": "Turkish", "İngilizce": "English"}
QUOTA = {"Genel": "general", "Milli sporcu": "national_athlete", "Engelli aday": "disability"}
SEX = {"Erkek": "male", "Kadın": "female"}
YESNO = {"Evet": 1, "Hayır": 0}
NUTS1_EN = {
    "TR1": "Istanbul", "TR2": "West Marmara", "TR3": "Aegean", "TR4": "East Marmara",
    "TR5": "West Anatolia", "TR6": "Mediterranean", "TR7": "Central Anatolia",
    "TR8": "West Black Sea", "TR9": "East Black Sea", "TRA": "Northeast Anatolia",
    "TRB": "Central East Anatolia", "TRC": "Southeast Anatolia",
}
REGION = {
    "Marmara": "Marmara", "Ege": "Aegean", "Akdeniz": "Mediterranean", "İç Anadolu": "Central Anatolia",
    "Karadeniz": "Black Sea", "Doğu Anadolu": "Eastern Anatolia", "Güneydoğu Anadolu": "Southeastern Anatolia",
    "Yurt dışı": "outside_Turkey",
}


def recode(series, mapping, name):
    out = series.map(lambda v: mapping[v] if pd.notna(v) else pd.NA)
    unmapped = series[series.notna() & out.isna()].unique()
    if len(unmapped):
        raise SystemExit(f"{name}: unmapped values {list(unmapped)}")
    return out


def nuts_code(v):
    return "abroad" if v == "Yurt dışı" else v.split(" ", 1)[0]


# ------------------------------------------------------------------ 1. placement groups
tr = pd.read_csv(SRC / "ozyes_veriseti.csv", dtype={"program_kodu": str}, encoding="utf-8-sig")
assert tr.shape == (7170, 33), tr.shape

g = pd.DataFrame({
    "year": tr.yil,
    "placement_round": recode(tr.yerlestirme, ROUND, "yerlestirme"),
    "program_panel_id": tr.panel_id,
    "program_group_id": tr.program_grup_id,
    "osym_program_code": tr.program_kodu,
    "university": tr.universite,
    "university_type": recode(tr.uni_turu, UNI_TYPE, "uni_turu"),
    "province": tr.il,
    "nuts1_code": tr.ibbs1.map(nuts_code),
    "geographic_region": recode(tr.cografi_bolge, REGION, "cografi_bolge"),
    "academic_unit": tr.birim,
    "unit_type": recode(tr.birim_turu, UNIT_TYPE, "birim_turu"),
    "program_name_tr": tr.program_adi,
    "program_type": recode(tr.program_turu, PROGRAM_TYPE, "program_turu"),
    "tuition_status": recode(tr.ucret_durumu, TUITION, "ucret_durumu"),
    "language_of_instruction": recode(tr.ogretim_dili, LANGUAGE, "ogretim_dili"),
    "quota_type": recode(tr.kontenjan_turu, QUOTA, "kontenjan_turu"),
    "sex": recode(tr.cinsiyet, SEX, "cinsiyet"),
    "quota": tr.kontenjan,
    "placed": tr.yerlesen,
    "min_score": tr.en_kucuk_puan,
    "max_score": tr.en_buyuk_puan,
    "fill_ratio": tr.doluluk_orani,
    "group_vacancy": tr.bos_kontenjan,
    "quota_filled": recode(tr.kontenjan_doldu, YESNO, "kontenjan_doldu").astype("Int64"),
    "score_range": tr.puan_araligi,
    "initial_min_score_same_year": tr.ilk_en_kucuk_puan,
    "suppl_minus_initial_min_score": tr.ek_ilk_farki,
    "prev_year_min_score": tr.onceki_yil_en_kucuk_puan,
    "min_score_change": tr.en_kucuk_puan_degisim,
    "code_changed": recode(tr.kod_degisti, YESNO, "kod_degisti").astype("Int64"),
    "boundary_score_flag": recode(tr.uc_puan, YESNO, "uc_puan").astype("Int64"),
    "program_counter": tr.program_sayac,
})
assert set(g.nuts1_code) - set(NUTS1_EN) <= {"abroad"}
# value-preservation check: every numeric column must equal the Turkish source exactly
for en, trc in [("quota", "kontenjan"), ("placed", "yerlesen"), ("min_score", "en_kucuk_puan"),
                ("max_score", "en_buyuk_puan"), ("fill_ratio", "doluluk_orani"), ("group_vacancy", "bos_kontenjan"),
                ("score_range", "puan_araligi"), ("initial_min_score_same_year", "ilk_en_kucuk_puan"),
                ("suppl_minus_initial_min_score", "ek_ilk_farki"), ("prev_year_min_score", "onceki_yil_en_kucuk_puan"),
                ("min_score_change", "en_kucuk_puan_degisim"), ("program_counter", "program_sayac")]:
    a, b = g[en], tr[trc]
    if not ((a == b) | (a.isna() & b.isna())).all():
        raise SystemExit(f"value mismatch in {en}")
key = ["year", "placement_round", "osym_program_code", "quota_type", "sex"]
assert not g.duplicated(key).any()
g.to_csv(OUT / "ozyes_placement_groups.csv", index=False, encoding="utf-8", lineterminator="\n")

# ------------------------------------------------------------------ 2. programs (panels)
wb = openpyxl.load_workbook(SRC / "ozyes_veriseti.xlsx", read_only=True, data_only=False)
rows = list(wb["Program_Panel"].iter_rows(values_only=True))
pp = pd.DataFrame(rows[1:], columns=rows[0])
assert len(pp) == g.program_panel_id.nunique() == 413
years = sorted(g.year.unique())
p = pd.DataFrame({
    "program_panel_id": pp.panel_id,
    "program_group_id": pp.program_grup_id,
    "university": pp.universite,
    "university_type": recode(pp.uni_turu, UNI_TYPE, "uni_turu"),
    "province": pp.il,
    "academic_unit": pp.birim,
    "program_name_tr": pp.program_adi,
    "program_type": recode(pp.program_turu, PROGRAM_TYPE, "program_turu"),
    "tuition_status": recode(pp.ucret_durumu, TUITION, "ucret_durumu"),
    "language_of_instruction": recode(pp.ogretim_dili, LANGUAGE, "ogretim_dili"),
    **{f"osym_code_{y}": pp[f"kod_{y}"].map(lambda v: str(v) if pd.notna(v) and v != "" else pd.NA) for y in years},
    "years_present": pp.bulundugu_yillar.str.replace(", ", ";"),
    "n_years": pp.yil_sayisi,
    "code_changed": recode(pp.kod_degisti, YESNO, "kod_degisti").astype("Int64"),
})
# cross-check panel table against the long table (initial placement codes per year)
ini = g[g.placement_round == "initial"].drop_duplicates(["year", "osym_program_code"])
for y in years:
    a = dict(zip(ini[ini.year == y].program_panel_id, ini[ini.year == y].osym_program_code))
    b = p.set_index("program_panel_id")[f"osym_code_{y}"].dropna().to_dict()
    if a != b:
        raise SystemExit(f"panel/code mismatch in {y}")
p.to_csv(OUT / "ozyes_programs.csv", index=False, encoding="utf-8", lineterminator="\n")

# ------------------------------------------------------------------ 3. universities
u = (g.drop_duplicates("university")[["university", "university_type", "province", "nuts1_code", "geographic_region"]]
     .sort_values("university").reset_index(drop=True))
for y in years:
    cnt = ini[ini.year == y].groupby("university").osym_program_code.nunique()
    u[f"n_programs_initial_{y}"] = u.university.map(cnt).fillna(0).astype(int)
assert len(u) == 108
u.to_csv(OUT / "ozyes_universities.csv", index=False, encoding="utf-8", lineterminator="\n")

# ------------------------------------------------------------------ 4. official totals
recs = []
for (y, r, t), (np_, q, pl, v) in sorted(OSYM.items()):
    rnd = "initial" if r == 1 else "supplementary"
    ut = "public" if t == 1 else "foundation"
    s = g[(g.year == y) & (g.placement_round == rnd) & (g.university_type == ut)]
    d = {"programs": int(s.program_counter.sum()), "quota": int(s.quota.sum()), "placed": int(s.placed.sum())}
    d["net_vacancy"] = d["quota"] - d["placed"]
    rec = {"year": y, "placement_round": rnd, "university_type": ut}
    for k, off in zip(["programs", "quota", "placed", "net_vacancy"], [np_, q, pl, v]):
        rec[f"{k}_osym"] = off
        rec[f"{k}_dataset"] = d[k]
        rec[f"{k}_difference"] = d[k] - off
    rec["candidates_with_preferences_osym"] = TERCIH[(y, r)]
    recs.append(rec)
ot = pd.DataFrame(recs)
diff_cols = [c for c in ot if c.endswith("_difference")]
if (ot[diff_cols] != 0).any().any():
    raise SystemExit("official totals differ")
ot.to_csv(OUT / "ozyes_official_totals.csv", index=False, encoding="utf-8", lineterminator="\n")

# ------------------------------------------------------------------ 5. quota transfer check
SOURCE = {"initial": "national_athlete", "supplementary": "disability"}
OTHER = {"initial": "disability", "supplementary": None}
pv = g.pivot_table(index=["year", "placement_round", "osym_program_code", "sex"], columns="quota_type",
                   values=["quota", "placed"], aggfunc="sum", fill_value=0)
pv.columns = [f"{a}_{b}" for a, b in pv.columns]
for qt in QUOTA.values():
    for m in ("quota", "placed"):
        pv[f"{m}_{qt}"] = pv.get(f"{m}_{qt}", 0)
pv = pv.reset_index()
meta = g.drop_duplicates(["year", "placement_round", "osym_program_code"])[
    ["year", "placement_round", "osym_program_code", "program_panel_id", "university", "university_type", "program_type"]]
pv = pv.merge(meta, on=["year", "placement_round", "osym_program_code"], how="left")
t = pd.DataFrame({
    "year": pv.year, "placement_round": pv.placement_round, "osym_program_code": pv.osym_program_code,
    "program_panel_id": pv.program_panel_id, "university": pv.university, "university_type": pv.university_type,
    "program_type": pv.program_type, "sex": pv.sex,
})
t["transfer_source_quota_type"] = t.placement_round.map(SOURCE)
t["general_quota"] = pv.quota_general
t["general_placed"] = pv.placed_general
t["source_quota"] = [row[f"quota_{SOURCE[r]}"] for r, (_, row) in zip(pv.placement_round, pv.iterrows())]
t["source_placed"] = [row[f"placed_{SOURCE[r]}"] for r, (_, row) in zip(pv.placement_round, pv.iterrows())]
t["other_quota"] = [row[f"quota_{OTHER[r]}"] if OTHER[r] else 0 for r, (_, row) in zip(pv.placement_round, pv.iterrows())]
t["other_placed"] = [row[f"placed_{OTHER[r]}"] if OTHER[r] else 0 for r, (_, row) in zip(pv.placement_round, pv.iterrows())]
t["general_excess"] = (t.general_placed - t.general_quota).clip(lower=0)
t["source_vacancy"] = (t.source_quota - t.source_placed).clip(lower=0)
t["source_excess"] = (t.source_placed - t.source_quota).clip(lower=0)
t["other_excess"] = (t.other_placed - t.other_quota).clip(lower=0)
t["excess_within_source_vacancy"] = (t.general_excess <= t.source_vacancy).astype(int)
t["excess_equals_source_vacancy"] = ((t.general_excess > 0) & (t.general_excess == t.source_vacancy)).astype(int)
t["post_transfer_vacancy"] = ((t.general_quota + t.source_quota - t.general_placed - t.source_placed).clip(lower=0)
                              + (t.other_quota - t.other_placed).clip(lower=0))
t = t.sort_values(["year", "placement_round", "osym_program_code", "sex"], key=lambda s: s.map({"male": 0, "female": 1}) if s.name == "sex" else s).reset_index(drop=True)
t.to_csv(OUT / "ozyes_quota_transfer.csv", index=False, encoding="utf-8", lineterminator="\n")

# ------------------------------------------------------------------ 6. codebook
CB = [
    # file, variable, type, description
    ("placement_groups", "year", "integer", "Placement year of the ÖSYM table."),
    ("placement_groups", "placement_round", "categorical", "initial = initial placement; supplementary = supplementary placement of the same year."),
    ("placement_groups", "program_panel_id", "string", "Program tracking identifier (OZY0001...). Stays constant across years even when the ÖSYM program code changes. Use as the unit identifier in longitudinal analyses."),
    ("placement_groups", "program_group_id", "string", "Program group identifier (G001...): same university + program type + language of instruction. Groups scholarship, discounted and fee-paying options of one program."),
    ("placement_groups", "osym_program_code", "string", "Nine-digit ÖSYM program code of that year's table. Stored as text."),
    ("placement_groups", "university", "string", "University name as in the ÖSYM table (Turkish, upper case), with the province in parentheses, the 'Devlet/Vakıf Üniversitesi' suffix and footnote marks removed."),
    ("placement_groups", "university_type", "categorical", "public = state university; foundation = foundation (non-profit private) university, as given in the ÖSYM table. Kyrgyz-Turkish Manas University is listed as a foundation university in the table and is coded accordingly."),
    ("placement_groups", "province", "string", "Province of the university's main campus (added by the authors; Turkish spelling). A program may run on a campus in another district."),
    ("placement_groups", "nuts1_code", "categorical", "NUTS-1 / İBBS Level 1 region code of the province (TR1...TRC); 'abroad' for the university located outside Turkey."),
    ("placement_groups", "geographic_region", "categorical", "One of the seven traditional geographic regions of Turkey, derived from the province; 'outside_Turkey' otherwise."),
    ("placement_groups", "academic_unit", "string", "Faculty or school name (Turkish). Upper-case spellings in the 2026 table were harmonised to the previous year's spelling or to Turkish title case."),
    ("placement_groups", "unit_type", "categorical", "faculty; school (unit name contains 'Yüksekokul')."),
    ("placement_groups", "program_name_tr", "string", "Program name as printed in the table, including tuition and language suffixes (Turkish)."),
    ("placement_groups", "program_type", "categorical", "Program type in English, obtained by removing tuition and language suffixes from the program name: " + "; ".join(PROGRAM_TYPE.values()) + "."),
    ("placement_groups", "tuition_status", "categorical", "no_distinction (public universities and programs without a suffix); full_scholarship; discount_50; discount_25; fee_paying."),
    ("placement_groups", "language_of_instruction", "categorical", "Turkish; English (program name contains '(İngilizce)')."),
    ("placement_groups", "quota_type", "categorical", "general; national_athlete; disability. Supplementary placement tables have no national_athlete quota."),
    ("placement_groups", "sex", "categorical", "male; female. Sex for which the quota is reserved."),
    ("placement_groups", "quota", "integer", "Quota in the ÖSYM table (in the supplementary placement: supplementary quota). May be 0 in the supplementary placement while placed > 0."),
    ("placement_groups", "placed", "integer", "Number of placed candidates in the ÖSYM table. Can exceed quota (see ozyes_quota_transfer.csv)."),
    ("placement_groups", "min_score", "decimal (5 d.p.)", "Lowest placement score of the group. Empty when no candidate was placed."),
    ("placement_groups", "max_score", "decimal (5 d.p.)", "Highest placement score of the group. Empty when no candidate was placed."),
    ("placement_groups", "fill_ratio", "decimal (4 d.p.)", "Derived: placed / quota, rounded to four decimals; empty when quota = 0; not capped at 1."),
    ("placement_groups", "group_vacancy", "integer", "Derived: max(quota - placed, 0), computed for each group separately. Its sum is larger than the net vacancy published by ÖSYM; see Usage Notes."),
    ("placement_groups", "quota_filled", "0/1", "Derived: 1 if placed >= quota; empty when quota = 0."),
    ("placement_groups", "score_range", "decimal (5 d.p.)", "Derived: max_score - min_score."),
    ("placement_groups", "initial_min_score_same_year", "decimal (5 d.p.)", "Derived, supplementary rows only: min_score of the same program panel, quota type and sex in the initial placement of the same year."),
    ("placement_groups", "suppl_minus_initial_min_score", "decimal (5 d.p.)", "Derived: min_score - initial_min_score_same_year. Negative values mean the lowest score fell in the supplementary placement."),
    ("placement_groups", "prev_year_min_score", "decimal (5 d.p.)", "Derived: min_score of the same program panel, round, quota type and sex in year - 1. Empty if that year is absent (panels that skip a year are not bridged)."),
    ("placement_groups", "min_score_change", "decimal (5 d.p.)", "Derived: min_score - prev_year_min_score."),
    ("placement_groups", "code_changed", "0/1", "Derived: 1 if the program panel contains more than one ÖSYM program code across years."),
    ("placement_groups", "boundary_score_flag", "0/1", "Derived: 1 if min_score or max_score equals exactly 100 or 500 (the bounds of the score scale). Flag only; values are kept as published."),
    ("placement_groups", "program_counter", "0/1", "Derived: 1 on the first row of each program code within a year and round. Sum this column to count programs; row counts count quota groups."),
    ("programs", "program_panel_id", "string", "See placement_groups."),
    ("programs", "program_group_id", "string", "See placement_groups."),
    ("programs", "university ... language_of_instruction", "", "As in placement_groups, taken from the first year in which the panel appears."),
    ("programs", "osym_code_<year>", "string", "ÖSYM program code of the panel in the initial placement table of that year; empty if the panel is absent that year."),
    ("programs", "years_present", "string", "Semicolon-separated years in which the panel appears in the initial placement table."),
    ("programs", "n_years", "integer", "Number of years in years_present."),
    ("programs", "code_changed", "0/1", "1 if the panel carries more than one ÖSYM code."),
    ("universities", "university ... geographic_region", "", "As in placement_groups."),
    ("universities", "n_programs_initial_<year>", "integer", "Number of program codes of the university in the initial placement table of that year."),
    ("official_totals", "year, placement_round, university_type", "", "Keys; university_type follows the ÖSYM summary tables."),
    ("official_totals", "<measure>_osym", "integer", "Value transcribed from the ÖSYM 'numerical information' summary document (programs, quota, placed, net_vacancy)."),
    ("official_totals", "<measure>_dataset", "integer", "Same measure computed from ozyes_placement_groups.csv (programs = sum of program_counter; net_vacancy = sum(quota) - sum(placed))."),
    ("official_totals", "<measure>_difference", "integer", "dataset - osym. All values are 0 in this release."),
    ("official_totals", "candidates_with_preferences_osym", "integer", "Number of candidates who submitted preferences, as reported by ÖSYM for the round (not split by university type; repeated on both rows)."),
    ("quota_transfer", "year ... sex", "", "Keys and program descriptors; one row per program code, round and sex present in placement_groups."),
    ("quota_transfer", "transfer_source_quota_type", "categorical", "Quota whose vacant places are transferred to the general quota of the same program and sex under the ÖSYM guides: national_athlete in the initial placement, disability in the supplementary placement."),
    ("quota_transfer", "general_quota, general_placed", "integer", "quota and placed of the general group (0 if the group is absent)."),
    ("quota_transfer", "source_quota, source_placed", "integer", "quota and placed of the transfer source group."),
    ("quota_transfer", "other_quota, other_placed", "integer", "quota and placed of the group that is not transferred in that round (disability in the initial placement; always 0 in the supplementary placement)."),
    ("quota_transfer", "general_excess", "integer", "max(general_placed - general_quota, 0)."),
    ("quota_transfer", "source_vacancy", "integer", "max(source_quota - source_placed, 0)."),
    ("quota_transfer", "source_excess, other_excess", "integer", "Excess in the source and other groups; 0 in all rows of this release."),
    ("quota_transfer", "excess_within_source_vacancy", "0/1", "1 if general_excess <= source_vacancy (consistent with the transfer rule)."),
    ("quota_transfer", "excess_equals_source_vacancy", "0/1", "1 if general_excess > 0 and equals source_vacancy."),
    ("quota_transfer", "post_transfer_vacancy", "integer", "max(general_quota + source_quota - general_placed - source_placed, 0) + max(other_quota - other_placed, 0)."),
]
with open(OUT / "codebook.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["file", "variable", "type", "description"])
    for fi, v, ty, de in CB:
        w.writerow([f"ozyes_{fi}.csv", v, ty, de])

# ------------------------------------------------------------------ 7. source list
import json  # noqa: E402

audit = ROOT / "research_validation" / "official_source_audit.json"
if audit.exists():
    src_rows = []
    for f in json.loads(audit.read_text(encoding="utf-8"))["files"]:
        name = Path(f["local_file"].replace("\\", "/"))
        y, r = name.stem.split("_")
        src_rows.append({
            "document": "numerical_summary" if name.parent.name == "src_sayisal" else "placement_table",
            "year": int(y), "placement_round": "initial" if r == "ilk" else "supplementary",
            "url": f["url"], "sha256": f["local_sha256"],
            "remote_copy_identical_2026_10_11": int(bool(f["identical"])),
        })
    pd.DataFrame(src_rows).sort_values(["document", "year", "placement_round"]).to_csv(
        OUT / "sources.csv", index=False, encoding="utf-8", lineterminator="\n")
else:
    print("warning: research_validation/official_source_audit.json not found; sources.csv not written")

# ------------------------------------------------------------------ 8. checksums
files = sorted(f for f in OUT.iterdir() if f.suffix == ".csv")
with open(OUT / "SHA256SUMS.txt", "w", encoding="utf-8", newline="\n") as f:
    for fp in files:
        f.write(f"{hashlib.sha256(fp.read_bytes()).hexdigest()}  {fp.name}\n")

print(f"placement_groups {g.shape}, programs {p.shape}, universities {u.shape}, "
      f"official_totals {ot.shape}, quota_transfer {t.shape}")
