"""What a pack tells a user to type, read back from a real `gc` that ran it.

A pack command is reached as `gc <binding> <verbs...>`, where the binding is the
key the city wrote under `[imports.<name>]`. It is the city's choice, not the
pack's: `[imports.fa] source = ".../factory-audit"` makes the pack answer to
`fa`. Gas City hands a command `GC_PACK_NAME`, which is the PACK's name, and
supplies nothing carrying the binding -- measured against the binary with a
scrubbed environment, the whole `GC_*` set a command receives is `GC_BIN`,
`GC_CITY`, `GC_CITY_NAME`, `GC_CITY_PATH`, `GC_CITY_RUNTIME_DIR`, `GC_PACK_DIR`,
`GC_PACK_NAME`, `GC_PACK_STATE_DIR`.

So a pack that prints `Run: gc factory setup`, or that reaches for
`GC_PACK_NAME` to build the instruction, is right on exactly one installation:
the one where the operator happened to bind the pack under its own name. That is
the author's own city, every time, which is why this class of defect cannot be
found by testing there. `factory-audit` shipped it at seven sites.

The suite therefore binds every pack under a name that is not its own and reads
what the pack says to type. Nothing else in this repository executes a pack
command: the rest of the live-gc coverage asks `gc` to LIST surfaces, and an
instruction is only produced by running the thing.

Executing is not free, which is why the commands are declared by each pack in
`tests/live-gc-safe-commands.txt` rather than derived from `commands/`. Whether
running a command posts to Slack, pushes a branch, or opens a pull request is
not a property of the directory tree, and inferring it wrongly means this suite
performs the effect. That is the one place in this harness where hand-writing is
the correct answer: a human decides an effect is safe to perform, and the file
is checked against the tree so it cannot name a command the pack does not ship.
"""

from __future__ import annotations

from pathlib import Path
import re
import textwrap

import pytest

from gc_live_city import (
    REPO_ROOT,
    discover_command_words,
    gc_test_bin,  # noqa: F401 -- pytest fixture, used by name
    read_pack_manifest,
    run_gc,
    write_city,
)
from test_maintained_packs_live_gc import MAINTAINED_PACKS, pack_dir, wiring


REQUIRES_GC_BINARY = True

# Deliberately not any pack's name, and not a word any pack ships as a verb.
# The whole method is that the binding and the pack name disagree, so a pack
# reaching for its own name to build an instruction says something wrong here
# and cannot say something wrong in a city that binds it under its own name.
BINDING = "bound-elsewhere"

DECLARATION = Path("tests") / "live-gc-safe-commands.txt"

# `gc foo`, `` `gc foo bar` ``, `gc <binding> foo`. The first word after `gc`
# is the one that has to be the binding; the second is read only to tell an
# instruction apart from prose.
WORD = r"[A-Za-z0-9_.<>-]+"
INSTRUCTION = re.compile(rf"\bgc\s+({WORD})(?:\s+({WORD}))?")

# `  doctor          Check workspace health`, under `Available Commands:`.
HELP_COMMAND = re.compile(r"^ {2}(\S+) {2,}\S")


def safe_commands(pack: str) -> list[tuple[str, ...]]:
    """Command word-paths a pack has declared safe to execute in a scratch city.

    Blank lines and `#` comments are ignored so the file can carry the reason a
    command is on it, or the reason one is missing.
    """
    path = pack_dir(pack) / DECLARATION
    if not path.is_file():
        return []
    declared = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            declared.append(tuple(line.split()))
    return declared


def gc_builtins(gc_test_bin: Path, workspace) -> set[str]:
    """Top-level commands this `gc` offers, read from its own help.

    Needed because a pack's output is prose as well as instructions, and packs
    legitimately tell a user to run `gc session list` or `gc doctor`. Read from
    the running binary rather than listed here, so a command gc adds or drops
    does not turn into a finding about a pack.
    """
    result = run_gc(gc_test_bin, workspace, "--help")
    output = result.stdout + result.stderr
    lines = output.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("Available Commands:"))
    except StopIteration:  # pragma: no cover - a gc that changed its help shape
        raise AssertionError(
            "gc --help has no `Available Commands:` section, so this file "
            f"cannot tell a builtin from a pack binding. Output:\n{output}"
        )
    builtins = set()
    for line in lines[start + 1:]:
        if not line.strip():
            break
        match = HELP_COMMAND.match(line)
        if match:
            builtins.add(match.group(1))
    # Bounded on both sides, because this set only ever SUPPRESSES findings.
    # Parse too little and every `gc doctor` in a pack's prose becomes a
    # finding; parse too much and a real misdirected instruction is swallowed
    # and this whole file goes quietly green. Measured on this binary: the
    # column parse yields 63 commands, and a parse that took whole lines
    # instead yields 236 words. The band separates those with room for gc to
    # grow, and is what fails when the help layout changes shape.
    assert 10 < len(builtins) < 150, (
        f"gc --help parsed to {len(builtins)} commands, which is outside the "
        "range this parse produces on a working binary. Below the band, every "
        "builtin a pack names reads as a finding; above it, the descriptions "
        f"are being read as command names and real findings are suppressed. "
        f"Parsed: {sorted(builtins)}"
    )
    return builtins


def misdirected(output: str, pack: str, shipped: set[str], builtins: set[str]) -> set[str]:
    """First words in `gc <word> ...` that are not the binding this city chose.

    Pure, so both rails can be exercised on inputs of this file's choosing
    rather than only on whatever the packs happen to print today.

    Three shapes are wrong, and each was found in a real pack:

    * the word is one of the pack's OWN command words, so the binding is
      missing entirely -- `gc factory setup`, which factory-audit printed at
      seven sites;
    * the word is the pack's name or the README's `<binding>` placeholder --
      right only in a city that bound the pack under its own name, or an
      admission that the pack could not work the binding out;
    * the word is followed by one of the pack's command words, so it sits
      where the binding belongs whatever it is -- `gc slack peers`, which
      slack-full writes 95 times and which is wrong in any city that does not
      bind it as `slack`.

    Everything else is left alone: a gc builtin (`gc doctor`, `gc session
    list`) because packs rightly name those, and any other word because
    `a running gc does ...` is prose, not an instruction.
    """
    wrong = set()
    for first, second in INSTRUCTION.findall(output):
        if first == BINDING or first in builtins:
            continue
        if first in shipped or first in {pack, "<binding>"} or (second and second in shipped):
            wrong.add(first)
    return wrong


def run_declared(gc_test_bin: Path, workspace, verbs: tuple[str, ...]) -> str:
    """A declared command's whole output, whatever it exits with.

    The exit status is not asserted on: these commands are being run in a city
    that has none of what they need, so the instruction under test is usually
    printed on the failure path. That is the path a new user meets first.
    """
    result = run_gc(gc_test_bin, workspace, BINDING, *verbs)
    return result.stdout + result.stderr


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_declared_safe_commands_are_commands_the_pack_ships(pack: str) -> None:
    """A declaration naming a command that no longer exists tests nothing.

    Checked separately from the run below so a stale line fails as a stale
    line, rather than as `gc` reporting an unknown command.
    """
    declared = set(safe_commands(pack))
    if not declared:
        pytest.skip(f"{pack} declares no safe commands")

    shipped = discover_command_words(pack_dir(pack))
    unknown = declared - shipped
    assert not unknown, (
        f"{pack}/{DECLARATION} names command(s) the pack does not ship: "
        + ", ".join(" ".join(words) for words in sorted(unknown))
        + f". It ships: " + ", ".join(sorted(" ".join(w) for w in shipped))
    )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_a_packs_instructions_name_the_binding_the_city_chose(
    pack: str, tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    declared = safe_commands(pack)
    if not declared:
        pytest.skip(
            f"{pack} declares no safe commands, so nothing here executes it; "
            f"add {DECLARATION} naming commands that are safe to run in a "
            f"scratch city to bring it under this check"
        )

    _, rig_imports = wiring(pack)
    workspace = write_city(
        tmp_path,
        {BINDING: pack_dir(pack)},
        {BINDING: pack_dir(pack)} if rig_imports else {},
    )
    shipped = {word for words in discover_command_words(pack_dir(pack)) for word in words}
    builtins = gc_builtins(gc_test_bin, workspace)

    for verbs in declared:
        output = run_declared(gc_test_bin, workspace, verbs)
        printed = INSTRUCTION.findall(output)
        assert printed, (
            f"gc {BINDING} {' '.join(verbs)} printed no `gc ...` instruction at "
            f"all, so listing it in {DECLARATION} asserts nothing. Either it "
            f"belongs off the list or it stopped telling the user what to run.\n"
            f"Output:\n{output}"
        )
        wrong = misdirected(output, pack, shipped, builtins)
        assert not wrong, (
            f"gc {BINDING} {' '.join(verbs)} told the user to run a command "
            f"that does not exist in this city: `gc {sorted(wrong)[0]} ...`. "
            f"The city bound this pack as `{BINDING}`, so every instruction has "
            f"to name that. GC_PACK_NAME is the pack's name and not the "
            f"binding; read the binding out of the city's pack.toml.\n"
            f"Output:\n{output}"
        )


# The pack in this table ships `factory audit` and `factory setup`, so its
# words are {factory, audit, setup}; `doctor` and `session` stand in for gc's
# own commands. Every wrong row is a shape found in a pack in this repository.
SHIPPED = {"factory", "audit", "setup"}
BUILTINS = {"doctor", "session", BINDING}


@pytest.mark.parametrize(
    "output,expected",
    [
        (f"Run: gc {BINDING} factory setup", set()),
        # factory-audit, seven sites, fixed in the same branch as this file.
        ("Run: gc factory setup", {"factory"}),
        # The same bug reached for through GC_PACK_NAME.
        ("Run: gc factory-audit factory setup", {"factory-audit"}),
        # A pack that could not resolve the binding and said so.
        ("Run: gc <binding> factory setup", {"<binding>"}),
        # slack-full, 95 times: a conventional binding hardcoded. `slack` is
        # not the pack name and not one of its verbs, and it is still wrong.
        ("Run: gc slack audit", {"slack"}),
        # Packs rightly name gc's own commands.
        ("first run gc doctor, then gc session list", set()),
        ("this is what a running gc does", set()),
        (f"gc {BINDING} factory setup, or gc factory setup", {"factory"}),
    ],
)
def test_the_rule_flags_a_misdirected_instruction_and_leaves_prose_alone(
    output: str, expected: set[str]
) -> None:
    assert misdirected(output, "factory-audit", SHIPPED, BUILTINS) == expected


def write_instruction_canary(root: Path) -> Path:
    """A pack that prints one right instruction and one wrong one, on purpose.

    The control for the live path. The parametrized rule above is exercised on
    strings this file wrote; this one goes through a city, the binary, and the
    pack's own script, which is where a green would otherwise be produced by
    the command never running, `gc` swallowing its output, or the binding
    never differing from the name.
    """
    pack = root / "instruction-canary"
    for verb, line in (
        ("right", f"  Run:  gc {BINDING} hint wrong"),
        ("wrong", "  Run:  gc hint right"),
    ):
        leaf = pack / "commands" / "hint" / verb
        leaf.mkdir(parents=True)
        leaf.joinpath("run.sh").write_text(
            f"#!/usr/bin/env bash\nprintf '%s\\n' {line!r}\n", encoding="utf-8"
        )
        leaf.joinpath("run.sh").chmod(0o755)
    pack.joinpath("pack.toml").write_text(
        textwrap.dedent(
            """\
            [pack]
            name = "instruction-canary"
            schema = 2
            """
        ),
        encoding="utf-8",
    )
    return pack


def test_a_wrong_instruction_is_caught_when_it_comes_through_gc(
    tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    canary = write_instruction_canary(tmp_path / "fixture")
    workspace = write_city(tmp_path / "city", {BINDING: canary})
    shipped = {"hint", "right", "wrong"}
    builtins = gc_builtins(gc_test_bin, workspace)

    right = run_declared(gc_test_bin, workspace, ("hint", "right"))
    assert INSTRUCTION.findall(right), (
        "the canary's correct command printed no instruction, so this control "
        f"proves nothing about the run path. Output:\n{right}"
    )
    assert misdirected(right, "instruction-canary", shipped, builtins) == set(), (
        f"the canary's correct instruction was flagged. Output:\n{right}"
    )

    wrong = run_declared(gc_test_bin, workspace, ("hint", "wrong"))
    assert misdirected(wrong, "instruction-canary", shipped, builtins) == {"hint"}, (
        "a command naming a top-level verb where the binding belongs was not "
        f"flagged, so every green in this file holds vacuously. Output:\n{wrong}"
    )


def test_at_least_one_maintained_pack_is_actually_executed() -> None:
    """Every test above skips a pack that declares nothing.

    All seven skipping is indistinguishable, in a CI log, from all seven
    passing -- pytest prints `s` and the step stays green. This is the line
    that goes red if the declarations are ever all removed.
    """
    declaring = [pack for pack in MAINTAINED_PACKS if safe_commands(pack)]
    assert declaring, (
        "no maintained pack declares a safe command, so nothing in this file "
        "executes anything and every result in it is a skip"
    )


def test_the_packs_under_test_are_the_packs_this_repository_holds() -> None:
    """MAINTAINED_PACKS is a policy list; this only checks it names real packs."""
    for pack in MAINTAINED_PACKS:
        assert read_pack_manifest(pack_dir(pack)).get("pack", {}).get("name"), (
            f"{pack} has no [pack] name in {REPO_ROOT / pack / 'pack.toml'}"
        )
