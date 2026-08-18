"""Every test file in the tree is collected by a CI step, and the ones that
need a real `gc` are given one.

The list in `.github/workflows/ci.yml` is hand-written, and a hand-written list
of packs is the failure this repository already has on record: ten of sixteen
registry packs sat outside both CI lists while their own suites passed, against
their own fixtures, and nobody noticed because a pack that is absent from a
command line produces no output at all. A suite that does not run and a suite
with nothing to say are the same silence.

So the list is checked against the tree rather than trusted. Both checks here
are written to err toward RED: a derivation that misses a test file, or reads a
skipped suite as covered, hands back a green that certifies nothing, which is
the failure being guarded rather than a milder version of it. A derivation that
flags a file CI does in fact run costs someone a minute.

The first version of this file counted pack NAMES and looked only in
`<pack>/tests`. It reported full coverage while five test files under
`oversight-rig/skills/` and `oversight-rig/assets/` had never run in CI, and it
accepted a `#` comment mentioning pytest as proof a suite executed. Both are
fixed here by working in resolved paths that have to exist on disk.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"

# A file declares this to say it cannot do its job without a real gc binary.
# It is a declaration and not an inference: "imports the live-city harness" was
# the inference, and it missed `test_gc_role_prompt_integration.py`, which
# reaches for `GC_TEST_BIN` through a fixture of its own. Anything that skips
# without a binary belongs here, whatever route it takes to ask for one.
DECLARATION = "REQUIRES_GC_BINARY"


def every_test_file() -> set[Path]:
    """Every `test_*.py` in the tree, wherever it sits.

    Recursive, and rooted at the packs themselves rather than at
    `<pack>/tests`, because pytest collects what it is pointed at and a pack is
    free to put a suite beside the code it tests. Pack roots come from
    `pack.toml` so that a stray top-level directory holding a `tests/` folder
    is not mistaken for a pack.
    """
    roots = [path.parent for path in REPO.glob("*/pack.toml")]
    roots.append(REPO / "tests")
    found: set[Path] = set()
    for root in roots:
        for path in root.rglob("test_*.py"):
            if ".pytest_cache" in path.parts or "__pycache__" in path.parts:
                continue
            found.add(path.resolve().relative_to(REPO))
    return found


def _run_lines(step: dict) -> list[str]:
    """The executable lines of a step's shell block.

    Continuations are joined first so a command split across lines is one
    line, then comments are dropped. Without the second step a commented-out
    `# python3 -m pytest <pack>/tests` reads exactly like the real thing, and
    deleting a suite from CI while leaving that comment behind is invisible.
    """
    run = step.get("run") or ""
    joined = re.sub(r"\\\n\s*", " ", run)
    return [line for line in joined.splitlines() if not line.strip().startswith("#")]


def _paths_on(line: str) -> set[Path]:
    """The repo paths named after `pytest` on one line.

    A token counts only if it resolves to something that exists inside the
    repository. That is what separates `factory-audit/tests` from `-q`, from
    `factory-audit/tests-disabled`, and from a path someone mistyped -- the
    typo then reads as absent coverage, which is the safe direction.
    """
    tokens = line.split()
    if "pytest" not in tokens:
        return set()
    named: set[Path] = set()
    for token in tokens[tokens.index("pytest") + 1:]:
        if token.startswith("-"):
            continue
        candidate = (REPO / token).resolve()
        if not candidate.exists():
            continue
        try:
            named.add(candidate.relative_to(REPO))
        except ValueError:
            continue
    return named


def _steps() -> list[dict]:
    workflow = yaml.safe_load(CI.read_text())
    return [
        step
        for job in workflow.get("jobs", {}).values()
        for step in job.get("steps", [])
    ]


def pytest_targets_in_ci() -> set[Path]:
    return {path for step in _steps() for line in _run_lines(step) for path in _paths_on(line)}


def uncovered(files: set[Path], targets: set[Path]) -> set[Path]:
    """Pure, so the failing direction can be exercised on inputs of our choosing.

    A file is covered when a target is the file itself or a directory above it,
    which is how pytest actually collects. Comparing strings instead rejected
    `./factory-audit/tests` and `tests/`, both of which run the suite.
    """
    return {
        path
        for path in files
        if not any(path == target or target in path.parents for target in targets)
    }


def declares_needing_gc(path: Path) -> bool:
    """Read the declaration structurally, not as a substring.

    This file names the constant in its own source, so a text search flags the
    check itself. An instrument that reports on its own source is the failure
    this repository keeps hitting.
    """
    try:
        tree = ast.parse((REPO / path).read_text())
    except (SyntaxError, ValueError):
        return False
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if DECLARATION in names and node.value.__class__ is ast.Constant:
            return bool(node.value.value)
    return False


def suites_needing_a_real_gc() -> set[Path]:
    return {path for path in every_test_file() if declares_needing_gc(path)}


def suites_that_ask_for_a_binary() -> set[Path]:
    """Files whose source reaches for a gc binary by any route.

    The rail under the declaration: this is the inference, and it exists only
    to catch a file that needs a binary and forgot to say so. It is allowed to
    over-report, because the fix for a false hit is to add the declaration.
    """
    imports = re.compile(r"^\s*(from|import)\s+gc_live_city\b", re.MULTILINE)
    here = Path(__file__).resolve().relative_to(REPO)
    asks = set()
    for path in every_test_file():
        # This file names the variable it searches for, so a text search over
        # the tree finds it and asks it to declare a requirement it does not
        # have. Excluded by path rather than by making the pattern cleverer:
        # the exclusion is one line and honest about what it is.
        if path == here:
            continue
        text = (REPO / path).read_text()
        if imports.search(text) or "GC_TEST_BIN" in text:
            asks.add(path)
    return asks


def _binary_value_on(step: dict) -> str | None:
    """What the step sets GC_TEST_BIN to, or None if it does not set it.

    The value, never the presence of the name. `GC_TEST_BIN=""` mentions it,
    passes a presence check, and makes the fixture skip every test in the step
    while the step stays green -- which is the exact silence this file exists
    to break.
    """
    declared = (step.get("env") or {}).get("GC_TEST_BIN")
    if declared is not None:
        return str(declared)
    for line in _run_lines(step):
        match = re.search(r'GC_TEST_BIN=("[^"]*"|\'[^\']*\'|\S*)', line)
        if match:
            return match.group(1).strip("\"'")
    return None


def suites_run_with_a_gc_binary() -> set[Path]:
    covered: set[Path] = set()
    for step in _steps():
        value = _binary_value_on(step)
        if not value:
            continue
        targets = {path for line in _run_lines(step) for path in _paths_on(line)}
        covered |= {path for path in every_test_file() if not uncovered({path}, targets)}
    return covered


def test_every_test_file_in_the_tree_is_collected_by_ci() -> None:
    files = every_test_file()
    assert files, "the derivation found no test files at all, which is the "\
                  "instrument failing rather than the repository being empty"

    missing = sorted(str(path) for path in uncovered(files, pytest_targets_in_ci()))
    assert not missing, (
        "no CI step collects these test files: "
        + ", ".join(missing)
        + f" -- name them, or a directory above them, in the pytest step in "
        f"{CI.relative_to(REPO)}"
    )


@pytest.mark.parametrize("targets,expected", [
    (set(), {Path("some-pack/tests/test_a.py")}),
    ({Path("some-pack/tests")}, set()),
    ({Path("some-pack")}, set()),
    ({Path("some-pack/tests/test_a.py")}, set()),
    ({Path("other-pack")}, {Path("some-pack/tests/test_a.py")}),
    ({Path("some-pack/tests/test_a.py.bak")}, {Path("some-pack/tests/test_a.py")}),
])
def test_the_coverage_rule_reports_a_file_no_target_collects(
    targets: set[Path], expected: set[Path]
) -> None:
    """The other rail, on inputs neither derivation produced.

    The previous version asserted that a made-up pack name was absent from both
    derived sets. That passes when both derivations return nothing, which is
    the false green it was written to detect. This calls the rule directly with
    a file that is covered, a file that is not, and the three shapes of target
    pytest accepts.
    """
    assert uncovered({Path("some-pack/tests/test_a.py")}, targets) == expected


def test_every_suite_that_needs_a_real_gc_declares_it() -> None:
    undeclared = sorted(
        str(path) for path in suites_that_ask_for_a_binary() - suites_needing_a_real_gc()
    )
    assert not undeclared, (
        "these files reach for a gc binary and do not declare it, so the check "
        f"below cannot see them: {', '.join(undeclared)} -- add "
        f"`{DECLARATION} = True` at module level"
    )


def test_every_live_gc_suite_is_run_with_a_gc_binary() -> None:
    needing = suites_needing_a_real_gc()
    assert needing, "the derivation found no live-gc suites, which is the "\
                    "instrument failing rather than the repository being empty"

    missing = sorted(str(path) for path in needing - suites_run_with_a_gc_binary())
    assert not missing, (
        "these suites need a real gc and no CI step gives them one, so they "
        "skip silently and their step still passes: " + ", ".join(missing)
    )
