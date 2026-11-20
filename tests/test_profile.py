from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from datasetbrief.ai import explain
from datasetbrief.cli import main
from datasetbrief.profile import profile_csv
from datasetbrief.report import render_html


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def csv(self, text):
        path = self.root / "private-name.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_missing_patterns_and_duplicates(self):
        profile = profile_csv(self.csv("id,x,y\n1,2,\n2, ,NA\n2, ,NA\n"))
        self.assertEqual(profile["missing_cells"], 5)
        self.assertEqual(profile["incomplete_rows"], 3)
        self.assertEqual(profile["duplicate_rows"], 1)
        self.assertEqual(profile["missing_patterns"][0], {"columns": ["x", "y"], "rows": 2})

    def test_prefix_boundary_and_header_only(self):
        path = self.csv("a\n1\n2\n")
        self.assertFalse(profile_csv(path, max_rows=2)["prefix_scan"])
        self.assertTrue(profile_csv(path, max_rows=1)["prefix_scan"])
        self.assertEqual(profile_csv(self.csv("a,b\n"))["rows"], 0)

    def test_strict_json_and_html_escaping(self):
        profile = profile_csv(self.csv('"<script>alert(1)</script>",empty\ninf,\n-inf,\n'))
        json.dumps(profile, allow_nan=False)
        self.assertEqual(profile["columns"][0]["infinite"], 2)
        html = render_html(profile)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_na_policy_and_blank_rows(self):
        profile = profile_csv(self.csv("a,b\nUNKNOWN,1\n,\n"), na_values=["UNKNOWN"])
        self.assertEqual(profile["rows"], 2)
        self.assertEqual(profile["missing_cells"], 3)

    def test_ai_contract_excludes_raw_data(self):
        profile = profile_csv(self.csv("name,score\nPRIVATE_PERSON,1\n"))
        generated = {"summary": "One row.", "possible_row_meaning": "Unknown.",
                     "caveats": ["Small dataset."], "next_steps": ["Inspect score units."]}
        response = BytesIO(json.dumps({"message": {"content": json.dumps(generated)}}).encode())
        with patch("datasetbrief.ai.urlopen", return_value=response) as call:
            result = explain(profile, model="test")
        self.assertEqual(result["status"], "generated")
        payload = call.call_args.args[0].data.decode()
        self.assertNotIn("PRIVATE_PERSON", payload)
        self.assertNotIn("private-name.csv", payload)

    def test_cli_ai_failure_preserves_profile(self):
        source = self.csv("a\n1\n")
        out = self.root / "report"
        with patch("datasetbrief.cli.explain", side_effect=ValueError("invalid response")):
            code = main([str(source), "--output", str(out), "--ai-model", "test"])
        self.assertEqual(code, 2)
        self.assertTrue((out / "report.html").is_file())
        self.assertEqual(json.loads((out / "profile.json").read_text())["ai"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
