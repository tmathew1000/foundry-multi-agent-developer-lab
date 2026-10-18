import importlib.util
import io
import subprocess
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentTests(unittest.TestCase):
    def test_remote_build_installs_a_portable_package(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text().splitlines()
        self.assertIn(".", requirements)
        self.assertFalse(any(line.startswith(("-e ", "--editable")) for line in requirements))

    def test_verification_prints_specific_environment_blockers(self) -> None:
        verify = load_script("verify_module")
        output = io.StringIO()
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            patch.object(verify.subprocess, "run", return_value=completed),
            redirect_stderr(output),
        ):
            self.assertFalse(verify._post_provision_environment_is_ready(ROOT))
        self.assertIn("model-deployment", output.getvalue())
        self.assertIn("AZURE_AI_MODEL_DEPLOYMENT_NAME", output.getvalue())

    def test_live_smoke_test_requires_completed_nonempty_answer(self) -> None:
        smoke = load_script("smoke_test")
        valid = {
            "status": "completed",
            "output": [{"content": [{"type": "output_text", "text": "Tokyo itinerary"}]}],
        }
        self.assertEqual("Tokyo itinerary", smoke.response_text(valid))
        for invalid in (
            {"status": "incomplete", "output": valid["output"]},
            {"status": "completed", "output": []},
            {"status": "completed", "output": None},
            {"status": "completed", "output": [{"content": None}]},
            {"status": "completed", "error": {"code": "session_not_ready"}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                smoke.response_text(invalid)


if __name__ == "__main__":
    unittest.main()
