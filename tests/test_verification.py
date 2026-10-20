import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from travel_buddy.cloud_evaluation import write_result
from travel_buddy.verification import MODULE_IDENTIFIERS, module_checks, normalize_module_identifier


class VerificationTests(unittest.TestCase):
    def test_missing_live_results_do_not_select_fallback(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(
                Path(__file__).parents[1] / "artifacts" / "evaluations",
                root / "artifacts" / "evaluations",
            )
            self.assertFalse(module_checks(root, "5")[0][1]())
            self.assertTrue(module_checks(root, "5", fallback=True)[0][1]())

    def test_custom_results_directory_is_used(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "experiment"
            with patch("travel_buddy.verification._comparable", return_value=True) as compare:
                for module in normalize_module_identifier("all"):
                    checks = module_checks(root, module, results_dir=results)
                    if module == "5":
                        self.assertTrue(checks[0][1]())
                compare.assert_called_once_with(
                    results / "baseline.json", results / "candidate.json"
                )
            with self.assertRaisesRegex(ValueError, "not both"):
                module_checks(root, "5", results_dir=results, fallback=True)

    def test_verifier_cli_requires_explicit_fallback(self) -> None:
        script = Path(__file__).parents[1] / "scripts" / "verify_module.py"
        with TemporaryDirectory() as directory:
            missing = subprocess.run(
                [sys.executable, str(script), "5", "--results-dir", directory],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, missing.returncode)
            self.assertIn("Missing evaluation results", missing.stdout)
        fallback = subprocess.run(
            [sys.executable, str(script), "5", "--fallback"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, fallback.returncode, fallback.stderr)
        self.assertIn("illustrative", fallback.stdout.casefold())

    def test_invalid_or_mixed_results_fail_verification(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_result(
                root / "baseline.json",
                {"artifact_kind": "fallback", "metrics": {}},
            )
            for payload in ('{"artifact_kind": "live", "metrics": {}}', "invalid json"):
                with self.subTest(payload=payload):
                    (root / "candidate.json").write_text(payload, encoding="utf-8")
                    self.assertFalse(module_checks(root, "5", results_dir=root)[0][1]())

    def test_all_expands_to_modules_zero_through_five(self) -> None:
        self.assertEqual(MODULE_IDENTIFIERS, normalize_module_identifier("all"))

    def test_invalid_module_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "0-5 or all"):
            normalize_module_identifier("6")


if __name__ == "__main__":
    unittest.main()
