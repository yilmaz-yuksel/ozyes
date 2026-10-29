# Program-level placement results for sport sciences undergraduate admissions in Turkey, 2024 to 2026

Version 1.0 · [date of deposit]
Author: Yılmaz Yüksel, Karabük University, Hasan Doğan Faculty of Sport Sciences (ORCID 0000-0003-1816-2916)
Licence: data CC BY 4.0; code MIT
Data descriptor: [citation after publication]

## What this is

Machine-readable versions of all placement tables published by the Centre for Assessment, Selection and Placement (ÖSYM) for programs that admit students through the Special Talent Examination for Sport Sciences (ÖZYES):

- 2024, 2025 and 2026 initial placements
- 2024 and 2025 supplementary placements

The source tables report, for each program, the quota, number placed and lowest and highest placement scores for the general, national-athlete and disability quotas, separately for male and female candidates. The data are aggregate and contain no candidate-level information.

## Files

| File | Rows | Unit |
|---|---|---|
| `ozyes_placement_groups.csv` | 7,170 | year × placement round × program code × quota type × sex (groups with quota > 0 or placed > 0) |
| `ozyes_programs.csv` | 413 | program tracking panel |
| `ozyes_universities.csv` | 108 | university |
| `ozyes_official_totals.csv` | 10 | year × round × university type, dataset totals next to ÖSYM published totals |
| `ozyes_quota_transfer.csv` | 3,079 | year × round × program code × sex, check of the quota transfer rule |
| `codebook.csv` | | definition of every variable |
| `SHA256SUMS.txt` | | checksums of the CSV files |

All files: UTF-8 (no BOM), comma-separated, header row, decimal point, empty field = missing. To open in Excel with correct Turkish characters, use Data > From Text/CSV and choose UTF-8.

## Before you analyse

1. **Rows are quota groups, not programs.** Count programs with `sum(program_counter)` within a year and round.
2. **Vacancy.** ÖSYM's vacant quota is `sum(quota) - sum(placed)`. `group_vacancy` is computed per group, so its sum is larger.
3. **Over-filled general groups are expected.** Vacant national-athlete places (initial placement) and vacant disability places (supplementary placement) are transferred to the general quota of the same program and sex. `fill_ratio` can therefore exceed 1, and a supplementary general quota of 0 can have placed candidates. See `ozyes_quota_transfer.csv`.
4. **Longitudinal work:** use `program_panel_id`; ÖSYM codes changed for 24 programs between 2024 and 2025.
5. **Tuition options** of one program have separate codes; `program_group_id` combines them.
6. **Scores:** only the lowest and highest scores of each group are published. Twelve groups have a score of exactly 100 or 500 (`boundary_score_flag = 1`), kept as published.
7. **Names** of universities, units and programs are in Turkish, as in the source; categories and the codebook are in English.

## Sources

The ten ÖSYM source documents (five placement tables, five numerical summaries) are listed with URLs and SHA-256 checksums in `sources.csv`. They are not redistributed here; download them from ÖSYM.

## Reproducing

With the code repository (https://github.com/yilmaz-yuksel/ozyes):

```bash
pip install -r requirements.txt
python get_sources.py                    # downloads the ten ÖSYM PDFs and verifies their checksums
python parse.py                          # PDF -> data.json (stops if a check fails)
cd dataset && python build_dataset.py    # -> dataset/out/ (Turkish CSV, XLSX, SAV)
cd .. && python release/build_release.py # -> release/out/ (this release)
```

Tested with Python 3.12.14, pdfplumber 0.11.9, pandas 3.0.1, openpyxl 3.1.5, pyreadstat 1.3.6.

## Versions

New placement rounds (starting with the 2026 supplementary placement) will be added as new versions of this record.

## Citation

Yüksel, Y. Program-level placement results for sport sciences undergraduate admissions in Turkey, 2024 to 2026. Zenodo https://doi.org/10.5281/zenodo.[XXXXXXX] (2026).
