# Validation scripts and records

Run from the repository root after the pipeline steps in the main README. Each script writes its record next to itself. The recorded outputs in this folder are from 10 and 11 October 2026 (Windows 11, Python 3.12.14, Node.js 24.19.0).

| Script | What it checks | Record |
|---|---|---|
| `audit_data.py` | Reads every program row a second time from the pypdf text layer and compares all 33,408 numeric fields with the pdfplumber output and `data.json`; recomputes the nine derived variables (64,530 fields); compares totals with the 40 values of the ÖSYM numerical summaries; builds the program tracking links | `data_audit.json`, `panel_links.json`, `dataset_records.json` (not tracked) |
| `audit_quota_transfer.py` | Tests the published quota transfer rule: over-filled groups only in general quotas, and each excess within the vacancy of the transfer source group of the same program and sex | `quota_transfer_audit.json` |
| `audit_exports.py` | Runs `dataset/build_dataset.py` unmodified in a separate folder and reads the CSV, XLSX and SAV files back (236,610 fields each; SPSS labels) | `export_audit.json` |
| `audit_parser_real.py` | Full parser run on the real sources into a separate folder; compares with `data.json` | `parser_real_audit.json` |
| `test_parser_safety.py` | Ten failure-injection tests: the parser must not overwrite its previous output when a check fails | `parser_safety.json` |
| `audit_official_sources.py` | Downloads the ten source documents from ÖSYM and compares checksums with the local copies (needs network access) | `official_source_audit.json` |
| `audit_link_sources.py` | Locates the old and new codes of the 24 code-change links in the source PDFs | `link_source_evidence.json`, `kod_degisikligi_kanit_raporu.md` (Turkish; English version in `docs/code_change_source_review.md`) |
| `audit_descriptors.py` | Compares the provinces printed in the source tables with the lookup table, the province-to-NUTS-1 table with Eurostat's NUTS 2024 classification (downloaded from github.com/eurostat/Nuts2json; checksum recorded), and counts sport management programs per table (added after v1.0.0; needs `release/out/`) | `descriptor_audit.json` |
| `audit_app.cjs` (Node.js) | Runs the browser viewer's data preparation, filtering, sorting and program history functions against independently computed references (needs `dataset_records.json` from `audit_data.py`) | `app_audit.json` |

The scripts record discrepancies rather than failing; read the records, not only the exit code. Checks on the same source records are not independent samples, so their counts should not be added up as an error rate.

The English release script (`release/build_release.py`) also stops if any value differs from the Turkish dataset, if the program file and the long table disagree, or if any dataset total differs from the ÖSYM summaries.
