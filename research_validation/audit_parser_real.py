"""Exercise the full parser with actual PDFs; redirect only its output directory."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ozyes_parser", ROOT / "parse.py")
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
output = ROOT / "research_validation/parser_real_run"
output.mkdir(exist_ok=True)
source = ROOT / "data.json"
before = hashlib.sha256(source.read_bytes()).hexdigest()
with patch.object(parser, "ROOT", output):
    parser.main()
generated = output / "data.json"
report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
          "parser_sha256": hashlib.sha256((ROOT / "parse.py").read_bytes()).hexdigest(),
          "generated_sha256": hashlib.sha256(generated.read_bytes()).hexdigest(),
          "original_sha256": before,
          "object_equal": json.loads(generated.read_text(encoding="utf-8")) == json.loads(source.read_text(encoding="utf-8")),
          "production_unchanged": before == hashlib.sha256(source.read_bytes()).hexdigest()}
(ROOT / "research_validation/parser_real_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(not (report["object_equal"] and report["production_unchanged"]))
