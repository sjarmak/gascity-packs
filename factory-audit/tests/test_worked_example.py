"""The worked contract in examples/gc-city has to keep saying what it says.

It ships as a failing example on purpose: a contract with the decisions filled
in, from the city this pack was written against, with its nine failures left
where they are. That is only useful while the file, its README and the reading
the checker gives it agree. Any one of the three can drift on its own.

Three checks, split by what they need:

  - the scrub holds, and the example is a whole contract (no kit, no network)
  - the README's inventory matches the sidecar (no kit, no network)
  - the checker's reading matches the sidecar (needs an installed kit)

The third is the only one that can confirm the score, and it is the only one
that skips. The first two exist so that the common edits -- re-copying the
contract out of the city, clearing a failure, rewording the README -- are
caught on a machine with no kit at all, which is every machine until the kit
commits are published.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PACK = Path(__file__).resolve().parents[1]
EXAMPLE = PACK / "examples" / "gc-city" / "factory.yaml"
README = PACK / "examples" / "gc-city" / "README.md"
EXPECTED = PACK / "examples" / "gc-city" / "expected-findings.txt"

# Every field an effect block has to decide. A contract that omits one reads as
# a shorter file rather than as an incomplete one, so the omission is invisible
# in a diff of a 1,171-line document.
EFFECT_FIELDS = (
    "effect_identity",
    "retry_contract",
    "unknown_state_policy",
    "instructed_call_sites",
)


def expected_findings() -> set[str]:
    out = set()
    for line in EXPECTED.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line)
    assert out, f"{EXPECTED} declares no findings"
    return out


def test_the_example_carries_no_path_from_the_machine_it_came_from() -> None:
    """It was copied out of a live city, and it will be copied again.

    The substitution is done by hand each time, which is exactly the kind of
    step that gets most of the occurrences. This is not a general secret scan;
    it is a guard on the one class of string this file is known to contain.
    """
    text = EXAMPLE.read_text()
    bad = [
        line
        for line in text.splitlines()
        if re.search(r"(/home/|/Users/)[A-Za-z0-9._-]+/", line)
    ]
    assert not bad, "example holds absolute paths from a real machine:\n" + "\n".join(
        bad[:10]
    )


def test_every_effect_in_the_example_decides_every_field() -> None:
    """The example's whole claim is that it shows what a decided field is.

    An effect that omits one is not a smaller example, it is a misleading one:
    the reader who came here to see what `unknown_state_policy` looks like
    finds nothing and cannot tell that anything is missing.
    """
    doc = yaml.safe_load(EXAMPLE.read_text())
    effects = doc.get("effects") or []
    assert effects, "example declares no effects"
    for index, effect in enumerate(effects):
        for field in EFFECT_FIELDS:
            assert field in effect, (
                f"effects[{index}] ({effect.get('name', 'unnamed')}) omits "
                f"{field}; the example exists to show what that field holds"
            )


def test_the_readme_names_every_rule_the_example_actually_trips() -> None:
    """A rule that stops being mentioned is how the README goes quietly stale.

    Checked in both directions. A rule in the sidecar and not in the README is
    a failure the reader is never told about; a rule the README explains and
    the example no longer trips is advice about a file that has moved on.
    """
    prose = README.read_text()
    in_sidecar = {line.split()[1] for line in expected_findings()}
    mentioned = set(re.findall(r"\b[A-Z]+-\d{3}\b", prose))
    assert in_sidecar <= mentioned, (
        f"README never mentions {sorted(in_sidecar - mentioned)}"
    )
    assert mentioned <= in_sidecar, (
        f"README explains {sorted(mentioned - in_sidecar)}, which the example "
        f"no longer trips"
    )


def test_the_readme_states_the_same_totals_as_the_sidecar() -> None:
    """The headline number is the one thing every reader takes away."""
    findings = expected_findings()
    fails = sum(1 for f in findings if f.startswith("FAIL "))
    warns = sum(1 for f in findings if f.startswith("WARN "))
    stated = f"`{fails} FAIL, {warns} WARN`"
    assert stated in README.read_text(), (
        f"README does not state {stated}; the sidecar holds {fails} FAIL and "
        f"{warns} WARN"
    )


def kit_home() -> Path | None:
    override = os.environ.get("FACTORY_KIT_HOME")
    if override and (Path(override) / "src" / "factory_check.py").exists():
        return Path(override)
    return None


def test_the_checker_reads_the_example_the_way_the_sidecar_says(tmp_path: Path) -> None:
    """Set equality, so a finding that disappears fails too.

    Emptiness would not do. Work that clears one of these failures has to
    delete its line here in the same change; otherwise a fixed contract and a
    checker that stopped reporting are the same reading.
    """
    kit = kit_home()
    if kit is None:
        pytest.skip(
            "set FACTORY_KIT_HOME to a checkout of the reliability kit to "
            "confirm the example's score; the pin is not fetchable until the "
            "kit commits are published"
        )
    # tmp_path, not a fixed directory. A fixed one survives the run, so a
    # review that failed to write would be read from the previous run's output
    # and the test would confirm a reading nothing produced.
    out = tmp_path / "findings"
    result = subprocess.run(
        [sys.executable, "-m", "src.factory_check", "review", str(EXAMPLE),
         "--out", str(out)],
        cwd=kit,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode in (0, 1), result.stderr[:500]
    produced = {
        f'{f["severity"]} {f["rule"]} {f["path"]}'
        for f in json.loads((out / "findings.json").read_text())
    }
    assert produced == expected_findings(), (
        f"new: {sorted(produced - expected_findings())}\n"
        f"gone: {sorted(expected_findings() - produced)}"
    )


def test_both_pages_state_the_example_length_the_example_actually_has() -> None:
    """Two pages quote it, and the file gets re-copied out of a live city.

    A stale line count is small and it is the visible half of a re-copy that
    also silently changed what the example says. Cheaper to pin than to
    remember, and the failure names both pages.
    """
    lines = len(EXAMPLE.read_text().splitlines())
    stated = f"{lines:,}"
    for page in (README, PACK / "README.md"):
        text = page.read_text()
        assert f"{stated} lines" in text, (
            f"{page.name} does not say '{stated} lines'; the example has "
            f"{lines}"
        )


def test_the_dead_mechanism_warning_and_the_contract_agree() -> None:
    """Half of the README's sharpest claim, and it is worth saying which half.

    The claim is that a DECIDED field can name a mechanism nothing runs. This
    binds the decided half only: set `lease_expiry` to `unknown` and the rule
    starts failing on it, at which point the paragraph describes a green line
    that is no longer green and the example teaches the opposite of what it
    says. The dead half is a measurement of a running store, recorded in the
    contract's comments with the query beside it, and no test in this pack can
    re-take it, because the pack ships without the store. The test below binds
    the reading the checker gives, which is the other thing that can drift.

    Runs with no kit and no network: the edit it guards against is one
    keystroke, and every other check of this claim needs an installed checker.
    """
    # Asserted, not skipped over. A skip here would quietly retire the whole
    # check the moment someone reworded the heading, which is the one edit most
    # likely to happen to it.
    pack_readme = (PACK / "README.md").read_text()
    assert "A decided field is not a live mechanism" in pack_readme, (
        "the pack README no longer carries the decided-but-dead section; the "
        "example README's own section points at it by that name"
    )

    ownership = yaml.safe_load(EXAMPLE.read_text())["work"]["ownership"]
    lease = str(ownership.get("lease_expiry", "")).strip()
    assert lease and lease.lower() not in {"unknown", "none", "tbd"}, (
        f"lease_expiry reads {lease!r}. Both READMEs argue from a field that "
        f"is decided and whose mechanism is dead; an undecided field fails the "
        f"rule outright and makes that argument false."
    )
    # The heading, not a bare mention of the field. `lease_expiry` also appears
    # in the failure table above that section, so a mention proves nothing
    # about the section still being there.
    assert "A field that passes, over a mechanism that does not run" in (
        README.read_text()
    ), "the example README lost the section that argues this case"


def test_auth_001_is_red_for_the_generation_and_not_for_the_lease(
    tmp_path: Path,
) -> None:
    """Which half of AUTH-001 fails is the whole point of that section.

    Both READMEs say this rule is red for the claim generation and that
    clearing it would turn the rule green over a lease almost nothing takes. If
    the checker is in fact failing on the lease, that reading is wrong and the
    advice inverts: clearing the generation would leave the rule red and nobody
    would learn anything from it.
    """
    kit = kit_home()
    if kit is None:
        pytest.skip(
            "set FACTORY_KIT_HOME to a checkout of the reliability kit to "
            "confirm which half of AUTH-001 is failing"
        )
    out = tmp_path / "findings"
    result = subprocess.run(
        [sys.executable, "-m", "src.factory_check", "review", str(EXAMPLE),
         "--out", str(out)],
        cwd=kit,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode in (0, 1), result.stderr[:500]
    findings = json.loads((out / "findings.json").read_text())
    ownership = [
        f for f in findings
        if f["rule"] == "AUTH-001" and f["path"] == "work.ownership"
    ]
    assert len(ownership) == 1, findings
    # Set equality over the field names the rule can list, not an absence
    # check. `lease_expiry not in message` would also pass if the wording
    # changed so that neither name appeared, which is a rule this test no
    # longer understands rather than a rule that agrees with the README.
    message = ownership[0]["message"]
    named = {n for n in ("generation", "lease_expiry") if n in message}
    assert named == {"generation"}, (
        f"AUTH-001 reads {message!r}. Both READMEs claim this rule is red for "
        f"the generation and that the lease half passes. An empty set here "
        f"means the rule stopped naming its undecided fields and this test "
        f"can no longer tell the two apart."
    )


GUIDE = PACK / "examples" / "gc-city" / "deciding-a-field.md"


def _section(heading: str, doc: str | None = None) -> str:
    """One `## ` section of the guide, by heading.

    Every check below reads a table, and a table is only meaningful inside the
    section that introduces it. Matching by shape across the whole file means a
    second table added later silently joins the data of the first, which is a
    drift the test would then report as agreement.
    """
    text = doc if doc is not None else GUIDE.read_text()
    assert text.count(heading) == 1, f"{heading!r} is not a unique heading"
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def _rows(section: str, width: int) -> list[list[str]]:
    """Table rows of exactly `width` cells, header and separator dropped."""
    out = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if len(cells) == width and cells[0] and not set(cells[0]) <= {"-", ":"}:
            out.append(cells)
    return out


def _guide_table() -> dict[str, tuple[str, str]]:
    """The guide's closing table, as {effect: (retry_contract, policy)}.

    Parsed rather than hardcoded here, so the test compares two files that can
    each move instead of comparing one file against a copy of itself.
    """
    rows = _rows(_section("## Our five answers, as a table"), 3)
    return {r[0]: (r[1], r[2]) for r in rows if r[0] != "Effect"}


def test_the_guide_states_the_answers_the_contract_actually_holds() -> None:
    """The guide argues from our five effects; the contract is where they live.

    This is the edit most likely to happen and least likely to be noticed:
    changing a decision in the contract, which is a real change to what we
    claim, and leaving the prose that explains it saying the old thing. Runs
    with no kit and no network, because both files ship in this pack.
    """
    contract = yaml.safe_load(EXAMPLE.read_text())
    actual = {
        e["name"]: (str(e.get("retry_contract")), str(e.get("unknown_state_policy")))
        for e in contract["effects"]
    }
    stated = _guide_table()
    assert stated, f"no table rows parsed out of {GUIDE.name}"
    assert stated == actual, (
        f"the guide's table and the contract disagree.\n"
        f"guide:    {sorted(stated.items())}\n"
        f"contract: {sorted(actual.items())}"
    )


def test_the_guide_lists_the_retry_contracts_the_checker_accepts() -> None:
    """A guide that names a value the rules reject teaches a failing edit.

    The four retry contracts are an enum in the rules, and the guide prints
    them as a table a reader chooses from. If the enum gains or loses a value,
    this is the file that has to move with it.
    """
    kit = kit_home()
    if kit is None:
        pytest.skip(
            "set FACTORY_KIT_HOME to a checkout of the reliability kit to "
            "compare the guide's value list against the rules"
        )
    sys.path.insert(0, str(kit))
    try:
        from src import rules  # noqa: PLC0415
    finally:
        sys.path.pop(0)

    # The table's first column, not every backticked token in the section. A
    # token scan passes on a section whose table has been deleted as long as
    # the prose still happens to name all four values, which is the one edit
    # this test exists to catch.
    section = _section("## `retry_contract`")
    listed = {r[0] for r in _rows(section, 2) if r[0] != "Value"}
    assert listed == rules.ALLOWED_RETRY_CONTRACTS, (
        f"the guide lists {sorted(listed)}; the rules accept "
        f"{sorted(rules.ALLOWED_RETRY_CONTRACTS)}"
    )
