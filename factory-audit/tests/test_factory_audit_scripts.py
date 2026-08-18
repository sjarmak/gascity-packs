"""The pack's own scripts, exercised as gc runs them.

Not a substitute for `tests/test_maintained_packs_live_gc.py` at the repo root,
which stands the pack up in a city and asks a real `gc` about it. This file
covers the part that lives below that line: what the scripts do when the kit is
missing, when the contract has not been written yet, and when the checkout is
not the commit the pack pins.

The checker itself is stubbed here. Its behaviour is tested in its own
repository; what is under test is the wrapper's handling of the checker's exit
status, which is what decides whether a scheduled order goes red.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap

import pytest


PACK = Path(__file__).resolve().parents[1]


def run(script: Path, city: Path, *args: str, **env_extra: str):
    env = dict(os.environ)
    env.pop("FACTORY_KIT_HOME", None)
    env.update(
        GC_PACK_DIR=str(PACK),
        GC_PACK_NAME="factory-audit",
        GC_CITY_PATH=str(city),
        **env_extra,
    )
    return subprocess.run(
        ["bash", str(script), *args],
        env=env,
        cwd=city,
        capture_output=True,
        text=True,
        timeout=120,
    )


def install_stub_kit(city: Path, exit_code: int = 0, commit: str | None = None) -> Path:
    """A checkout shaped like the kit, whose checker exits how the test says."""
    kit = city / ".gc" / "factory-kit"
    (kit / "src").mkdir(parents=True)
    kit.joinpath("src", "factory_check.py").write_text(
        textwrap.dedent(
            f"""\
            import sys
            print("stub checker ran: " + " ".join(sys.argv[1:]))
            sys.exit({exit_code})
            """
        )
    )
    subprocess.run(["git", "init", "-q"], cwd=kit, check=True)
    subprocess.run(["git", "add", "-A"], cwd=kit, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "stub"],
        cwd=kit,
        check=True,
    )
    return kit


def pinned_commit() -> str:
    for line in PACK.joinpath("kit.pin").read_text().splitlines():
        if line.startswith("KIT_COMMIT="):
            return line.split("=", 1)[1].strip().strip("'")
    raise AssertionError("kit.pin declares no KIT_COMMIT")


def write_contract(city: Path) -> None:
    out = city / ".gc" / "factory-audit"
    out.mkdir(parents=True, exist_ok=True)
    out.joinpath("factory.yaml").write_text("version: factory.reliability/v1\n")
    out.joinpath("probes.yaml").write_text("effects: []\n")


ORDER = PACK / "assets" / "scripts" / "factory-drift-check.sh"
AUDIT = PACK / "commands" / "factory" / "audit" / "run.sh"
RECONCILE = PACK / "commands" / "factory" / "reconcile" / "run.sh"
SETUP = PACK / "commands" / "factory" / "setup" / "run.sh"


def test_the_order_stays_green_when_the_kit_is_not_installed(tmp_path: Path) -> None:
    """An unconfigured city is not a drift finding.

    A scheduled check that goes red because a human has not run a one-time
    setup command teaches people that red means "not set up yet", and the first
    real finding then reads the same as the noise it has been producing for
    weeks.
    """
    result = run(ORDER, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "gc factory setup" in result.stdout


def test_the_order_stays_green_when_no_contract_has_been_written(tmp_path: Path) -> None:
    install_stub_kit(tmp_path)
    result = run(ORDER, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "gc factory derive" in result.stdout


def test_the_order_goes_red_when_the_checker_reports_drift(tmp_path: Path) -> None:
    """The other rail. Without this, the two greens above are indistinguishable
    from a wrapper that swallows every exit status it is handed.
    """
    install_stub_kit(tmp_path, exit_code=1)
    write_contract(tmp_path)
    result = run(ORDER, tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "stub checker ran: reconcile" in result.stdout


def test_the_order_is_green_when_the_checker_reports_no_drift(tmp_path: Path) -> None:
    install_stub_kit(tmp_path, exit_code=0)
    write_contract(tmp_path)
    result = run(ORDER, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_checkout_that_is_not_the_pinned_commit_says_so(tmp_path: Path) -> None:
    """The whole argument for pinning rather than vendoring.

    A vendored copy drifts silently. A pin is allowed to be stale only because
    every run prints which commit it actually used, so the stub kit -- which is
    never the pinned commit -- must produce a DRIFT line.
    """
    install_stub_kit(tmp_path)
    write_contract(tmp_path)
    result = run(ORDER, tmp_path)
    assert "DRIFT: pack pins" in result.stdout
    assert pinned_commit()[:12] in result.stdout


def test_audit_without_a_contract_gives_an_instruction_not_a_traceback(
    tmp_path: Path,
) -> None:
    install_stub_kit(tmp_path)
    result = run(AUDIT, tmp_path)
    assert result.returncode == 2
    assert "factory derive" in result.stderr
    assert "Traceback" not in result.stderr


def test_reconcile_without_probes_gives_an_instruction(tmp_path: Path) -> None:
    install_stub_kit(tmp_path)
    result = run(RECONCILE, tmp_path)
    assert result.returncode == 2
    assert "factory derive" in result.stderr


def test_every_command_refuses_to_run_without_pack_context(tmp_path: Path) -> None:
    """gc sets GC_PACK_DIR. Run by hand from a shell it is absent, and every
    path below it resolves against whatever directory happened to be current.
    """
    for script in (AUDIT, RECONCILE, SETUP):
        env = {k: v for k, v in os.environ.items() if k != "GC_PACK_DIR"}
        result = subprocess.run(
            ["bash", str(script)],
            env=env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 1, f"{script.parent.name}: {result.stderr}"
        assert "pack context" in result.stderr


def test_setup_refuses_while_an_override_points_elsewhere(tmp_path: Path) -> None:
    """Installing into the city while FACTORY_KIT_HOME wins would report success
    for a checkout no other command in the pack is going to read.
    """
    other = tmp_path / "elsewhere"
    other.mkdir()
    result = run(SETUP, tmp_path, FACTORY_KIT_HOME=str(other))
    assert result.returncode == 2
    assert "FACTORY_KIT_HOME" in result.stderr


def test_setup_refuses_a_pin_the_remote_does_not_carry(tmp_path: Path) -> None:
    """A pin naming an unpublished commit must fail loudly rather than land on
    whatever the default branch happens to be. Checking out the wrong checker
    produces findings the pack's own README cannot account for.

    The pin is overridden by copying the pack, not by exporting KIT_REPO: every
    command sources `kit.pin` itself, so an exported value is overwritten before
    it is read. The first version of this test did exactly that, reached the
    real repository, and passed on an unrelated failure.
    """
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=seed, check=True)
    seed.joinpath("README").write_text("not the kit\n")
    subprocess.run(["git", "add", "-A"], cwd=seed, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=seed,
        check=True,
    )
    subprocess.run(
        ["git", "push", "-q", str(remote), "HEAD:refs/heads/main"], cwd=seed, check=True
    )

    pack = tmp_path / "pack"
    subprocess.run(["cp", "-r", str(PACK), str(pack)], check=True)
    pack.joinpath("kit.pin").write_text(
        f"KIT_REPO='{remote}'\n"
        "KIT_COMMIT='0000000000000000000000000000000000000000'\n"
        "KIT_COMMIT_SUMMARY='a commit that was never published'\n"
    )

    city = tmp_path / "city"
    city.mkdir()
    env = dict(os.environ)
    env.pop("FACTORY_KIT_HOME", None)
    env.update(GC_PACK_DIR=str(pack), GC_PACK_NAME="factory-audit",
               GC_CITY_PATH=str(city))
    result = subprocess.run(
        ["bash", str(pack / "commands" / "factory" / "setup" / "run.sh")],
        env=env, cwd=city, capture_output=True, text=True, timeout=120,
    )

    assert result.returncode == 4, result.stdout + result.stderr
    assert "no commit" in result.stderr
    # The clone happened; what must not have happened is a checkout of some
    # other commit. The seed repository has no `src/`, so the kit resolver will
    # refuse this checkout rather than run whatever landed.
    assert not (city / ".gc" / "factory-kit" / "src").exists()
