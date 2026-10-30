# src/: ÖSYM placement tables (not included)

This folder holds the five ÖSYM placement tables (lowest and highest placement scores) that `parse.py` reads. They are published by ÖSYM and are not redistributed in this repository.

**Fill it with one command** from the repository root:

```bash
python get_sources.py
```

This downloads the tables from ÖSYM, saves them here under the expected names and checks each file against its SHA-256 checksum. To use copies you already have, put them in a folder with the same layout and run `python get_sources.py --from <folder>`.

Expected files (`ilk` = initial placement, `ek` = supplementary placement):

| File | Document |
|---|---|
| `2024_ilk.pdf` | 2024 initial placement table |
| `2024_ek.pdf` | 2024 supplementary placement table |
| `2025_ilk.pdf` | 2025 initial placement table |
| `2025_ek.pdf` | 2025 supplementary placement table |
| `2026_ilk.pdf` | 2026 initial placement table |

`parse.py` reads only files named `<year>_ilk.pdf` and `<year>_ek.pdf`; other files in this folder are ignored. URLs and checksums: `research_validation/official_source_audit.json`.

---

**Türkçe:** Bu klasöre ÖSYM'nin yerleştirme tabloları (en küçük ve en büyük puanlar) gelir. Depoda yer almazlar; depo kökünde `python get_sources.py` komutu onları ÖSYM'den indirip doğru adlarla buraya kaydeder ve özetlerini doğrular. Dosya adları `<yıl>_ilk.pdf` (ilk yerleştirme) ve `<yıl>_ek.pdf` (ek yerleştirme) olmalıdır.
