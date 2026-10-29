"""ÖSYM ÖZYES (YKS Spor Bilimleri Özel Yetenek) en küçük / en büyük puan PDF'lerini JSON'a çevirir.

Kaynak dosyalar src/ klasöründe şu adla durur:  <yıl>_ilk.pdf  ve  <yıl>_ek.pdf
Yeni yıl eklemek için PDF'i bu adla src/ içine koyup betiği çalıştırmak yeterlidir.

Çıktı: data.json
  { "2026": [ {kod, tur, uni, sehir, fak, prog, ptur, burs, dil,
               ge, gk, me, mk, ee, ek,          # ilk yerleştirme grupları
               x: {ge, gk, ee, ek} | null }, ... ], ... }
  Grup dizisi: [kontenjan, yerleşen, en küçük puan, en büyük puan]
  x: aynı yılın ek yerleştirme değerleri (ek tablosunda milli sporcu grubu yoktur).
"""
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).parent
SRC = ROOT / "src"
GROUP_BY_HEADER = {
    "Genel Kontenjan Erkek": "ge",
    "Genel Kontenjan Kadın": "gk",
    "Milli Sporcu Kontenjanı Erkek": "me",
    "Milli Sporcu Kontenjanı Kadın": "mk",
    "Engelli Aday Kontenjanı Erkek": "ee",
    "Engelli Aday Kontenjanı Kadın": "ek",
}
FEE_RE = r"\((Burslu|Ücretli|%\d+ İndirimli)\)"
SMALL = {"ve", "ile", "için"}


def num(s):
    s = (s or "").strip().replace("\n", "")
    if s in ("", "--", "-"):
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def tr_lower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_title(s):
    """'SPOR BİLİMLERİ FAKÜLTESİ' -> 'Spor Bilimleri Fakültesi'"""
    out = []
    for i, w in enumerate(tr_lower(s).split(" ")):
        if i > 0 and w in SMALL:
            out.append(w)
            continue
        first = w[:1]
        first = {"i": "İ", "ı": "I"}.get(first, first.upper())
        out.append(first + w[1:])
    return " ".join(out)


def read_pdf(path):
    """Tablodaki her program satırını {kod, meta..., grup: [...]} sözlüğü olarak döndürür."""
    rows = []
    with pdfplumber.open(path) as pdf:
        groups = None
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if r and r[0] is None and any(c in GROUP_BY_HEADER for c in r if c):
                        groups = [GROUP_BY_HEADER[clean(c)] for c in r if c and clean(c) in GROUP_BY_HEADER]
                        continue
                    if not r or not r[0] or not re.fullmatch(r"\d{9}", clean(r[0])):
                        continue
                    if groups is None or len(r) != 5 + 4 * len(groups):
                        sys.exit(f"HATA: {path.name} beklenmeyen sütun sayısı {len(r)}: {r[:5]}")
                    rec = {"kod": clean(r[0]), "tur": clean(r[1]), "uni_raw": clean(r[2]),
                           "fak_raw": clean(r[3]), "prog": clean(r[4])}
                    for i, g in enumerate(groups):
                        b = 5 + i * 4
                        k, y = num(r[b]), num(r[b + 1])
                        rec[g] = [None if k is None else int(k), None if y is None else int(y),
                                  num(r[b + 2]), num(r[b + 3])]
                    rows.append(rec)
    return rows


def enrich(rec, fak_by_kod):
    # 2024 ve 2026 tablolarında üniversite türü adın sonuna ek olarak yazılmış;
    # 2026'da bazı adların sonunda dipnot yıldızı (*) var. Bunlar ad değil, temizlenir.
    uni = rec.pop("uni_raw")
    for suffix in (" (Devlet Üniversitesi)", " (Vakıf Üniversitesi)"):
        uni = uni.replace(suffix, "")
    uni = uni.rstrip("*").strip()
    m = re.search(r"\(([^()]*)\)\s*$", uni)
    rec["uni"] = re.sub(r"\s*\([^()]*\)\s*$", "", uni) if m else uni
    rec["sehir"] = m.group(1) if m else ""
    fak = rec.pop("fak_raw")
    if fak.isupper():
        fak = fak_by_kod.get(rec["kod"]) or tr_title(fak)
    rec["fak"] = fak
    fm = re.search(FEE_RE, rec["prog"])
    rec["burs"] = fm.group(1) if fm else ""
    base = clean(re.sub(FEE_RE, "", rec["prog"]))
    rec["dil"] = "İngilizce" if "(İngilizce)" in base else "Türkçe"
    rec["ptur"] = clean(base.replace("(İngilizce)", ""))
    return rec


def code_count(path):
    """Kontrol için: PDF metnindeki 9 haneli program kodu sayısı."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    return len(set(re.findall(r"(?<!\d)[1-4]\d{8}(?!\d)", text)))


def check(name, rows, path):
    problems = []
    if not rows:
        problems.append("program satırı okunamadı")
    kods = [r["kod"] for r in rows]
    if len(kods) != len(set(kods)):
        problems.append("tekrarlanan program kodu")
    expected = code_count(path)
    if expected != len(rows):
        problems.append(f"PDF'te {expected} kod var, {len(rows)} satır okundu")
    for r in rows:
        for g in GROUP_BY_HEADER.values():
            if g not in r:
                continue
            k, y, mn, mx = r[g]
            if mn is not None and mx is not None and mn > mx:
                problems.append(f"{r['kod']} {g}: en küçük > en büyük")
            if y and mn is None:
                problems.append(f"{r['kod']} {g}: yerleşen var, puan yok")
    print(f"{name}: {len(rows)} program", "OK" if not problems else "SORUN: " + "; ".join(problems[:5]))
    return not problems


def main():
    files = sorted(f for f in SRC.glob("*.pdf") if re.fullmatch(r"\d{4}_(ilk|ek)\.pdf", f.name))
    years = sorted({int(f.name.split("_")[0]) for f in files}, reverse=True)
    if not years:
        sys.exit("HATA: Kaynak PDF bulunamadı; data.json değiştirilmedi.")
    out, ok = {}, True
    fak_by_kod = {}
    for y in sorted(years):  # eski yıllar önce: büyük harfli fakülte adlarını önceki yıldan düzeltmek için
        ilk_path = SRC / f"{y}_ilk.pdf"
        ek_path = SRC / f"{y}_ek.pdf"
        ilk = read_pdf(ilk_path)
        ok &= check(f"{y} ilk", ilk, ilk_path)
        rows = [enrich(r, fak_by_kod) for r in ilk]
        for r in rows:
            fak_by_kod[r["kod"]] = r["fak"]
            r["x"] = None
        if ek_path.exists():
            ek = read_pdf(ek_path)
            ok &= check(f"{y} ek", ek, ek_path)
            by = {r["kod"]: r for r in rows}
            orphan = 0
            for e in ek:
                target = by.get(e["kod"])
                if target is None:
                    orphan += 1
                    continue
                target["x"] = {g: e[g] for g in ("ge", "gk", "ee", "ek") if g in e}
            if orphan:
                print(f"  UYARI: {y} ek tablosunda ilk tabloda olmayan {orphan} kod var")
        out[str(y)] = rows
    if not ok:
        print("HATA: Doğrulama başarısız; data.json değiştirilmedi.", file=sys.stderr)
        sys.exit(1)
    (ROOT / "data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("data.json yazıldı:", {y: len(v) for y, v in out.items()})


if __name__ == "__main__":
    main()
