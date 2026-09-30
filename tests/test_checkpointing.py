import tempfile
import unittest
from pathlib import Path

from travel_buddy.checkpointing import apply_restore, restore_plan, start_plan


class CheckpointingTests(unittest.TestCase):
    def test_module_mapping_and_dry_run_do_not_modify_destination(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "checkpoints/01-tools/solution/activity_tool.py"
            destination = root / "src/travel_buddy/tools.py"
            source.parent.mkdir(parents=True)
            destination.parent.mkdir(parents=True)
            source.write_text("solution\n", encoding="utf-8")
            destination.write_text("learner\n", encoding="utf-8")

            operations = restore_plan(root, "2")
            reported = apply_restore(operations, dry_run=True)

            self.assertEqual([destination], reported)
            self.assertEqual("learner\n", destination.read_text(encoding="utf-8"))

    def test_apply_restore_replaces_mapped_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "checkpoints/02-orchestration/solution/workflow_step.py"
            agent_source = root / "checkpoints/02-orchestration/solution/agents_step.py"
            destination = root / "src/travel_buddy/workflow.py"
            agent_destination = root / "src/travel_buddy/agents.py"
            source.parent.mkdir(parents=True)
            destination.parent.mkdir(parents=True)
            source.write_text("solution\n", encoding="utf-8")
            agent_source.write_text("agent solution\n", encoding="utf-8")
            destination.write_text("learner\n", encoding="utf-8")
            agent_destination.write_text("agent learner\n", encoding="utf-8")

            apply_restore(restore_plan(root, "3"), dry_run=False)

            self.assertEqual("solution\n", destination.read_text(encoding="utf-8"))
            self.assertEqual("agent solution\n", agent_destination.read_text(encoding="utf-8"))

    def test_start_plan_uses_starter_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "checkpoints/01-tools/starter/activity_tool.py"
            destination = root / "src/travel_buddy/tools.py"
            source.parent.mkdir(parents=True)
            destination.parent.mkdir(parents=True)
            source.write_text("starter\n", encoding="utf-8")
            destination.write_text("solution\n", encoding="utf-8")

            apply_restore(start_plan(root, "2"), dry_run=False)

            self.assertEqual("starter\n", destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
