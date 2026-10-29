"""Download the ten ÖSYM source documents and verify their SHA-256 checksums.

The URLs and expected checksums are read from research_validation/official_source_audit.json.
Files are saved under the names the pipeline expects:
    src/<year>_ilk.pdf, src/<year>_ek.pdf            placement tables (ilk = initial, ek = supplementary)
    src_sayisal/<year>_ilk.pdf, src_sayisal/<year>_ek.pdf   numerical summaries

Usage:
    python get_sources.py                  # download from ÖSYM
    python get_sources.py --from DIR       # copy from a local folder with the same layout (offline)

Exit code 0 only if every file is present and matches its expected checksum.
"""
import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "research_validation" / "official_source_audit.json"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src_dir", type=Path, help="copy from a local folder instead of downloading")
    ap.add_argument("--force", action="store_true", help="replace files that already exist")
    args = ap.parse_args()

    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    ok = True
    for e in entries:
        rel = Path(e["local_file"].replace("\\", "/"))
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not args.force and sha256(target) == e["local_sha256"]:
            print(f"ok (present)  {rel}")
            continue
        tmp = target.with_suffix(".part")
        try:
            if args.src_dir:
                shutil.copyfile(args.src_dir / rel, tmp)
            else:
                req = urllib.request.Request(e["url"], headers={"User-Agent": "ozyes-get-sources"})
                with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                    shutil.copyfileobj(r, f)
        except Exception as exc:  # network or file error
            print(f"FAILED        {rel}: {exc}")
            tmp.unlink(missing_ok=True)
            ok = False
            continue
        got = sha256(tmp)
        if got != e["local_sha256"]:
            print(f"CHECKSUM DIFF {rel}: expected {e['local_sha256'][:16]}..., got {got[:16]}... (kept as {tmp.name})")
            ok = False
            continue
        tmp.replace(target)
        print(f"ok            {rel}")
    if not ok:
        print("\nSome files are missing or differ from the versions used to build the dataset.", file=sys.stderr)
        sys.exit(1)
    print(f"\nAll {len(entries)} source documents verified.")


if __name__ == "__main__":
    main()
