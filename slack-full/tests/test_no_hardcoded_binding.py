"""No runtime string in the python layer may hardcode this city's import name.

The live-gc suite (`tests/test_pack_instructions_live_gc.py`) is the stronger
check where it reaches: it binds the pack under a name that is not its own,
runs the real `gc`, and reads what actually came out. It reaches the failure
paths a command takes with no arguments, which is most of them and not all of
them. Three of the worst sites in this pack are past that point:

  * the `<system-reminder>` `bind-room` sends to every newly bound agent, which
    only renders after a successful bind against a live Slack workspace;
  * `publish` and `upload`'s "session has no binding" remedy, which needs a
    session that exists and has no binding;
  * `delegate`'s two "a sibling is still pending" remedies, which need a
    partially completed peer fanout.

Those are exactly the sites where being wrong costs the most. The bind-room one
is read by an autonomous agent that will run what it says. So this test covers
the source instead of the output: every string literal that is not a docstring,
across the pack's python layer, is checked for a hardcoded `gc slack`.

`slack` is this city's `[imports.slack]` key (and the reason the defect was
invisible here); the pack's own name is `slack-full`. A hit is not
necessarily wrong -- but it is a claim about someone else's city, so the
allowance is written down per site rather than assumed.

Comments and docstrings are documentation for whoever opens the file, not
instructions a user is handed, and are out of scope by design -- an AST walk
sees docstrings and never sees comments, which is why the check is an AST walk
and not a grep.
"""

import ast
import pathlib

import pytest

PACK = pathlib.Path(__file__).resolve().parent.parent

# Sites where a literal `gc slack` is correct. Empty, and it should stay that
# way; an entry here is a promise that the string is never shown to a user.
ALLOWED: dict[str, set[int]] = {}


def _docstrings(tree: ast.AST) -> set[int]:
    """Ids of the string nodes python treats as docstrings."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                found.add(id(body[0].value))
    return found


def _sources() -> list[pathlib.Path]:
    files = sorted(PACK.joinpath("scripts").glob("*.py"))
    files += sorted(PACK.joinpath("assets", "scripts").glob("*.py"))
    assert files, "no python layer found -- the test is pointing at nothing"
    return files


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.name)
def test_no_runtime_string_hardcodes_the_binding(path: pathlib.Path) -> None:
    tree = ast.parse(path.read_text(), filename=str(path))
    docs = _docstrings(tree)
    allowed = ALLOWED.get(path.name, set())
    hits = sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "gc slack" in node.value
        and id(node) not in docs
        and node.lineno not in allowed
    )
    assert not hits, (
        f"{path.name} hardcodes `gc slack` in a runtime string at "
        f"line(s) {hits}. Build the instruction with "
        f"`common.command_prog('<verb>')` instead, or record the line in "
        f"ALLOWED with a reason.")


def test_the_check_can_go_red() -> None:
    """A guard nobody has seen fail is not evidence of anything.

    Both rails on a synthetic file: the same instruction in a docstring is
    ignored, and in a runtime string is caught.
    """
    tree = ast.parse('"""Run gc slack publish."""\nx = "Run gc slack publish."\n')
    docs = _docstrings(tree)
    hits = [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and "gc slack" in n.value and id(n) not in docs]
    assert hits == [2]
