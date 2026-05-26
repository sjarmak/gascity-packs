from __future__ import annotations

import os
import pathlib
import tomllib
import unittest


FORMULAS = {
    "build-run",
    "do-work",
    "do-work-item",
    "fix-convoy",
    "gap-analysis",
    "implement",
    "publish",
    "review",
    "same-session-implement",
}


class FormulaAssetTests(unittest.TestCase):
    def test_expected_formula_set_is_convoy_first(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        paths = sorted((root / "formulas").glob("*.formula.toml"))

        self.assertEqual({path.name.removesuffix(".formula.toml") for path in paths}, FORMULAS)
        for path in paths:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            name = path.name.removesuffix(".formula.toml")
            self.assertEqual(data["formula"], name)
            self.assertEqual(data["contract"], "graph.v2")
            var_names = set(data.get("vars", {}))
            self.assertNotIn("issue", var_names)
            self.assertNotIn("bead_id", var_names)
            self.assertNotIn("convoy_id", var_names, f"{path.name} must not redeclare reserved convoy_id")

    def test_implement_formula_uses_core_drain_steps(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        data = tomllib.loads((root / "formulas" / "implement.formula.toml").read_text(encoding="utf-8"))

        step_ids = [step["id"] for step in data["steps"]]
        self.assertEqual(step_ids, ["prepare", "drain-separate", "drain-same-session", "wait-for-drain", "summarize"])

        separate = data["steps"][1]
        same = data["steps"][2]
        self.assertEqual(separate["condition"], "{{drain_policy}} == separate")
        self.assertEqual(separate["drain"]["context"], "separate")
        self.assertEqual(separate["drain"]["formula"], "do-work")
        self.assertEqual(separate["drain"]["member_access"], "exclusive")
        self.assertEqual(same["condition"], "{{drain_policy}} == same-session")
        self.assertEqual(same["drain"]["context"], "shared")
        self.assertEqual(same["drain"]["formula"], "do-work-item")
        self.assertEqual(same["drain"]["member_access"], "exclusive")
        self.assertTrue(same["drain"]["item"]["single_lane"])
        self.assertEqual(same["drain"]["on_item_failure"], "skip_remaining")

        helper = tomllib.loads((root / "formulas" / "same-session-implement.formula.toml").read_text(encoding="utf-8"))
        self.assertEqual(helper["steps"][0]["drain"]["member_access"], "exclusive")

    def test_report_formulas_are_targetless_and_report_only(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        for name in ("gap-analysis", "review"):
            data = tomllib.loads((root / "formulas" / f"{name}.formula.toml").read_text(encoding="utf-8"))
            self.assertEqual(data["mode"], "report")
            self.assertFalse(data["target_required"])
            self.assertEqual([step["id"] for step in data["steps"]], ["validate-context", "write-report"])

    def test_check_scripts_are_executable_and_portable(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        scripts = sorted((root / "assets" / "scripts" / "checks").glob("*.sh"))

        self.assertEqual(
            [script.name for script in scripts],
            ["gap-analysis-approved.sh", "implementation-review-approved.sh"],
        )
        for script in scripts:
            text = script.read_text(encoding="utf-8")
            self.assertTrue(os.access(script, os.X_OK), f"{script} must be executable")
            self.assertNotIn("/data/projects", text)
            self.assertNotIn("gascity-packs-worktrees", text)


if __name__ == "__main__":
    unittest.main()
