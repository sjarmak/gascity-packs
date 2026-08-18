"""The pack's own wiring, exercised the way gc runs it.

Not a substitute for `tests/test_maintained_packs_live_gc.py` at the repo root,
which stands the pack up in a city and asks a real `gc` about it. This file
covers what sits below that line: the command wrapper's handling of the
checker's exit status, the order that schedules it, the fixtures the checker
uses as its own controls, and the checker's own suite.

The exit-status cases are the load-bearing ones. This checker has three
outcomes, not two — 0 conforms, 1 found a failure, 2 could not check — and a
wrapper that collapses 2 into 1 reports a finding the city does not have, while
a wrapper that collapses 2 into 0 reports a clean run over a corpus it never
read. Both readings are worse than no instrument, so each code is pinned
separately against a stub that exits exactly that code.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap
import tomllib

import pytest


PACK = Path(__file__).resolve().parents[1]
CHECK_RUN = PACK / "commands" / "scan" / "run.sh"


def run_wrapper(*args: str, pack_dir: Path | None = None, city: Path | None = None,
                **env_extra: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    for var in ("GC_PACK_DIR", "GC_PACK_NAME", "GC_CITY_PATH", "GC_CITY",
                "INSTRUMENT_CONTRACT_CITY", "INSTRUMENT_CONTRACT_CONTROL",
                "INSTRUMENT_CONTRACT_ISSUE_PREFIXES"):
        env.pop(var, None)
    if pack_dir is not None:
        env["GC_PACK_DIR"] = str(pack_dir)
        env["GC_PACK_NAME"] = "untested-orders"
    if city is not None:
        env["GC_CITY_PATH"] = str(city)
    env.update(env_extra)
    return subprocess.run(
        ["bash", str(CHECK_RUN), *args],
        env=env,
        cwd=str(city) if city is not None else str(PACK),
        capture_output=True,
        text=True,
        timeout=120,
    )


def stub_pack(tmp_path: Path, exit_code: int) -> Path:
    """A pack-shaped directory whose checker exits how the test says.

    The real checker's behaviour is covered by its own suite, run below. What
    is under test here is the wrapper around it, and stubbing the checker is
    the only way to drive an exit code the real one would not produce on
    demand.
    """
    pack = tmp_path / "stub-pack"
    scripts = pack / "assets" / "scripts"
    scripts.mkdir(parents=True)
    checker = scripts / "untested-orders-check"
    checker.write_text(
        textwrap.dedent(
            f"""\
            import sys
            print("argv: " + " ".join(sys.argv[1:]))
            sys.exit({exit_code})
            """
        )
    )
    checker.chmod(0o755)
    return pack


# --- pack identity --------------------------------------------------------

def test_pack_declares_its_identity():
    pack = tomllib.loads((PACK / "pack.toml").read_text())["pack"]
    assert pack["name"] == "untested-orders"
    assert pack["schema"] == 2
    assert pack["version"]


def test_every_command_has_help_and_is_runnable():
    runs = sorted((PACK / "commands").rglob("run.sh"))
    assert runs, "the pack registers no commands"
    for run in runs:
        assert (run.parent / "help.md").is_file(), f"{run} has no help.md"
        assert os.access(run, os.X_OK), f"{run} is not executable"


# --- the wrapper's three outcomes ----------------------------------------

@pytest.mark.parametrize("code", [0, 1, 2])
def test_wrapper_propagates_every_checker_exit_code(tmp_path, code):
    city = tmp_path / "city"
    city.mkdir()
    result = run_wrapper(pack_dir=stub_pack(tmp_path, code), city=city)
    assert result.returncode == code, result.stderr


def test_no_arguments_audits_the_enabled_order_population(tmp_path):
    city = tmp_path / "city"
    city.mkdir()
    result = run_wrapper(pack_dir=stub_pack(tmp_path, 0), city=city)
    assert "argv: --enabled-local-orders" in result.stdout


def test_arguments_are_forwarded_verbatim(tmp_path):
    city = tmp_path / "city"
    city.mkdir()
    result = run_wrapper("bin/one", "bin/two",
                         pack_dir=stub_pack(tmp_path, 0), city=city)
    assert "argv: bin/one bin/two" in result.stdout
    # A path selector must NOT quietly become a population audit: the two
    # answer different questions and only one of them is scoped to what the
    # caller asked about.
    assert "--enabled-local-orders" not in result.stdout


def test_missing_pack_context_fails_loudly(tmp_path):
    city = tmp_path / "city"
    city.mkdir()
    result = run_wrapper(city=city)
    assert result.returncode == 1
    assert "missing Gas City pack context" in result.stderr


def test_missing_checker_names_the_path_it_looked_for(tmp_path):
    empty = tmp_path / "empty-pack"
    empty.mkdir()
    result = run_wrapper(pack_dir=empty, city=tmp_path)
    assert result.returncode == 1
    assert "checker missing at" in result.stderr
    assert str(empty) in result.stderr


# --- the standing order ---------------------------------------------------

def test_audit_order_runs_a_script_the_pack_ships():
    order = tomllib.loads(
        (PACK / "orders" / "untested-orders-audit.toml").read_text())["order"]
    assert order["trigger"] == "cooldown"
    assert order["idempotent"] is True
    # Quoted, because a pack directory containing a space otherwise splits into
    # two arguments and the order fails naming a file that does not exist
    # rather than the path that does.
    assert '"$GC_PACK_DIR/assets/scripts/untested-orders-check"' in order["exec"]
    assert "--enabled-local-orders" in order["exec"]
    relative = order["exec"].split('"')[1].replace("$GC_PACK_DIR/", "")
    assert (PACK / relative).is_file()


def test_audit_order_names_no_absolute_path():
    """A path from the city this came from would run somewhere else, or nowhere."""
    text = (PACK / "orders" / "untested-orders-audit.toml").read_text()
    assert "/home/" not in text
    assert "$GC_PACK_DIR" in text


# --- the fixtures the checker uses as its own controls --------------------

def test_positive_control_fixture_is_protected():
    control = PACK / "assets" / "fixtures" / "protected-canary"
    assert control.is_file()
    assert os.access(control, os.X_OK)
    assert (PACK / "assets" / "fixtures" / "protected-canary.test").is_file()


def test_negative_control_fixture_has_no_test_on_purpose():
    """The finding rail needs something that fails, or only half the tool is proven."""
    unprotected = PACK / "assets" / "fixtures" / "unprotected-canary"
    assert unprotected.is_file()
    fixtures = PACK / "assets" / "fixtures"
    assert not (fixtures / "unprotected-canary.test").exists()
    assert not list(fixtures.glob("test_unprotected_canary.py"))


def test_checker_ships_no_path_from_the_city_it_came_from():
    text = (PACK / "assets" / "scripts" / "untested-orders-check").read_text()
    assert "/home/" not in text


# --- the checker's own suite ---------------------------------------------

def test_vendored_checker_suite_passes():
    """C3 applied to this pack: the checker it ships is itself under test."""
    suite = PACK / "assets" / "scripts" / "untested-orders-check.test"
    result = subprocess.run(
        ["python3", str(suite)], capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.rstrip().endswith("RESULT: PASS")
