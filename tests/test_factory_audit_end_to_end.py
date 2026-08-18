"""factory-audit driven the way a user drives it: through a real `gc`.

The pack's own suite runs the wrapper scripts directly, and the shared live-gc
suite asks `gc <binding> factory --help` whether the verbs are listed. Neither
one runs the chain. A pack test that never invokes `gc` measures the pack's
TOML, and `--help` listing a verb is not evidence that invoking it reaches
anything: gc could hand the script a different environment, swallow its exit
status, or resolve the pack directory somewhere else, and every assertion in
both suites would stay green.

So this stands the pack up in a scratch city and drives it end to end. The kit
is a stub, deliberately: whether the checker's findings are right is the kit's
own suite's question. What is asked here is whether gc reaches it, hands it the
city it claims to, and reports back what it said -- including the failure,
which is the direction a wrapper is most likely to lose.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from gc_live_city import (  # noqa: F401  (fixture import)
    REPO_ROOT,
    Workspace,
    gc_test_bin,
    write_city,
)

# This suite cannot do its job without a real gc binary: without one its
# fixture skips, the step stays green, and the output says `s` where it would
# have said `F`. Declared rather than inferred, so the CI-coverage guard in
# tests/test_ci_runs_every_pack_suite.py can see it whatever route it takes to
# ask for a binary.
REQUIRES_GC_BINARY = True

BINDING = "factory-audit"

# The stub records what it was asked to do and then does the smallest thing the
# wrapper promises the user. `--exit` lets a single fixture play both the clean
# run and the drift, so the failure path is exercised by the same code that
# proves the success path works.
# The counts line the stub ends a reconcile with when FACTORY_STUB_DRIFT is
# set. Named because two tests assert on it: one that the wrapper wrote this
# run's report and not an appended one, and one that the receipt parsed it.
DRIFT_REPORT = "1 drift, 0 unverified, 2 confirmed, 0 open (of 3 declared)"

STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, sys

argv = sys.argv[1:]
log = pathlib.Path(os.environ["FACTORY_STUB_LOG"])
calls = json.loads(log.read_text()) if log.exists() else []
calls.append({"argv": argv, "cwd": os.getcwd()})
log.write_text(json.dumps(calls))

verb = argv[0] if argv else ""


def value(flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


if verb == "probes-init":
    pathlib.Path(value("--write")).write_text("factory_name: scratch\neffects: {}\n")
    print("scaffolded probes")
elif verb == "infer":
    pathlib.Path(value("--write")).write_text("factory_name: scratch\neffects: {}\n")
    pathlib.Path(value("--out"), "evidence.json").write_text("{}\n")
    print("inferred 0 effects")
elif verb == "reconcile":
    # The full counts line the real checker ends a reconcile with. The receipt
    # parses it, so an abbreviated stand-in reads as an unparsable report and
    # every state derived from it is ERRORED -- a stub that measures the stub.
    if os.environ.get("FACTORY_STUB_DRIFT"):
        print("1 drift, 0 unverified, 2 confirmed, 0 open (of 3 declared)")
    elif os.environ.get("FACTORY_STUB_VACUOUS"):
        print("0 drift, 0 unverified, 0 confirmed, 5 open (of 5 declared)")
    else:
        print("0 drift, 0 unverified, 3 confirmed, 0 open (of 3 declared)")
elif verb == "review":
    # `factory audit` runs the kit's `review`, not a verb named after itself.
    # This branch used to be spelled `audit` and was therefore dead: driving
    # audit through gc landed in the `else` below and exited 64, and no test
    # drove it, so both mistakes kept each other invisible.
    pathlib.Path(value("--out"), "findings.json").write_text("[]\n")
    print("0 FAIL, 0 WARN")
else:
    print("stub: unknown verb %s" % verb, file=sys.stderr)
    sys.exit(64)

# Per-verb override. The interesting state for the verification receipt needs a
# reconcile that found drift and an audit whose own rules pass, and one exit
# status for the whole stub cannot say that.
sys.exit(int(os.environ.get(
    "FACTORY_STUB_EXIT_" + verb.upper(),
    os.environ.get("FACTORY_STUB_EXIT", "0"))))
'''


@pytest.fixture
def city(tmp_path: Path) -> tuple[Workspace, Path, Path]:
    """A scratch city importing the pack, plus a stub kit it will resolve to."""
    kit = tmp_path / "kit"
    (kit / "src").mkdir(parents=True)
    checker = kit / "src" / "factory_check.py"
    checker.write_text(STUB)
    checker.chmod(0o755)

    workspace = write_city(tmp_path, {BINDING: REPO_ROOT / "factory-audit"})
    log = tmp_path / "stub-calls.json"
    return workspace, kit, log


def drive(
    gc_bin: Path,
    workspace: Workspace,
    kit: Path,
    log: Path,
    *args: str,
    **extra: str,
) -> subprocess.CompletedProcess[str]:
    env = {
        **workspace.env,
        "FACTORY_KIT_HOME": str(kit),
        "FACTORY_STUB_LOG": str(log),
        **extra,
    }
    return subprocess.run(
        [str(gc_bin), BINDING, *args],
        cwd=workspace.rig_dir,
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
    )


def calls(log: Path) -> list[dict]:
    return json.loads(log.read_text()) if log.exists() else []


def test_derive_through_gc_reaches_the_kit_and_writes_what_it_promises(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    workspace, kit, log = city

    result = drive(gc_test_bin, workspace, kit, log, "derive")
    assert result.returncode == 0, result.stdout + result.stderr

    # The whole argv of every call, in order. Checking the verb and the city
    # left every flag between them unasserted, and deleting `--probes` from the
    # infer call passed: the stub still wrote the files this test looks for,
    # while the real checker would have been scanning with no probe pack. A
    # wrapper's job here is entirely the argv it assembles, so that is the
    # thing to pin, including the city -- pointing it at the rig or at the
    # wrapper's own directory yields a clean report about the wrong tree, which
    # is the most expensive way for this pack to be wrong.
    out = workspace.city_dir / ".gc" / "factory-audit"
    probes = out / "probes.yaml"
    assert [c["argv"] for c in calls(log)] == [
        ["probes-init", str(workspace.city_dir), "--write", str(probes)],
        [
            "infer", str(workspace.city_dir),
            "--probes", str(probes),
            "--out", str(out),
            "--write", str(out / "factory.derived.yaml"),
        ],
    ], f"gc reached the kit with the wrong chain. Calls: {calls(log)}"

    for promised in ("probes.yaml", "factory.derived.yaml", "derived.txt", "evidence.json"):
        assert (out / promised).is_file(), (
            f"the command's closing message names {promised} and it is not there"
        )


def test_reconcile_through_gc_reports_the_kits_failure_rather_than_swallowing_it(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    """The direction that matters.

    Every layer here can turn a drift into a success: the wrapper pipes the
    kit through `tee`, and a shell reports the pipe's status, not the command's.
    The order that runs on a schedule is green when this exits zero, so a lost
    status is a check that has stopped checking while still printing findings.
    """
    workspace, kit, log = city
    assert drive(gc_test_bin, workspace, kit, log, "derive").returncode == 0

    contract = workspace.city_dir / ".gc" / "factory-audit" / "factory.yaml"
    contract.write_text("factory_name: scratch\neffects: {}\n")

    clean = drive(gc_test_bin, workspace, kit, log, "reconcile")
    assert clean.returncode == 0, clean.stdout + clean.stderr

    drifted = drive(
        gc_test_bin, workspace, kit, log, "reconcile",
        FACTORY_STUB_EXIT="1", FACTORY_STUB_DRIFT="1",
    )
    assert drifted.returncode == 1, (
        "the kit reported drift and exited 1; gc reported "
        f"{drifted.returncode}. Output:\n{drifted.stdout}{drifted.stderr}"
    )
    assert "1 drift" in drifted.stdout, drifted.stdout + drifted.stderr

    # Equality, not membership. Searching for the new finding leaves an
    # appending write undetected: switching the wrapper's `tee` to `tee -a`
    # keeps both reports in the file, and a reader who greps it for drift is
    # answered by a run that has been superseded.
    written = workspace.city_dir / ".gc" / "factory-audit" / "reconcile.txt"
    assert written.read_text().strip() == DRIFT_REPORT, (
        "the file the wrapper says it wrote does not hold exactly this run's "
        f"report. It holds:\n{written.read_text()}"
    )


@pytest.mark.parametrize("present,missing", [
    ("probes.yaml", "factory.yaml"),
    ("factory.yaml", "probes.yaml"),
])
def test_reconcile_before_derive_gives_an_instruction_not_a_traceback(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path,  # noqa: F811
    present: str, missing: str,
) -> None:
    """One prerequisite at a time, and the message names the absent one.

    With both absent the command cannot show which of the two it checks: the
    surviving check answers for both, so dropping either one from the wrapper
    leaves this green. Each case here supplies one file and asserts the error
    names the other.
    """
    workspace, kit, log = city
    out = workspace.city_dir / ".gc" / "factory-audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / present).write_text("factory_name: scratch\neffects: {}\n")

    result = drive(gc_test_bin, workspace, kit, log, "reconcile")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "gc factory-audit derive" in result.stderr
    assert missing in result.stderr, (
        f"{present} is present and {missing} is not; the error should name "
        f"{missing}. It said:\n{result.stderr}"
    )
    assert not calls(log), "the kit ran before its inputs existed"


def test_the_banner_names_the_override_when_one_is_in_use(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    """Through gc, not just through the script.

    `FACTORY_KIT_HOME` is how these tests reach a stub at all, which makes it
    the one variable most likely to be silently correct here and silently
    ignored in a real install. The banner is the only thing that can tell them
    apart, so it is read from gc's own output.
    """
    workspace, kit, log = city
    result = drive(gc_test_bin, workspace, kit, log, "derive")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DRIFT: FACTORY_KIT_HOME is set" in result.stdout, result.stdout
    assert "(pinned)" not in result.stdout


def test_the_override_warning_is_not_printed_when_there_is_no_override(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:

    """The other rail on the banner.

    A banner that always printed the override line would satisfy the test
    above, and would then be noise on every real install rather than the one
    piece of information that separates a pinned run from an operator's
    checkout. So the same stub is placed where the pack looks by default and
    the line has to be absent. It is still not `(pinned)`: the stub is not a
    checkout of the pinned commit, and the banner says so, which is the
    property that makes the pin a claim rather than a decoration.
    """
    workspace, kit, log = city
    default = workspace.city_dir / ".gc" / "factory-kit" / "src"
    default.mkdir(parents=True)
    checker = default / "factory_check.py"
    checker.write_text((kit / "src" / "factory_check.py").read_text())
    checker.chmod(0o755)

    env = {**workspace.env, "FACTORY_STUB_LOG": str(log)}
    result = subprocess.run(
        [str(gc_test_bin), BINDING, "derive"],
        cwd=workspace.rig_dir, env=env, text=True, capture_output=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FACTORY_KIT_HOME" not in result.stdout, (
        "no override is in use and the banner named one anyway:\n" + result.stdout
    )
    assert "(pinned)" not in result.stdout, result.stdout


def test_audit_through_gc_states_that_nothing_has_checked_its_score(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    """The score alone is a property of a document, and gc has to say so.

    The pack's own suite can prove the wrapper prints this line. It cannot
    prove a user meets it: gc resolves the pack directory, sets the city, and
    runs the script, and a wrapper whose banner is correct in isolation is
    worth nothing if the command a user types never reaches it.
    """
    workspace, kit, log = city
    assert drive(gc_test_bin, workspace, kit, log, "derive").returncode == 0
    out = workspace.city_dir / ".gc" / "factory-audit"
    (out / "factory.yaml").write_text("factory_name: scratch\neffects: {}\n")

    result = drive(gc_test_bin, workspace, kit, log, "audit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verification: NONE" in result.stdout, result.stdout
    assert "0 FAIL, 0 WARN" in result.stdout, (
        "the rule catalog did not run through gc, so the line above is a "
        f"banner over nothing:\n{result.stdout}{result.stderr}"
    )
    assert [c["argv"] for c in calls(log)][-1] == [
        "review", str(out / "factory.yaml"), "--out", str(out),
    ], f"gc reached the kit with the wrong audit call. Calls: {calls(log)}"


def test_audit_through_gc_refuses_a_clean_score_over_a_contradicted_contract(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    """The whole reason the receipt exists, driven the way a user drives it.

    Reconcile finds the installation contradicts the contract. Nothing changes
    the contract. The rule catalog then passes, because the rules read the
    document and the document is internally consistent -- it is simply not
    true. Before the receipt this printed `0 FAIL, 0 WARN` and exited 0, and
    that is the pair anyone would quote.
    """
    workspace, kit, log = city
    assert drive(gc_test_bin, workspace, kit, log, "derive").returncode == 0
    out = workspace.city_dir / ".gc" / "factory-audit"
    (out / "factory.yaml").write_text("factory_name: scratch\neffects: {}\n")

    drifted = drive(
        gc_test_bin, workspace, kit, log, "reconcile",
        FACTORY_STUB_EXIT="1", FACTORY_STUB_DRIFT="1",
    )
    assert drifted.returncode == 1, drifted.stdout + drifted.stderr
    assert (out / "reconcile.receipt").is_file(), (
        "reconcile through gc left no receipt, so the audit below has nothing "
        f"to read:\n{drifted.stdout}{drifted.stderr}"
    )

    result = drive(gc_test_bin, workspace, kit, log, "audit")
    assert "0 FAIL, 0 WARN" in result.stdout, (
        "the rules did not pass, so a nonzero exit here would not be the "
        f"finding under test:\n{result.stdout}{result.stderr}"
    )
    assert "verification: DRIFTED" in result.stdout, result.stdout
    assert result.returncode == 4, (
        "audit's rules passed over a contract gc had just reported as drifted "
        f"and it exited {result.returncode}:\n{result.stdout}{result.stderr}"
    )


def test_the_verification_state_reads_the_receipt_and_not_the_report_text(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    """The stub perturbation, not another revert of the fix.

    Here the kit PRINTS a drift line and exits 0. A wrapper that decided the
    verification state by grepping `reconcile.txt` would report DRIFTED and
    exit 4, and every other test in this file would stay green while the pack
    was coupled to a sentence in the checker's output -- a sentence the checker
    is free to rewrite, in a repository this pack only pins.
    """
    workspace, kit, log = city
    assert drive(gc_test_bin, workspace, kit, log, "derive").returncode == 0
    out = workspace.city_dir / ".gc" / "factory-audit"
    (out / "factory.yaml").write_text("factory_name: scratch\neffects: {}\n")

    clean = drive(
        gc_test_bin, workspace, kit, log, "reconcile",
        FACTORY_STUB_DRIFT="1",
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "1 drift" in clean.stdout, clean.stdout

    result = drive(gc_test_bin, workspace, kit, log, "audit")
    assert "verification: CONFIRMED" in result.stdout, result.stdout
    assert result.returncode == 0, result.stdout + result.stderr


def test_audit_through_gc_refuses_to_call_an_unchecked_contract_confirmed(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    """Reconcile exits 0 when nothing contradicts the contract.

    A contract that leaves every effect undecided has nothing for a probe to
    contradict, so the first reconcile anyone runs after `derive` exits 0 while
    confirming nothing. Read as a status alone that is CONFIRMED, which is this
    pack telling a newcomer their unchecked document has been checked. Driven
    through the real `gc` because the wrapper, the receipt and the state word
    are three layers and the defect lived in the seam between them.
    """
    workspace, kit, log = city
    assert drive(gc_test_bin, workspace, kit, log, "derive").returncode == 0
    out = workspace.city_dir / ".gc" / "factory-audit"
    (out / "factory.yaml").write_text("factory_name: scratch\neffects: {}\n")

    clean = drive(
        gc_test_bin, workspace, kit, log, "reconcile",
        FACTORY_STUB_VACUOUS="1",
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr

    result = drive(gc_test_bin, workspace, kit, log, "audit")
    assert "verification: VACUOUS" in result.stdout, result.stdout
    assert "CONFIRMED" not in result.stdout, result.stdout
    # A fresh contract is legitimately here, so it is not a failure by itself.
    assert result.returncode == 0, result.stdout + result.stderr

    strict = drive(gc_test_bin, workspace, kit, log, "audit", "--require-verified")
    assert strict.returncode == 4, strict.stdout + strict.stderr
