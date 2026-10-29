"""Targeted failure-injection tests; real data.json is never written."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ozyes_parser", ROOT / "parse.py")
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
VALID = dict(kod="100190016", tur="DEVLET", uni_raw="Deneme Üniversitesi",
             fak_raw="Spor Bilimleri Fakültesi", prog="Antrenörlük Eğitimi",
             ge=[10, 10, 300.12345, 400.12345])
SENTINEL = b'{"previous_valid_output":true}\n'


class ParserSafety(unittest.TestCase):
    def scenario(self, initial=None, supplementary=None, expected_count=1,
                 error=None, empty=False, success=False, extra_name=None):
        with tempfile.TemporaryDirectory(prefix="ozyes-parser-") as folder:
            root = Path(folder)
            assert root.resolve() != ROOT.resolve()  # never write to the project folder
            src = root / "src"
            src.mkdir()
            output = root / "data.json"
            output.write_bytes(SENTINEL)
            if not empty:
                (src / "2025_ilk.pdf").touch()
            if extra_name:
                (src / extra_name).touch()
            if supplementary is not None:
                (src / "2025_ek.pdf").touch()

            def read(path):
                if error:
                    raise error
                return copy.deepcopy(supplementary if path.stem.endswith("_ek") else initial)

            with patch.object(parser, "ROOT", root), patch.object(parser, "SRC", src), \
                    patch.object(parser, "read_pdf", side_effect=read), \
                    patch.object(parser, "code_count", return_value=expected_count), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                if success:
                    parser.main()
                    result = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(result["2025"][0]["ge"], VALID["ge"])
                    self.assertEqual(result["2025"][0]["uni"], VALID["uni_raw"])
                else:
                    with self.assertRaises((SystemExit, ValueError)):
                        parser.main()
                    self.assertEqual(output.read_bytes(), SENTINEL)

    def test_duplicate_code_preserves_output(self):
        self.scenario([copy.deepcopy(VALID), copy.deepcopy(VALID)])

    def test_code_count_mismatch_preserves_output(self):
        self.scenario([VALID], expected_count=2)

    def test_reversed_score_range_preserves_output(self):
        self.scenario([{**VALID, "ge": [10, 10, 400, 300]}])

    def test_missing_score_preserves_output(self):
        self.scenario([{**VALID, "ge": [10, 10, None, 400]}])

    def test_invalid_supplementary_preserves_output(self):
        self.scenario([VALID], [{**VALID, "ge": [1, 1, 400, 300]}])

    def test_reader_exception_preserves_output(self):
        self.scenario([VALID], error=ValueError("injected PDF read failure"))

    def test_empty_source_preserves_output(self):
        self.scenario(empty=True)

    def test_valid_source_updates_output(self):
        self.scenario([VALID], success=True)

    def test_empty_extraction_preserves_output(self):
        self.scenario([], expected_count=0)

    def test_original_download_name_is_ignored(self):
        self.scenario([VALID], success=True, extra_name="minmax_ozyd11102024.pdf")


if __name__ == "__main__":
    before = hashlib.sha256((ROOT / "data.json").read_bytes()).hexdigest()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ParserSafety))
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "parser_sha256": hashlib.sha256((ROOT / "parse.py").read_bytes()).hexdigest(),
              "production_data_sha256": before,
              "production_data_unchanged": before == hashlib.sha256((ROOT / "data.json").read_bytes()).hexdigest(),
              "scope": "Synthetic rows exercise real check/main; mocked PDF reader and code counter. No real production output writes."}
    (ROOT / "research_validation/parser_safety.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(not result.wasSuccessful())
