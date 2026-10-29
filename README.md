# ÖZYES placement data: extraction, dataset and validation code

[![DOI](https://zenodo.org/badge/1410005340.svg)](https://doi.org/10.5281/zenodo.23783909)

Code that converts the placement tables published by the Centre for Assessment, Selection and Placement (ÖSYM) for sport sciences programs admitting students through the Special Talent Examination for Sport Sciences (ÖZYES) into a validated, machine-readable dataset.

Coverage: 2024, 2025 and 2026 initial placements; 2024 and 2025 supplementary placements.

- **Dataset:** Zenodo, https://doi.org/10.5281/zenodo.23782814 (CC BY 4.0)
- **This code:** archived at Zenodo, https://doi.org/10.5281/zenodo.23783909 (all versions; v1.0.0: https://doi.org/10.5281/zenodo.23783910) (MIT)
- **Data descriptor:** [citation after publication]

## Pipeline

```
ÖSYM PDFs ──get_sources.py──▶ src/, src_sayisal/
src/*.pdf ──parse.py──▶ data.json ──dataset/build_dataset.py──▶ dataset/out/ (Turkish CSV, XLSX, SAV)
                                                    └──release/build_release.py──▶ release/out/ (English release)
data.json ──build.py──▶ ozyes-analizor.html (optional Turkish browser viewer)
```

| Step | Script | Output |
|---|---|---|
| 1. Get sources | `get_sources.py` | the ten ÖSYM PDFs, checked against their SHA-256 checksums |
| 2. Extract | `parse.py` | `data.json`, one record per program and year; stops without writing if a structural check fails |
| 3. Build dataset | `dataset/build_dataset.py` | long-format table (7,170 rows) with program tracking panels and derived variables, in Turkish CSV, Excel and SPSS formats |
| 4. Release | `release/build_release.py` | English CSV files, codebook, source list and checksums, as deposited at Zenodo; see `release/README.md` |
| Optional | `build.py` | single-file Turkish browser viewer with filtering and program histories |

## Reproduce

Requires Python 3.12 or later.

```bash
pip install -r requirements.txt
python get_sources.py                    # downloads and verifies the ten source PDFs
python parse.py
cd dataset && python build_dataset.py && cd ..
python release/build_release.py
```

`release/out/SHA256SUMS.txt` should then match the checksums in the Zenodo record. The released files are written with Unix line endings on every platform; the Turkish CSV in `dataset/out/` uses the platform's line endings.

If ÖSYM moves a document, `get_sources.py` reports which file failed. Copies obtained elsewhere can be checked with `python get_sources.py --from <folder>`.

## Validation

Scripts and their recorded outputs are in `research_validation/`; see `research_validation/README.md`. The recorded outputs are from the run of 10 and 11 October 2026 (Windows 11, Python 3.12.14). On 30 October 2026 the full pipeline and all validation scripts were re-run in a clean copy (Linux, Python 3.13.18, same package versions): `data.json` and the released files were byte-identical and all checks gave the same results.

## Repository layout

```
parse.py                    PDF extraction
get_sources.py              download and checksum verification of the sources
dataset/                    long-format dataset (build_dataset.py, lookups.py: university to province, osym_ozet.py: official totals)
release/                    English release script and dataset README
research_validation/        validation scripts and recorded outputs
docs/                       source review of program code changes
app.js, template.html, build.py   Turkish browser viewer
```

Source PDFs, `data.json` and all generated outputs are not tracked; they are recreated by the steps above.

## Licence

Code: MIT (see `LICENSE`). Dataset files produced by the pipeline: CC BY 4.0. The source documents are published by ÖSYM and are not redistributed here.

## Citation

See `CITATION.cff`. Please cite the dataset and, once published, the data descriptor.

---

**Türkçe özet.** Bu depo, ÖSYM'nin ÖZYES ile öğrenci alan programlara ilişkin yerleştirme tablolarını (PDF) okuyup doğrulanmış, makinece okunabilir bir veri setine dönüştüren kodu içerir. Türkçe değişken adlı CSV/Excel/SPSS çıktıları `dataset/build_dataset.py`, İngilizce açık sürüm `release/build_release.py` ile üretilir. Tarayıcıda çalışan Türkçe görüntüleyici `build.py` ile oluşturulur.
