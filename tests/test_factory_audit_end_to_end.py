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

BINDING = "factory-audit"

# The stub records what it was asked to do and then does the smallest thing the
# wrapper promises the user. `--exit` lets a single fixture play both the clean
# run and the drift, so the failure path is exercised by the same code that
# proves the success path works.
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
    print("1 drift, 0 confirmed" if os.environ.get("FACTORY_STUB_DRIFT") else "0 drift")
elif verb == "audit":
    print("0 FAIL, 0 WARN")
else:
    print("stub: unknown verb %s" % verb, file=sys.stderr)
    sys.exit(64)

sys.exit(int(os.environ.get("FACTORY_STUB_EXIT", "0")))
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

    result = drive(gc_test_bin, workspace, kit, log, "factory", "derive")
    assert result.returncode == 0, result.stdout + result.stderr

    verbs = [c["argv"][0] for c in calls(log)]
    assert verbs == ["probes-init", "infer"], (
        "gc reached the kit with the wrong chain; a `--help` that lists the "
        f"verb would not have caught this. Calls: {calls(log)}"
    )

    # The city the kit was handed has to be the city gc is running in. Passing
    # the wrapper's own directory, or the rig, would produce a clean report
    # about the wrong tree -- the most expensive way for this pack to be wrong.
    #
    # Every call, not the first one. Checking only the scaffold step left the
    # step that actually produces the report free to scan somewhere else, and a
    # mutation pointing `infer` at $PWD passed against that weaker assertion.
    pointed_at = {Path(c["argv"][1]) for c in calls(log)}
    assert pointed_at == {workspace.city_dir}, (
        f"the kit was pointed at {sorted(map(str, pointed_at))}, and the city "
        f"is {workspace.city_dir}"
    )

    out = workspace.city_dir / ".gc" / "factory-audit"
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
    assert drive(gc_test_bin, workspace, kit, log, "factory", "derive").returncode == 0

    contract = workspace.city_dir / ".gc" / "factory-audit" / "factory.yaml"
    contract.write_text("factory_name: scratch\neffects: {}\n")

    clean = drive(gc_test_bin, workspace, kit, log, "factory", "reconcile")
    assert clean.returncode == 0, clean.stdout + clean.stderr

    drifted = drive(
        gc_test_bin, workspace, kit, log, "factory", "reconcile",
        FACTORY_STUB_EXIT="1", FACTORY_STUB_DRIFT="1",
    )
    assert drifted.returncode == 1, (
        "the kit reported drift and exited 1; gc reported "
        f"{drifted.returncode}. Output:\n{drifted.stdout}{drifted.stderr}"
    )
    assert "1 drift" in drifted.stdout, drifted.stdout + drifted.stderr

    written = workspace.city_dir / ".gc" / "factory-audit" / "reconcile.txt"
    assert "1 drift" in written.read_text(), (
        "the finding reached the terminal but not the file the wrapper says it "
        "wrote, so the next reader of that file sees the previous run"
    )


def test_reconcile_before_derive_gives_an_instruction_not_a_traceback(
    city: tuple[Workspace, Path, Path], gc_test_bin: Path  # noqa: F811
) -> None:
    workspace, kit, log = city

    result = drive(gc_test_bin, workspace, kit, log, "factory", "reconcile")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "factory derive" in result.stderr
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
    result = drive(gc_test_bin, workspace, kit, log, "factory", "derive")
    assert "DRIFT: FACTORY_KIT_HOME is set" in result.stdout, result.stdout
    assert "(pinned)" not in result.stdout
