"""Every pack that ships tests is named in the CI command that runs them.

The list in `.github/workflows/ci.yml` is hand-written, and a hand-written list
of packs is the failure this repository already has on record: ten of sixteen
registry packs sat outside both CI lists while their own suites passed, against
their own fixtures, and nobody noticed because a pack that is absent from a
command line produces no output at all. A suite that does not run and a suite
with nothing to say are the same silence.

So the list is checked against the tree rather than trusted. Adding a pack with
tests and forgetting the workflow now fails here, on the change that introduced
it, instead of years later when someone asks why a green CI never caught a
defect the pack's own suite tests for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"


def packs_shipping_python_tests() -> set[str]:
    """Derived from the tree, never enumerated.

    A `tests/` directory holding no `test_*.py` is not a suite pytest would
    collect, so it is not something CI can be expected to name.
    """
    found = set()
    for tests_dir in REPO.glob("*/tests"):
        if any(tests_dir.glob("test_*.py")):
            found.add(tests_dir.parent.name)
    return found


def pytest_targets_in_ci() -> set[str]:
    """The pack directories named on any `python3 -m pytest` line in the file.

    Read out of the parsed YAML rather than by grepping the raw text, so a
    target inside a commented-out step cannot count as coverage.
    """
    workflow = yaml.safe_load(CI.read_text())
    targets: set[str] = set()
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            run = step.get("run")
            if not run or "pytest" not in run:
                continue
            for word in re.findall(r"[\w./-]+", run):
                head, _, rest = word.partition("/")
                if rest.startswith("tests"):
                    targets.add(head)
    return targets


def test_every_pack_with_a_python_suite_is_run_by_ci() -> None:
    shipping = packs_shipping_python_tests()
    assert shipping, "the derivation found no pack suites at all, which is the "\
                     "instrument failing rather than the repository being empty"

    missing = sorted(shipping - pytest_targets_in_ci())
    assert not missing, (
        "these packs ship a python suite that no CI step runs: "
        + ", ".join(missing)
        + f" -- add '<pack>/tests' to the pytest step in {CI.relative_to(REPO)}"
    )


def test_the_check_notices_a_pack_that_is_absent_from_the_workflow() -> None:
    """The other rail.

    A membership check over two sets it derives itself can pass because both
    derivations broke, so the failing direction is exercised against a pack
    name the workflow provably does not contain.
    """
    absent = "a-pack-no-workflow-mentions"
    assert absent not in pytest_targets_in_ci()
    assert absent not in packs_shipping_python_tests()
