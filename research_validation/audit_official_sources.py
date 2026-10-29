"""Download URLs discovered through ÖSYM index pages and compare exact bytes."""
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "research_validation/official_sources"
DEST.mkdir(exist_ok=True)
BASE = "https://dokuman.osym.gov.tr/pdfdokuman/"
URLS = {
    "src/2024_ilk.pdf": BASE + "2024/OZYES/YERLESTIRME/minmax_ozyd11102024.pdf",
    "src_sayisal/2024_ilk.pdf": BASE + "2024/OZYES/YERLESTIRME/sayisalbilgiler_ozyd11102024.pdf",
    "src/2024_ek.pdf": BASE + "2024/OZYES/YERLESTIRME/EK/minmaxoz_ed14112024.pdf",
    "src_sayisal/2024_ek.pdf": BASE + "2024/OZYES/YERLESTIRME/EK/sayisalbilgileroz_ed14112024.pdf",
    "src/2025_ilk.pdf": BASE + "2025/OZYES/YERLESTIRME/minmax-ozyyd19092025.pdf",
    "src_sayisal/2025_ilk.pdf": BASE + "2025/OZYES/YERLESTIRME/sayisalbilgiler_ozyyd19092025.pdf",
    "src/2025_ek.pdf": BASE + "2025/OZYES/YERLESTIRME/EK/minmax_oyed27102025.pdf",
    "src_sayisal/2025_ek.pdf": BASE + "2025/OZYES/YERLESTIRME/EK/sayisalbilgiler_oyed27102025.pdf",
    "src/2026_ilk.pdf": "https://dokuman.osym.gov.tr/web/2026/10/2026-ozyes-yerlestirme-sonuclarina-liskin-en-kucuk-ve-en-buyuk-puanlar-ed0yq5-06160838.pdf",
    "src_sayisal/2026_ilk.pdf": "https://dokuman.osym.gov.tr/web/2026/10/2026-ozyes-yerlestirme-sonuclarina-liskin-sayisal-bilgiler-qf6bi9-07071140.pdf",
}


def check(item):
    local, url = item
    result = {"local_file": local, "url": url, "local_sha256": hashlib.sha256((ROOT / local).read_bytes()).hexdigest()}
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()
            result.update(http_status=response.status, final_url=response.url)
        if not content.startswith(b"%PDF-"):
            raise ValueError("Response is not a PDF")
        (DEST / local.replace("/", "_")).write_bytes(content)
        result["remote_sha256"] = hashlib.sha256(content).hexdigest()
        result["identical"] = result["remote_sha256"] == result["local_sha256"]
    except Exception as exc:
        result["error"] = str(exc)
    return result


with ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(check, URLS.items()))
report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "files": rows,
          "pending": [r["local_file"] for r in rows if not r.get("identical")],
          "2026_index": "https://osym.gov.tr/2026-ozyes-yerlestirme-sonuclarina-iliskin-sayisal-bilgiler",
          "2026_announcement": "https://www.osym.gov.tr/2026-yks-kapsaminda-spor-bilimleri-icin-ozel-yetenek-sinavi-ozyes-yerlestirme-sonuclari-aciklandi"}
(ROOT / "research_validation/official_source_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"identical": sum(r.get("identical", False) for r in rows), "total": len(rows), "pending": report["pending"]}, ensure_ascii=False))
