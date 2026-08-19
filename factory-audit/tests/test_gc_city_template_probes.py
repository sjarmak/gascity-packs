"""The gc-city probe template, checked against the two ways it went quiet.

Neither defect here is an error state. A probe pack that stops matching the
call sites it was written for reports a SMALLER number, and a smaller number
reads like progress. So both are pinned as properties of the template file
rather than left to be noticed in a report nobody diffs.

The checker is not involved. What is under test is the template's own regexes
and globs, evaluated with the same two primitives the checker evaluates them
with: `re.search` for a matcher, and `fnmatch` with "**/" allowed to match zero
segments for a path glob (src/infer.py::_matches_any). Re-implementing those
two lines here is the point: a test that imported the checker could not run in
a city that has not installed one, and these are the semantics the template is
written against.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
import re

import pytest
import yaml


TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "gc-city-probes.yaml"

# The line this template could not see. Verbatim from the wrapper every Slack
# send in the city the template was written against goes through.
WRAPPER_LINE = '"$GC_BIN" slack publish-to-channel "${ARGS[@]}"'

# What the template carried before, kept as the control. If this ever starts
# matching WRAPPER_LINE the fix below has stopped being load-bearing and these
# tests are passing for another reason.
FORMER_MATCHER = "gc slack publish-to-channel"


def template() -> dict:
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))


def effect(name: str) -> dict:
    for item in template()["effects"]:
        if item["name"] == name:
            return item
    raise AssertionError(f"the template declares no effect {name}")


def scripted_shell_matchers(name: str) -> list[dict]:
    matchers = effect(name)["call_site"]["scripted"]["any_of"]
    return [m for m in matchers if "shell" in (m.get("languages") or ["shell"])]


def first_match(line: str, matchers: list[dict]):
    """The match the checker would take: first matcher that hits, in order."""
    for matcher in matchers:
        found = re.search(matcher["regex"], line)
        if found:
            return found
    return None


def inside_a_string(line: str, pos: int) -> bool:
    """The checker's quoting walk (src/infer.py::set_aside_reason), shell rules.

    A match starting inside an open quote is a mention, not an invocation, and
    is set aside. That rule is correct and this template has to be written so
    that a real call does not trip it.
    """
    quote, i = None, 0
    while i < pos and i < len(line):
        char = line[i]
        if quote is None:
            if char in "'\"":
                quote = char
            elif char == "\\":
                i += 1
        elif char == quote:
            quote = None
        elif quote == '"' and char == "\\":
            i += 1
        i += 1
    return quote is not None


def matches_any(rel: str, globs: list[str]) -> bool:
    for glob in globs:
        if fnmatch.fnmatch(rel, glob):
            return True
        if "**/" in glob and fnmatch.fnmatch(rel, glob.replace("**/", "")):
            return True
    return False


def test_the_slack_matcher_sees_a_wrapper_that_resolves_its_own_binary() -> None:
    assert first_match(WRAPPER_LINE, scripted_shell_matchers("slack_publish"))


def test_the_matcher_this_replaced_is_the_reason_it_had_to_change() -> None:
    # The control for the test above. Naming the binary literally is what took
    # the scripted count for this effect to zero while it was performed daily.
    assert re.search(FORMER_MATCHER, WRAPPER_LINE) is None


def test_a_wrapper_call_is_not_set_aside_as_a_quoted_mention() -> None:
    # The second half, and the one that is easy to get wrong while fixing the
    # first: matching on `$GC_BIN` puts the match start INSIDE the opening
    # quote, and every wrapper line is then discarded as a mention. Anchoring on
    # the verb lands the match after the quote has closed.
    found = first_match(WRAPPER_LINE, scripted_shell_matchers("slack_publish"))
    assert found is not None
    assert not inside_a_string(WRAPPER_LINE, found.start())


def test_a_genuinely_quoted_mention_is_still_set_aside() -> None:
    # The other rail. A matcher loose enough to read every echoed command as a
    # call site would pass the test above and be worse than what it replaced.
    line = 'echo "run gc slack publish-to-channel --channel ops"'
    found = first_match(line, scripted_shell_matchers("slack_publish"))
    assert found is not None
    assert inside_a_string(line, found.start())


def test_harness_globs_reach_tests_outside_bin() -> None:
    globs = template()["harness_globs"]
    for rel in (
        "assets/scripts/prune-branches.test",
        "hooks/pre-publish.test",
        "bin/slack-publish-fenced.test",
        "bin/test_messaging_state_reconciler_cli.py",
    ):
        assert matches_any(rel, globs), rel


def test_harness_globs_do_not_swallow_the_scripts_themselves() -> None:
    globs = template()["harness_globs"]
    for rel in (
        "bin/slack-publish-fenced",
        "assets/scripts/prune-branches.sh",
        "hooks/post-claim",
    ):
        assert not matches_any(rel, globs), rel


def test_the_template_still_names_no_city() -> None:
    # It is shipped to be copied. A real factory_name here would be someone
    # else's city name in every reader's first derivation.
    assert template()["factory_name"] == "my-gas-city"


@pytest.mark.parametrize(
    "name",
    ["slack_publish", "git_push", "open_pull_request",
     "merge_pull_request", "agent_mail_nudge"],
)
def test_every_effect_shares_the_one_harness_list(name: str) -> None:
    # The YAML anchor is what keeps the fix above from applying to one effect
    # and not the rest. Resolved by the loader, so this reads the merged value.
    assert effect(name)["call_site"]["harness_globs"] == template()["harness_globs"]
