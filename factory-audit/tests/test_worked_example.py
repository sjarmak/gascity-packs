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
