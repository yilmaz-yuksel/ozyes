"""ÖZYES araştırma veri seti üretici.

Girdi : ../data.json  (parse.py çıktısı; ÖSYM PDF'lerinden okunmuş program satırları)
Çıktı : out/ozyes_veriseti.xlsx  (Veri, Özet, Program_Panel, Üniversiteler, Değişken sözlüğü, Kaynak ve yöntem)
        out/ozyes_veriseti.csv   (UTF-8, virgül ayraçlı, ondalık nokta; metin etiketli)
        out/ozyes_veriseti.sav   (SPSS; sayısal kodlu, değişken ve değer etiketli)

Çalıştırma: python build_dataset.py
"""
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
import pyreadstat
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from lookups import UNI_IL, region_of, IL_IBBS1, IL_COGRAFI
from osym_ozet import OSYM, TERCIH, KAYNAK

HERE = Path(__file__).parent
OUT = HERE / "out"
DATA = json.loads((HERE.parent / "data.json").read_text(encoding="utf-8"))
YEARS = sorted(int(y) for y in DATA)

# ---------------------------------------------------------------- kod tabloları
YERLESTIRME = {1: "İlk yerleştirme", 2: "Ek yerleştirme"}
UNI_TURU = {1: "Devlet", 2: "Vakıf"}
BIRIM_TURU = {1: "Fakülte", 2: "Yüksekokul"}
PROGRAM_TURU = {
    1: "Antrenörlük Eğitimi",
    2: "Beden Eğitimi ve Spor Öğretmenliği",
    3: "Spor Yöneticiliği",
    4: "Rekreasyon",
    5: "Egzersiz ve Spor Bilimleri",
    6: "Engellilerde Egzersiz ve Spor Bilimleri",
    7: "Engellilerde Beden Eğitimi ve Spor Öğretmenliği",
}
UCRET = {0: "Ücret ayrımı yok", 1: "Burslu", 2: "%50 İndirimli", 3: "%25 İndirimli", 4: "Ücretli"}
DIL = {1: "Türkçe", 2: "İngilizce"}
KONT_TURU = {1: "Genel", 2: "Milli sporcu", 3: "Engelli aday"}
CINSIYET = {1: "Erkek", 2: "Kadın"}
EVET_HAYIR = {0: "Hayır", 1: "Evet"}
GROUPS = {"ge": (1, 1), "gk": (1, 2), "me": (2, 1), "mk": (2, 2), "ee": (3, 1), "ek": (3, 2)}

inv = lambda d: {v: k for k, v in d.items()}
PT_CODE, UCRET_CODE, DIL_CODE = inv(PROGRAM_TURU), inv(UCRET), inv(DIL)
UCRET_CODE[""] = 0

# ---------------------------------------------------------------- program satırları
progs = {}          # (yil, kod) -> program kaydı
by_year = defaultdict(dict)
for y in YEARS:
    for r in DATA[str(y)]:
        r = dict(r)
        r["yil"] = y
        r["k2"] = (r["uni"], r["ptur"], r["dil"], r["burs"])
        progs[(y, r["kod"])] = r
        by_year[y][r["kod"]] = r

missing_il = sorted({r["uni"] for r in progs.values()} - set(UNI_IL))
if missing_il:
    raise SystemExit(f"UNI_IL tablosunda olmayan üniversite: {missing_il}")
assert len(IL_IBBS1) == 81 and len(IL_COGRAFI) == 81, "il-bölge tabloları 81 il içermeli"

# ---------------------------------------------------------------- program izleme kimliği
# 1. geçiş: aynı ÖSYM kodu en yakın önceki yılda varsa bağla (ara yıl atlanabilir).
# 2. geçiş: bağlanamayanlar için bir önceki yılda aynı üniversite + program türü + dil + ücret
#    durumu tek bir programa karşılık geliyorsa ve o programın kodu bu yıl kullanılmıyorsa bağla.
link = {}            # (yil, kod) -> (önceki yil, önceki kod)
used = set()
for y in YEARS:
    earlier = [p for p in YEARS if p < y][::-1]
    for kod, r in by_year[y].items():
        for p in earlier:
            if kod in by_year[p] and (p, kod) not in used:
                link[(y, kod)] = (p, kod)
                used.add((p, kod))
                break
    if earlier:
        p = earlier[0]
        idx_p, idx_y = defaultdict(list), defaultdict(list)
        for k, r in by_year[p].items():
            idx_p[r["k2"]].append(k)
        for k, r in by_year[y].items():
            idx_y[r["k2"]].append(k)
        for kod, r in by_year[y].items():
            if (y, kod) in link:
                continue
            c = idx_p.get(r["k2"], [])
            if len(c) == 1 and len(idx_y[r["k2"]]) == 1 and c[0] not in by_year[y] and (p, c[0]) not in used:
                link[(y, kod)] = (p, c[0])
                used.add((p, c[0]))

chain = {}
for y in YEARS:
    for kod in by_year[y]:
        key = (y, kod)
        chain[key] = chain[link[key]] if key in link else key   # zincirin ilk halkası
panels = defaultdict(list)
for key, root in chain.items():
    panels[root].append(key)


def sort_key(root):
    first = progs[root]
    return (first["uni"], PT_CODE[first["ptur"]], DIL_CODE[first["dil"]], UCRET_CODE[first["burs"]], root[0], root[1])


panel_id = {}
for i, root in enumerate(sorted(panels, key=sort_key), 1):
    for key in panels[root]:
        panel_id[key] = f"OZY{i:04d}"
kod_degisti_panel = {panel_id[keys[0]]: int(len({k for _, k in keys}) > 1) for keys in panels.values()}

grp_keys = sorted({(r["uni"], PT_CODE[r["ptur"]], DIL_CODE[r["dil"]]) for r in progs.values()})
grup_id = {g: f"G{i:03d}" for i, g in enumerate(grp_keys, 1)}

# ---------------------------------------------------------------- uzun format
rows = []
for (y, kod), r in progs.items():
    il = UNI_IL[r["uni"]]
    ibbs, bolge = region_of(il)
    base = {
        "yil": y,
        "panel_id": panel_id[(y, kod)],
        "program_grup_id": grup_id[(r["uni"], PT_CODE[r["ptur"]], DIL_CODE[r["dil"]])],
        "program_kodu": kod,
        "universite": r["uni"],
        "uni_turu": 1 if r["tur"] == "DEVLET" else 2,
        "il": il,
        "ibbs1": ibbs,
        "cografi_bolge": bolge,
        "birim": r["fak"],
        "birim_turu": 2 if "Yüksekokul" in r["fak"] else 1,
        "program_adi": r["prog"],
        "program_turu": PT_CODE[r["ptur"]],
        "ucret_durumu": UCRET_CODE[r["burs"]],
        "ogretim_dili": DIL_CODE[r["dil"]],
    }
    sources = [(1, {g: r[g] for g in GROUPS})]
    if r.get("x"):
        sources.append((2, r["x"]))
    for yer, groups in sources:
        for g, v in groups.items():
            k, n, mn, mx = v
            if not ((k or 0) > 0 or (n or 0) > 0):
                continue   # bu grupta kontenjan da yerleşen de yok: satır üretilmez
            kt, cs = GROUPS[g]
            rows.append({**base, "yerlestirme": yer, "kontenjan_turu": kt, "cinsiyet": cs,
                         "kontenjan": k, "yerlesen": n if n is not None else 0,
                         "en_kucuk_puan": mn, "en_buyuk_puan": mx})

df = pd.DataFrame(rows)
df["doluluk_orani"] = df.apply(lambda s: round(s.yerlesen / s.kontenjan, 4) if s.kontenjan and s.kontenjan > 0 else None, axis=1)
df["bos_kontenjan"] = df.apply(lambda s: max(s.kontenjan - s.yerlesen, 0) if pd.notna(s.kontenjan) else None, axis=1)
df["kontenjan_doldu"] = df.apply(lambda s: int(s.yerlesen >= s.kontenjan) if s.kontenjan and s.kontenjan > 0 else None, axis=1)
df["puan_araligi"] = (df.en_buyuk_puan - df.en_kucuk_puan).round(5)

key_cols = ["panel_id", "yerlestirme", "kontenjan_turu", "cinsiyet", "yil"]
mins = df.set_index(key_cols)["en_kucuk_puan"].to_dict()
df["ilk_en_kucuk_puan"] = df.apply(lambda s: mins.get((s.panel_id, 1, s.kontenjan_turu, s.cinsiyet, s.yil)) if s.yerlestirme == 2 else None, axis=1)
df["ek_ilk_farki"] = (df.en_kucuk_puan - df.ilk_en_kucuk_puan).round(5)
df["onceki_yil_en_kucuk_puan"] = df.apply(lambda s: mins.get((s.panel_id, s.yerlestirme, s.kontenjan_turu, s.cinsiyet, s.yil - 1)), axis=1)
df["en_kucuk_puan_degisim"] = (df.en_kucuk_puan - df.onceki_yil_en_kucuk_puan).round(5)
df["kod_degisti"] = df.panel_id.map(kod_degisti_panel)
df["uc_puan"] = df.apply(lambda s: int(any(v in (100.0, 500.0) for v in (s.en_kucuk_puan, s.en_buyuk_puan) if pd.notna(v))), axis=1)

COLS = ["yil", "yerlestirme", "panel_id", "program_grup_id", "program_kodu", "universite", "uni_turu", "il",
        "ibbs1", "cografi_bolge", "birim", "birim_turu", "program_adi", "program_turu", "ucret_durumu",
        "ogretim_dili", "kontenjan_turu", "cinsiyet", "kontenjan", "yerlesen", "en_kucuk_puan", "en_buyuk_puan",
        "doluluk_orani", "bos_kontenjan", "kontenjan_doldu", "puan_araligi", "ilk_en_kucuk_puan", "ek_ilk_farki",
        "onceki_yil_en_kucuk_puan", "en_kucuk_puan_degisim", "kod_degisti", "uc_puan"]
df = df[COLS].sort_values(["yil", "yerlestirme", "universite", "program_turu", "ogretim_dili", "ucret_durumu",
                           "program_kodu", "kontenjan_turu", "cinsiyet"]).reset_index(drop=True)
df["program_sayac"] = (~df.duplicated(["yil", "yerlestirme", "program_kodu"])).astype(int)
COLS.append("program_sayac")
for c in ["kontenjan", "yerlesen", "bos_kontenjan", "kontenjan_doldu"]:
    df[c] = df[c].astype("Int64")

VALUE_LABELS = {
    "yerlestirme": YERLESTIRME, "uni_turu": UNI_TURU, "birim_turu": BIRIM_TURU, "program_turu": PROGRAM_TURU,
    "ucret_durumu": UCRET, "ogretim_dili": DIL, "kontenjan_turu": KONT_TURU, "cinsiyet": CINSIYET,
    "kontenjan_doldu": EVET_HAYIR, "kod_degisti": EVET_HAYIR, "uc_puan": EVET_HAYIR,
}
labeled = df.copy()
for c, m in VALUE_LABELS.items():
    labeled[c] = labeled[c].map(lambda v: m.get(int(v)) if pd.notna(v) else None)

# ---------------------------------------------------------------- değişken sözlüğü
fmt_vals = lambda m: "; ".join(f"{k} = {v}" for k, v in m.items())
DICT = [
    ("yil", "Yerleştirme yılı", "Sayı", "", "ÖSYM tablosunun yılı."),
    ("yerlestirme", "Yerleştirme türü", "Kategorik", fmt_vals(YERLESTIRME), "İlk yerleştirme veya aynı yılın ek yerleştirmesi."),
    ("panel_id", "Program izleme kimliği", "Metin", "OZY0001 ...", "Aynı programı yıllar boyunca izleyen sabit kimlik. ÖSYM kodu değişse de aynı kalır (bkz. Kaynak ve yöntem). Boylamsal analizlerde birim tanımlayıcısı olarak kullanın."),
    ("program_grup_id", "Program grubu kimliği", "Metin", "G001 ...", "Aynı üniversite + program türü + öğretim dili. Burslu, indirimli ve ücretli seçenekleri tek programda birleştirmek için kullanın."),
    ("program_kodu", "ÖSYM program kodu", "Metin", "", "O yılın tablosundaki 9 haneli kod. Metin olarak saklanır."),
    ("universite", "Üniversite adı", "Metin", "", "Tablodaki ad; parantez içindeki il ve 'Devlet/Vakıf Üniversitesi' ekleri ile dipnot işaretleri temizlenmiştir."),
    ("uni_turu", "Üniversite türü", "Kategorik", fmt_vals(UNI_TURU), "ÖSYM tablosundaki tür. Kırgızistan-Türkiye Manas Üniversitesi tabloda VAKIF olarak geçtiği için Vakıf kodlanmıştır."),
    ("il", "İl", "Metin", "", "Üniversitenin merkezinin bulunduğu il (araştırmacı tarafından eklendi). Program farklı bir ilçedeki kampüste olabilir."),
    ("ibbs1", "İBBS Düzey 1 bölgesi", "Metin", "TR1 ... TRC; Yurt dışı", "TÜİK İstatistiki Bölge Birimleri Sınıflaması, 12 bölge (il bilgisinden türetildi)."),
    ("cografi_bolge", "Coğrafi bölge", "Metin", "7 bölge; Yurt dışı", "İl bilgisinden türetildi. Bolu ve Düzce Karadeniz, Eskişehir İç Anadolu bölgesine alınmıştır."),
    ("birim", "Fakülte / yüksekokul adı", "Metin", "", "2026 tablosunda büyük harfle yazılan adlar önceki yılın yazımıyla ya da Türkçe başlık biçimine çevrilerek düzeltilmiştir."),
    ("birim_turu", "Birim türü", "Kategorik", fmt_vals(BIRIM_TURU), "Birim adında 'Yüksekokul' geçiyorsa Yüksekokul, aksi halde Fakülte."),
    ("program_adi", "Program adı (tablodaki haliyle)", "Metin", "", "Ücret durumu ve öğretim dili ekleriyle birlikte."),
    ("program_turu", "Program türü", "Kategorik", fmt_vals(PROGRAM_TURU), "Program adından ücret ve dil ekleri çıkarılarak elde edildi."),
    ("ucret_durumu", "Ücret / burs durumu", "Kategorik", fmt_vals(UCRET), "Program adındaki parantez ekinden. Devlet üniversitelerinde ve ek taşımayan programlarda 0."),
    ("ogretim_dili", "Öğretim dili", "Kategorik", fmt_vals(DIL), "Program adında '(İngilizce)' geçiyorsa İngilizce."),
    ("kontenjan_turu", "Kontenjan türü", "Kategorik", fmt_vals(KONT_TURU), "Ek yerleştirme tablolarında milli sporcu kontenjanı yoktur."),
    ("cinsiyet", "Cinsiyet", "Kategorik", fmt_vals(CINSIYET), "Kontenjanın ayrıldığı cinsiyet."),
    ("kontenjan", "Kontenjan", "Sayı", "", "ÖSYM tablosundaki kontenjan. Ek yerleştirmede ek kontenjan."),
    ("yerlesen", "Yerleşen sayısı", "Sayı", "", "ÖSYM tablosundaki yerleşen. Kontenjandan büyük olabilir; ek yerleştirmede kontenjan 0 iken yerleşen olabilir."),
    ("en_kucuk_puan", "En küçük yerleştirme puanı", "Sayı (5 ondalık)", "", "Yerleşen yoksa boş."),
    ("en_buyuk_puan", "En büyük yerleştirme puanı", "Sayı (5 ondalık)", "", "Yerleşen yoksa boş."),
    ("doluluk_orani", "Doluluk oranı", "Oran", "0-1 (1'i aşabilir)", "yerlesen / kontenjan. Kontenjan 0 ise boş. Türetilmiş."),
    ("bos_kontenjan", "Boş kalan kontenjan (grup düzeyi)", "Sayı", "", "max(kontenjan − yerlesen, 0), her kontenjan grubu için ayrı. Türetilmiş. DİKKAT: ÖSYM'nin sayısal bilgiler tablosundaki 'boş kontenjan' net farktır: toplam kontenjan − toplam yerleşen. Bazı gruplarda yerleşen kontenjanı aştığı için bu sütunun toplamı ÖSYM rakamından büyüktür. ÖSYM rakamını elde etmek için SUM(kontenjan) − SUM(yerlesen) kullanın."),
    ("kontenjan_doldu", "Kontenjan doldu mu", "Kategorik", fmt_vals(EVET_HAYIR), "yerlesen ≥ kontenjan ise 1. Kontenjan 0 ise boş. Türetilmiş."),
    ("puan_araligi", "Puan aralığı", "Sayı", "", "en_buyuk_puan − en_kucuk_puan. Türetilmiş."),
    ("ilk_en_kucuk_puan", "Aynı yılın ilk yerleştirme en küçük puanı", "Sayı", "", "Yalnızca ek yerleştirme satırlarında dolu: aynı program, aynı kontenjan türü ve cinsiyet. Türetilmiş."),
    ("ek_ilk_farki", "Ek − ilk en küçük puan farkı", "Sayı", "", "en_kucuk_puan − ilk_en_kucuk_puan. Negatif değer ek yerleştirmede taban puanın düştüğünü gösterir. Türetilmiş."),
    ("onceki_yil_en_kucuk_puan", "Bir önceki yılın en küçük puanı", "Sayı", "", "Aynı panel_id, yerleştirme türü, kontenjan türü ve cinsiyet için yil − 1. Önceki yıl yoksa boş. Türetilmiş."),
    ("en_kucuk_puan_degisim", "En küçük puanın yıllık değişimi", "Sayı", "", "en_kucuk_puan − onceki_yil_en_kucuk_puan. Türetilmiş."),
    ("kod_degisti", "Program kodu yıllar arasında değişti", "Kategorik", fmt_vals(EVET_HAYIR), "Aynı panel_id altında birden fazla ÖSYM kodu varsa 1."),
    ("program_sayac", "Program sayacı", "Sayı (0/1)", "1 = programın o yıl ve yerleştirmedeki ilk satırı", "Program saymak için bu sütunu toplayın (pivot tabloda 'Toplam'). Satır sayısı programı değil grubu sayar. Türetilmiş."),
    ("uc_puan", "Uç puan işareti", "Kategorik", fmt_vals(EVET_HAYIR), "En küçük veya en büyük puan tam 100,00000 ya da 500,00000 ise 1. Çoğunlukla engelli aday kontenjanlarında görülür; analizlerde ayrıca ele alınması önerilir."),
]
DICT.sort(key=lambda d: COLS.index(d[0]))
assert [d[0] for d in DICT] == COLS

# ---------------------------------------------------------------- SPSS ve CSV
OUT.mkdir(exist_ok=True)
coded = df.copy()
for c in ["kontenjan", "yerlesen", "bos_kontenjan", "kontenjan_doldu"]:
    coded[c] = coded[c].astype("float")
pyreadstat.write_sav(
    coded, OUT / "ozyes_veriseti.sav",
    column_labels={d[0]: d[1] for d in DICT},
    variable_value_labels={c: {float(k): v for k, v in m.items()} for c, m in VALUE_LABELS.items()},
    variable_measure={**{c: "nominal" for c in VALUE_LABELS}, **{c: "scale" for c in
                      ["yil", "kontenjan", "yerlesen", "en_kucuk_puan", "en_buyuk_puan", "doluluk_orani", "bos_kontenjan",
                       "puan_araligi", "ilk_en_kucuk_puan", "ek_ilk_farki", "onceki_yil_en_kucuk_puan", "en_kucuk_puan_degisim", "program_sayac"]},
                      **{c: "nominal" for c in ["panel_id", "program_grup_id", "program_kodu", "universite", "il", "ibbs1",
                                                "cografi_bolge", "birim", "program_adi"]}},
    file_label="ÖZYES araştırma veri seti",
)
labeled.to_csv(OUT / "ozyes_veriseti.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- Excel
FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3A68")
HEAD_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
BODY = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
TITLE = Font(name=FONT, size=14, bold=True, color="1F3A68")
NOTE = Font(name=FONT, size=9, italic=True, color="555555")
THIN = Border(bottom=Side(style="thin", color="C9D1DE"))
WRAP = Alignment(wrap_text=True, vertical="top")

wb = Workbook()
wb.remove(wb.active)


def header(ws, row, names):
    for j, n in enumerate(names, 1):
        c = ws.cell(row=row, column=j, value=n)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
        c.alignment = Alignment(vertical="center", wrap_text=True)


def widths(ws, w):
    for j, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(j)].width = x


def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA:
        return None
    return v


# Oku beni
ws = wb.create_sheet("Oku beni")
lines = [
    ("ÖZYES araştırma veri seti", TITLE),
    ("YKS Spor Bilimleri İçin Özel Yetenek Sınavı ile öğrenci alan programların ÖSYM yerleştirme sonuçları, uzun format.", BODY),
    ("", BODY),
    ("Hazırlayan: Dr. Öğr. Üyesi Yılmaz YÜKSEL, Karabük Üniversitesi Hasan Doğan Spor Bilimleri Fakültesi (yyuksel@karabuk.edu.tr)", BODY),
    (f"Oluşturulma tarihi: {date.today().strftime('%d.%m.%Y')}", BODY),
    ("Kapsam: 2024, 2025 ve 2026 ilk yerleştirme; 2024 ve 2025 ek yerleştirme.", BODY),
    ("", BODY),
    ("Sayfalar", BOLD),
    ("Veri: Her satır bir yıl × yerleştirme × program × kontenjan türü × cinsiyet birleşimidir. Analizlerin temel tablosu.", BODY),
    ("Özet: Yıl, yerleştirme, kontenjan türü ve cinsiyete göre toplamlar. Veri sayfasından formülle hesaplanır.", BODY),
    ("Program_Panel: Her program için bir satır; yıllara göre ÖSYM kodları ve hangi yıllarda tabloda yer aldığı.", BODY),
    ("Üniversiteler: Üniversite, tür, il ve bölge bilgileri; yıllara göre program sayıları.", BODY),
    ("Değişken sözlüğü: Tüm değişkenlerin tanımı, kodları ve türetilme kuralları.", BODY),
    ("ÖSYM karşılaştırma: Veri setinin toplamları ile ÖSYM'nin sayısal bilgiler tablolarının karşılaştırması; tercih yapan aday sayıları.", BODY),
    ("Kaynak ve yöntem: Kaynak dosyalar, işleme adımları, doğrulama sonuçları ve sınırlılıklar.", BODY),
    ("", BODY),
    ("Kullanım notları", BOLD),
    ("Boylamsal analizlerde program birimi olarak panel_id kullanın; ÖSYM kodu yıllar arasında değişebilir.", BODY),
    ("Burslu/ücretli seçenekleri tek program saymak için program_grup_id kullanın.", BODY),
    ("Program sayısı için program_sayac sütununu toplayın; satır sayısı programı değil kontenjan grubunu sayar.", BODY),
    ("ÖSYM'nin 'boş kontenjan' rakamı net farktır (toplam kontenjan − toplam yerleşen); bos_kontenjan sütununun toplamı bundan büyüktür.", BODY),
    ("SPSS için ozyes_veriseti.sav dosyası sayısal kodlu ve etiketlidir; R/Python için ozyes_veriseti.csv kullanılabilir.", BODY),
    ("", BODY),
    ("Lisans: Veri CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Kaynak: ÖSYM yerleştirme tabloları. İngilizce açık sürüm ve atıf bilgisi için depodaki release/README.md dosyasına bakın.", Font(name=FONT, size=10, bold=True, color="1F4E79")),
]
for i, (t, f) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=t)
    c.font = f
widths(ws, [130])

# Veri
ws = wb.create_sheet("Veri")
header(ws, 1, COLS)
num_fmt = {"en_kucuk_puan": "0.00000", "en_buyuk_puan": "0.00000", "puan_araligi": "0.00000",
           "ilk_en_kucuk_puan": "0.00000", "ek_ilk_farki": "0.00000", "onceki_yil_en_kucuk_puan": "0.00000",
           "en_kucuk_puan_degisim": "0.00000", "doluluk_orani": "0.0%", "yil": "0"}
for i, rec in enumerate(labeled.itertuples(index=False), 2):
    for j, v in enumerate(rec, 1):
        c = ws.cell(row=i, column=j, value=clean(v))
        c.font = BODY
        f = num_fmt.get(COLS[j - 1])
        if f:
            c.number_format = f
ws.freeze_panes = "C2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{len(labeled) + 1}"
widths(ws, [7, 16, 10, 10, 12, 40, 9, 14, 22, 18, 36, 11, 50, 34, 16, 10, 13, 9, 10, 9, 13, 13, 10, 10, 10, 11, 13, 11, 13, 13, 10, 8, 10])
N = len(labeled) + 1
COL = {c: get_column_letter(i) for i, c in enumerate(COLS, 1)}

# Özet (formüllü)
ws = wb.create_sheet("Özet", 1)
ws["A1"] = "Özet: yıl, yerleştirme, kontenjan türü ve cinsiyete göre"
ws["A1"].font = TITLE
ws["A2"] = ("Tüm değerler Veri sayfasından formülle hesaplanır (COUNTIFS, SUMIFS, AVERAGEIFS). "
            "Ortalama en küçük puan, yerleşeni olan programların ortalamasıdır.")
ws["A2"].font = NOTE
cols = ["Yıl", "Yerleştirme", "Kontenjan türü", "Cinsiyet", "Satır (program) sayısı", "Toplam kontenjan",
        "Toplam yerleşen", "Doluluk", "Kontenjanı dolmayan program", "Ortalama en küçük puan",
        "En düşük en küçük puan", "En yüksek en küçük puan"]
header(ws, 4, cols)


def rng(c):
    return f"Veri!${COL[c]}$2:${COL[c]}${N}"


combos = (labeled[["yil", "yerlestirme", "kontenjan_turu", "cinsiyet"]].drop_duplicates()
          .assign(_y=lambda d: d.yil, _p=lambda d: d.yerlestirme.map(inv(YERLESTIRME)),
                  _k=lambda d: d.kontenjan_turu.map(inv(KONT_TURU)), _c=lambda d: d.cinsiyet.map(inv(CINSIYET)))
          .sort_values(["_y", "_p", "_k", "_c"]))
r0 = 5
for i, rec in enumerate(combos.itertuples(index=False)):
    r = r0 + i
    vals = [rec.yil, rec.yerlestirme, rec.kontenjan_turu, rec.cinsiyet]
    for j, v in enumerate(vals, 1):
        ws.cell(row=r, column=j, value=v).font = BODY
    crit = (f"{rng('yil')},$A{r},{rng('yerlestirme')},$B{r},{rng('kontenjan_turu')},$C{r},{rng('cinsiyet')},$D{r}")
    f = {
        5: f"=COUNTIFS({crit})",
        6: f"=SUMIFS({rng('kontenjan')},{crit})",
        7: f"=SUMIFS({rng('yerlesen')},{crit})",
        8: f"=IFERROR(G{r}/F{r},\"\")",
        9: f"=COUNTIFS({crit},{rng('kontenjan_doldu')},\"Hayır\")",
        10: f"=IFERROR(AVERAGEIFS({rng('en_kucuk_puan')},{crit}),\"\")",
        11: f"=IFERROR(_xlfn.MINIFS({rng('en_kucuk_puan')},{crit}),\"\")",
        12: f"=IFERROR(_xlfn.MAXIFS({rng('en_kucuk_puan')},{crit}),\"\")",
    }
    for j, formula in f.items():
        c = ws.cell(row=r, column=j, value=formula)
        c.font = BODY
        c.number_format = {8: "0.0%", 10: "0.000", 11: "0.000", 12: "0.000"}.get(j, "#,##0")
    ws.cell(row=r, column=1).number_format = "0"
last = r0 + len(combos) - 1
tr = last + 1
ws.cell(row=tr, column=1, value="Toplam").font = BOLD
for j, col in ((5, "E"), (6, "F"), (7, "G"), (9, "I")):
    c = ws.cell(row=tr, column=j, value=f"=SUM({col}{r0}:{col}{last})")
    c.font, c.number_format = BOLD, "#,##0"
ws.cell(row=tr + 2, column=1, value=("Not: 'Toplam' satırı kontrol amaçlıdır; satır sayısı toplamı Veri sayfasındaki satır sayısına "
                                      "eşit olmalıdır.")).font = NOTE
ws.cell(row=tr + 3, column=1, value="Veri sayfasındaki satır sayısı:").font = NOTE
ws.cell(row=tr + 3, column=5, value=f"=COUNTA(Veri!$A$2:$A${N})").font = NOTE
ws.freeze_panes = "E5"
widths(ws, [8, 16, 15, 10, 13, 12, 12, 10, 14, 14, 14, 14])

# Program_Panel
ws = wb.create_sheet("Program_Panel")
pcols = ["panel_id", "program_grup_id", "universite", "uni_turu", "il", "birim", "program_adi", "program_turu",
         "ucret_durumu", "ogretim_dili"] + [f"kod_{y}" for y in YEARS] + ["bulundugu_yillar", "yil_sayisi", "kod_degisti"]
header(ws, 1, pcols)
prow = []
for root, keys in panels.items():
    keys = sorted(keys)
    last_r = progs[keys[-1]]
    codes = {y: k for y, k in keys}
    pid = panel_id[keys[0]]
    prow.append([pid, grup_id[(last_r["uni"], PT_CODE[last_r["ptur"]], DIL_CODE[last_r["dil"]])], last_r["uni"],
                 UNI_TURU[1 if last_r["tur"] == "DEVLET" else 2], UNI_IL[last_r["uni"]], last_r["fak"], last_r["prog"],
                 last_r["ptur"], UCRET[UCRET_CODE[last_r["burs"]]], last_r["dil"]]
                + [codes.get(y) for y in YEARS] + [", ".join(str(y) for y in sorted(codes)), len(codes),
                                                    EVET_HAYIR[kod_degisti_panel[pid]]])
prow.sort(key=lambda x: x[0])
for i, rec in enumerate(prow, 2):
    for j, v in enumerate(rec, 1):
        ws.cell(row=i, column=j, value=v).font = BODY
ws.freeze_panes = "B2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(pcols))}{len(prow) + 1}"
widths(ws, [10, 10, 40, 9, 14, 36, 50, 34, 16, 10] + [12] * len(YEARS) + [18, 9, 10])
PN = len(prow) + 1

# Üniversiteler (program sayıları formülle)
ws = wb.create_sheet("Üniversiteler")
ucols = ["universite", "uni_turu", "il", "ibbs1", "cografi_bolge"] + [f"program_sayisi_{y}" for y in YEARS]
header(ws, 1, ucols)
unis = sorted({(r["uni"], r["tur"]) for r in progs.values()})
kod_col = {y: get_column_letter(pcols.index(f"kod_{y}") + 1) for y in YEARS}
for i, (u, t) in enumerate(unis, 2):
    il = UNI_IL[u]
    ib, bo = region_of(il)
    for j, v in enumerate([u, UNI_TURU[1 if t == "DEVLET" else 2], il, ib, bo], 1):
        ws.cell(row=i, column=j, value=v).font = BODY
    for k, y in enumerate(YEARS):
        c = ws.cell(row=i, column=6 + k,
                    value=f'=COUNTIFS(Program_Panel!$C$2:$C${PN},$A{i},Program_Panel!${kod_col[y]}$2:${kod_col[y]}${PN},"<>")')
        c.font = BODY
ws.freeze_panes = "B2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(ucols))}{len(unis) + 1}"
widths(ws, [42, 9, 20, 24, 18] + [16] * len(YEARS))

# Değişken sözlüğü
ws = wb.create_sheet("Değişken sözlüğü")
header(ws, 1, ["Değişken", "Etiket", "Tür", "Değerler", "Açıklama / türetme kuralı"])
for i, d in enumerate(DICT, 2):
    for j, v in enumerate(d, 1):
        c = ws.cell(row=i, column=j, value=v)
        c.font = BOLD if j == 1 else BODY
        c.alignment = WRAP
        c.border = THIN
ws.freeze_panes = "B2"
widths(ws, [26, 36, 14, 40, 80])

# ÖSYM karşılaştırma
ws = wb.create_sheet("ÖSYM karşılaştırma")
ws["A1"] = "ÖSYM sayısal bilgiler tabloları ile karşılaştırma"
ws["A1"].font = TITLE
ws["A2"] = ("Mavi sayılar ÖSYM tablolarından elle aktarılmıştır (kaynaklar altta). Siyah sayılar Veri sayfasından formülle hesaplanır. "
            "Fark sütunlarının tamamı 0 olmalıdır.")
ws["A2"].font = NOTE
ws["A3"] = ("Boş kontenjan: ÖSYM net farkı verir (toplam kontenjan − toplam yerleşen). Veri sayfasındaki bos_kontenjan sütunu grup düzeyinde "
            "hesaplandığı için toplamı daha büyüktür; son sütun bu toplamı ayrıca gösterir.")
ws["A3"].font = NOTE
cols = ["Yıl", "Yerleştirme", "Üniversite türü",
        "Program (ÖSYM)", "Program (veri)", "Fark",
        "Kontenjan (ÖSYM)", "Kontenjan (veri)", "Fark",
        "Yerleşen (ÖSYM)", "Yerleşen (veri)", "Fark",
        "Boş kontenjan (ÖSYM)", "Boş kontenjan, net (veri)", "Fark",
        "Tercih yapan aday (ÖSYM)", "Tercih yapan aday / kontenjan", "bos_kontenjan toplamı (grup düzeyi)"]
header(ws, 5, cols)
BLUE = Font(name=FONT, size=10, color="0000FF")
BLUEB = Font(name=FONT, size=10, color="0000FF", bold=True)
r = 6
for (y, yer) in sorted(TERCIH):
    first = r
    for tur in (1, 2):
        p, k, n, b = OSYM[(y, yer, tur)]
        crit = (f"{rng('yil')},$A{r},{rng('yerlestirme')},$B{r},{rng('uni_turu')},$C{r}")
        vals = {1: y, 2: YERLESTIRME[yer], 3: UNI_TURU[tur], 4: p, 7: k, 10: n, 13: b,
                5: f"=SUMIFS({rng('program_sayac')},{crit})", 6: f"=E{r}-D{r}",
                8: f"=SUMIFS({rng('kontenjan')},{crit})", 9: f"=H{r}-G{r}",
                11: f"=SUMIFS({rng('yerlesen')},{crit})", 12: f"=K{r}-J{r}",
                14: f"=H{r}-K{r}", 15: f"=N{r}-M{r}",
                18: f"=SUMIFS({rng('bos_kontenjan')},{crit})"}
        for j, v in vals.items():
            c = ws.cell(row=r, column=j, value=v)
            c.font = BLUE if j in (4, 7, 10, 13) else BODY
            c.number_format = "0" if j == 1 else "#,##0"
        r += 1
    # toplam satırı
    ws.cell(row=r, column=1, value=y).font = BOLD
    ws.cell(row=r, column=1).number_format = "0"
    ws.cell(row=r, column=2, value=YERLESTIRME[yer]).font = BOLD
    ws.cell(row=r, column=3, value="Toplam").font = BOLD
    for j in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18):
        L = get_column_letter(j)
        c = ws.cell(row=r, column=j, value=f"=SUM({L}{first}:{L}{r - 1})")
        c.font, c.number_format = BOLD, "#,##0"
    c = ws.cell(row=r, column=16, value=TERCIH[(y, yer)])
    c.font, c.number_format = BLUEB, "#,##0"
    c = ws.cell(row=r, column=17, value=f"=IFERROR(P{r}/H{r},\"\")")
    c.font, c.number_format = BOLD, "0.00"
    for j in range(1, 19):
        ws.cell(row=r, column=j).border = THIN
    r += 2
ws.cell(row=r, column=1, value="Tüm farkların mutlak toplamı (0 olmalı):").font = BOLD
c = ws.cell(row=r, column=6, value=f"=SUMPRODUCT(ABS(F6:F{r-2}))+SUMPRODUCT(ABS(I6:I{r-2}))+SUMPRODUCT(ABS(L6:L{r-2}))+SUMPRODUCT(ABS(O6:O{r-2}))")
c.font = BOLD
r += 2
ws.cell(row=r, column=1, value="Kaynaklar (ÖSYM)").font = BOLD
r += 1
for (y, yer), t in sorted(KAYNAK.items()):
    ws.cell(row=r, column=1, value=f"{y} {YERLESTIRME[yer].lower()}: {t} (src_sayisal/{y}_{'ilk' if yer == 1 else 'ek'}.pdf)").font = BODY
    r += 1
ws.cell(row=r + 1, column=1, value=("Not: 'Tercih yapan aday' ÖSYM tablosunda üniversite türüne ayrılmadan tek değer olarak verilmiştir; "
                                    "bu yüzden yalnızca toplam satırında yer alır. Aday / kontenjan oranı bir rekabet göstergesi olarak kullanılabilir.")).font = NOTE
ws.freeze_panes = "D6"
widths(ws, [8, 16, 14] + [11] * 15)

# Kaynak ve yöntem
counts = df.groupby(["yil", "yerlestirme"]).agg(satir=("panel_id", "size"), program=("program_kodu", "nunique")).reset_index()
ws = wb.create_sheet("Kaynak ve yöntem")
ws["A1"] = "Kaynak ve yöntem"
ws["A1"].font = TITLE
header(ws, 3, ["Kaynak dosya", "Yıl", "Yerleştirme", "Tablodaki program", "Veri setindeki satır"])
src_files = {(y, 1): f"src/{y}_ilk.pdf" for y in YEARS}
src_files.update({(y, 2): f"src/{y}_ek.pdf" for y in YEARS})
r = 4
for rec in counts.itertuples(index=False):
    vals = [src_files[(rec.yil, rec.yerlestirme)], rec.yil, YERLESTIRME[rec.yerlestirme], rec.program, rec.satir]
    for j, v in enumerate(vals, 1):
        ws.cell(row=r, column=j, value=v).font = BODY
    r += 1
ws.cell(row=r, column=1, value="Toplam").font = BOLD
ws.cell(row=r, column=5, value=f"=SUM(E4:E{r - 1})").font = BOLD
r += 2
text = [
    ("Kaynak", True),
    ("ÖSYM, 'YKS Spor Bilimleri İçin Özel Yetenek Sınavı İle Öğrenci Alan Yükseköğretim Programları' en küçük ve en büyük puan tabloları (PDF). Ek yerleştirme tabloları aynı başlığın 'Ek Yerleştirme' sürümleridir.", False),
    ("", False),
    ("İşleme adımları", True),
    ("1. PDF tabloları pdfplumber kütüphanesiyle satır satır okundu (parse.py). Sütun grupları tablo başlığındaki kontenjan türü adlarından belirlendi.", False),
    ("2. Üniversite adlarından parantez içindeki il, 'Devlet Üniversitesi' / 'Vakıf Üniversitesi' ekleri ve dipnot işaretleri ayrıldı; program adından ücret durumu ve öğretim dili çıkarıldı.", False),
    ("3. Her program satırı kontenjan türü × cinsiyet gruplarına açılarak uzun formata çevrildi. Kontenjanı da yerleşeni de olmayan gruplar (ör. vakıf burslu programlarda milli sporcu kontenjanı) satır olarak üretilmedi.", False),
    ("4. Program izleme kimliği (panel_id): önce aynı ÖSYM kodu en yakın önceki yılda arandı (ara yıl atlanabilir; ör. 2025'te tabloda olmayan Spor Yöneticiliği programları). Bulunamazsa, bir önceki yılda aynı üniversite + program türü + öğretim dili + ücret durumu tek bir programa karşılık geliyor ve o programın kodu bu yıl kullanılmıyorsa iki kayıt bağlandı.", False),
    ("5. İl, İBBS Düzey 1 ve coğrafi bölge bilgisi araştırmacı tarafından hazırlanan üniversite → il tablosundan eklendi (dataset/lookups.py).", False),
    ("6. Türetilmiş değişkenler (doluluk oranı, boş kontenjan, puan aralığı, ek−ilk farkı, yıllık değişim) build_dataset.py ile hesaplandı.", False),
    ("", False),
    ("Doğrulama", True),
    ("Her PDF için: okunan program sayısı PDF metnindeki benzersiz 9 haneli program kodu sayısına eşit; tekrarlanan kod yok; en küçük puan en büyük puandan büyük olan kayıt yok; yerleşeni olup puanı boş kayıt yok. Örnek kayıtlar PDF metniyle elle karşılaştırıldı.", False),
    ("Veri setinin yıl × yerleştirme × üniversite türü toplamları (program sayısı, kontenjan, yerleşen, boş kontenjan) ÖSYM'nin 'Yerleştirme Sonuçlarına İlişkin Sayısal Bilgiler' tablolarıyla 10 hücrenin tamamında birebir aynıdır (bkz. ÖSYM karşılaştırma sayfası).", False),
    ("", False),
    ("Sınırlılıklar", True),
    ("Tablolar yalnızca en küçük ve en büyük puanı verir; puan dağılımı, ortalama ve aday düzeyinde bilgi yoktur. Analizler program düzeyindedir.", False),
    ("Kontenjanı 1-2 olan gruplarda en küçük ve en büyük puan çoğunlukla aynıdır.", False),
    ("Engelli aday kontenjanlarında 100 ve 500 gibi uç puanlar bulunur (uc_puan = 1).", False),
    ("Bazı programlarda yerleşen sayısı kontenjanı aşar; ek yerleştirmede kontenjan 0 iken yerleşen olabilir. Değerler ÖSYM tablosundaki haliyle bırakılmıştır.", False),
    ("İl bilgisi üniversitenin merkezine göredir; programın yürütüldüğü kampüs farklı bir ilçede olabilir.", False),
]
for t, bold in text:
    c = ws.cell(row=r, column=1, value=t)
    c.font = BOLD if bold else BODY
    c.alignment = WRAP
    if t and not bold:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        ws.row_dimensions[r].height = 15 * max(1, math.ceil(len(t) / 150))
    r += 1
widths(ws, [30, 8, 18, 18, 20])

xlsx = OUT / "ozyes_veriseti.xlsx"
wb.save(xlsx)
print("satır:", len(df), "| program paneli:", len(prow), "| üniversite:", len(unis))
print(counts.to_string(index=False))
