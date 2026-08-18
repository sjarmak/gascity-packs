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
DERIVE = PACK / "commands" / "factory" / "derive" / "run.sh"
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
    assert "factory setup" in result.stdout


def test_the_order_stays_green_when_no_contract_has_been_written(tmp_path: Path) -> None:
    install_stub_kit(tmp_path)
    result = run(ORDER, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "factory derive" in result.stdout


def bind_pack_in(city: Path, name: str) -> None:
    """Write a city pack.toml importing this pack under `name`."""
    city.joinpath("pack.toml").write_text(
        textwrap.dedent(
            f"""\
            [pack]
            name = "city-under-test"
            schema = 2

            [imports.{name}]
            source = {str(PACK)!r}
            """
        )
    )


def test_an_instruction_names_the_binding_the_city_actually_used(
    tmp_path: Path,
) -> None:
    """gc sets GC_PACK_NAME to the PACK's name and exposes nothing carrying the
    BINDING. Every "run gc factory-audit factory setup" this pack printed was
    therefore a command that exits `unknown command` for anyone who bound it as
    anything else, and that could not be seen on an installation that happened
    to bind it under its own name. Measured against a real gc before this was
    written: bound as `fa`, `gc fa factory audit` printed `Run: gc factory
    setup`, and `gc factory setup` is not a command.
    """
    bind_pack_in(tmp_path, "fa")
    result = run(ORDER, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "gc fa factory setup" in result.stdout, result.stdout
    assert "<binding>" not in result.stdout


def test_the_placeholder_stands_in_when_the_binding_cannot_be_read(
    tmp_path: Path,
) -> None:
    """The other rail, and the reason the resolver returns nothing rather than
    guessing: a pack bound twice has two correct answers, so it gets the
    README's placeholder instead of whichever one sorted first. A concrete name
    that is wrong reads as an instruction; a placeholder reads as a placeholder.
    """
    tmp_path.joinpath("pack.toml").write_text(
        textwrap.dedent(
            f"""\
            [pack]
            name = "city-under-test"
            schema = 2

            [imports.fa]
            source = {str(PACK)!r}

            [imports.factory-audit]
            source = {str(PACK)!r}
            """
        )
    )
    result = run(ORDER, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "gc <binding> factory setup" in result.stdout, result.stdout


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
    # Without this line, deleting the checker invocation entirely and exiting 0
    # passes. Green because nothing ran and green because nothing is wrong are
    # the same exit status and must not be the same assertion.
    assert "stub checker ran: reconcile" in result.stdout


def test_a_checkout_that_is_not_the_pinned_commit_says_so(tmp_path: Path) -> None:
    """The whole argument for pinning rather than vendoring.

    A vendored copy drifts silently. A pin is allowed to be stale only because
    every run prints which commit it actually used, so the stub kit -- which is
    never the pinned commit -- must produce a DRIFT line.
    """
    kit = install_stub_kit(tmp_path)
    write_contract(tmp_path)
    result = run(ORDER, tmp_path)
    assert "DRIFT: pack pins" in result.stdout
    assert pinned_commit()[:12] in result.stdout
    # And the commit it reports as ACTUAL has to be this checkout's, not a
    # constant. A banner that prints the pin twice would satisfy the two
    # assertions above while telling the reader nothing about what ran.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=kit, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert f"kit {head[:12]} at " in result.stdout
    # And the checker still ran; a banner is not a check.
    assert "stub checker ran: reconcile" in result.stdout


def test_audit_without_a_contract_gives_an_instruction_not_a_traceback(
    tmp_path: Path,
) -> None:
    install_stub_kit(tmp_path)
    # probes.yaml present, factory.yaml absent: the fixture isolates the file
    # under test. With both absent this test passes against a command that
    # checks the wrong one.
    out = tmp_path / ".gc" / "factory-audit"
    out.mkdir(parents=True)
    out.joinpath("probes.yaml").write_text("effects: []\n")
    result = run(AUDIT, tmp_path)
    assert result.returncode == 2
    assert "factory derive" in result.stderr
    assert "Traceback" not in result.stderr


def test_reconcile_without_probes_gives_an_instruction(tmp_path: Path) -> None:
    install_stub_kit(tmp_path)
    # Contract present, probes absent. Written this way because with both
    # absent the command exits on the contract and this test would pass with
    # the probes check deleted outright.
    out = tmp_path / ".gc" / "factory-audit"
    out.mkdir(parents=True)
    out.joinpath("factory.yaml").write_text("version: factory.reliability/v1\n")
    result = run(RECONCILE, tmp_path)
    assert result.returncode == 2
    assert "probes.yaml" in result.stderr
    assert "factory derive" in result.stderr


def test_every_command_refuses_to_run_without_pack_context(tmp_path: Path) -> None:
    """gc sets GC_PACK_DIR. Run by hand from a shell it is absent, and every
    path below it resolves against whatever directory happened to be current.
    """
    for script in (AUDIT, DERIVE, RECONCILE, SETUP):
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
    # Deliberately not created. An implementation that refused only an
    # existing override directory would pass with `other.mkdir()` here, and the
    # property is about the variable being set, not about what it points at.
    other = tmp_path / "elsewhere"
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
    # The seed carries a checker at the path the resolver looks for, and a
    # DIFFERENT one. Without this the final assertion below is vacuous: a seed
    # with no `src/` makes "no unverified checker was left on disk" true no
    # matter what setup did, and the first version of this test passed that way
    # against an implementation that really did leave the default branch
    # checked out.
    seed.joinpath("src").mkdir()
    seed.joinpath("src", "factory_check.py").write_text(
        'raise SystemExit("the default branch checker ran")\n'
    )
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

    # The property: no working tree was materialized. A plain `git clone`
    # checks out the remote's default branch BEFORE anything verifies the pin,
    # so this used to leave an executable checker behind while the message said
    # nothing had been checked out -- and every later command would have run
    # it, because a commit mismatch is a warning rather than a refusal.
    assert not (city / ".gc" / "factory-kit" / "src").exists()

    # And the resolver refuses that directory rather than running whatever is
    # in it, which is the second half of the same property.
    followup = subprocess.run(
        ["bash", str(pack / "commands" / "factory" / "audit" / "run.sh")],
        env=env, cwd=city, capture_output=True, text=True, timeout=60,
    )
    assert followup.returncode == 2, followup.stdout + followup.stderr
    assert "no reliability kit" in followup.stderr
    assert "default branch checker ran" not in followup.stdout + followup.stderr


@pytest.mark.parametrize("script", ["audit", "derive", "reconcile", "setup"])
def test_help_does_not_require_the_kit(script: str, tmp_path: Path) -> None:
    """Help is not a checker result.

    Every command used to call `kit_require` before parsing its arguments, so
    the one command a person runs to find out how to install the kit failed
    because the kit was not installed.
    """
    result = run(PACK / "commands" / "factory" / script / "run.sh", tmp_path, "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip()


@pytest.mark.parametrize(
    "script,flag",
    [("audit", "--contract"), ("reconcile", "--probes"), ("derive", "--template")],
)
def test_a_flag_without_its_value_is_a_usage_error(
    script: str, flag: str, tmp_path: Path
) -> None:
    """Under `set -u` a bare $2 aborts with bash's own diagnostic and exit 1,
    so a typo in a flag reads as an internal error rather than as bad input.
    """
    install_stub_kit(tmp_path)
    result = run(PACK / "commands" / "factory" / script / "run.sh", tmp_path, flag)
    assert result.returncode == 64, result.stdout + result.stderr
    assert "needs a value" in result.stderr
    assert "unbound variable" not in result.stderr


def test_a_modified_checkout_is_not_reported_as_pinned(tmp_path: Path) -> None:
    """The checker runs from the working tree, not from the commit.

    A tree edited at the pinned commit reported `(pinned)` until the tree state
    was read too, which made the pin a decoration: the banner named a commit
    that was not what executed.
    """
    kit = install_stub_kit(tmp_path)
    write_contract(tmp_path)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "tag", "-f", "pin"],
        cwd=kit, check=True, capture_output=True,
    )
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=kit,
                          capture_output=True, text=True, check=True).stdout.strip()

    pack = tmp_path / "pack"
    subprocess.run(["cp", "-r", str(PACK), str(pack)], check=True)
    pack.joinpath("kit.pin").write_text(
        f"KIT_REPO='unused'\nKIT_COMMIT='{head}'\nKIT_COMMIT_SUMMARY='the pin'\n"
    )

    env = dict(os.environ)
    env.pop("FACTORY_KIT_HOME", None)
    env.update(GC_PACK_DIR=str(pack), GC_PACK_NAME="factory-audit",
               GC_CITY_PATH=str(tmp_path))

    def order() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(pack / "assets" / "scripts" / "factory-drift-check.sh")],
            env=env, cwd=tmp_path, capture_output=True, text=True, timeout=60,
        )

    clean = order()
    assert "(pinned)" in clean.stdout, clean.stdout + clean.stderr

    # The mutation, applied to the checkout rather than to the code: same
    # commit, different bytes.
    kit.joinpath("src", "factory_check.py").write_text("print('edited')\n")
    dirty = order()
    assert "(pinned)" not in dirty.stdout
    assert "local modifications" in dirty.stdout


def test_an_override_checkout_is_not_reported_as_pinned(tmp_path: Path) -> None:
    """FACTORY_KIT_HOME is a deliberate escape hatch, and saying so is the
    entire reason it is safe to have one.
    """
    kit = install_stub_kit(tmp_path)
    write_contract(tmp_path)
    result = run(ORDER, tmp_path, FACTORY_KIT_HOME=str(kit))
    assert "(pinned)" not in result.stdout
    assert "FACTORY_KIT_HOME is set" in result.stdout


def test_derive_from_a_template_installs_it_and_will_not_clobber_it(
    tmp_path: Path,
) -> None:
    """The probe pack is hand-edited after the first run, so a second `derive
    --template` from the README must not silently discard that work.
    """
    install_stub_kit(tmp_path)
    first = run(DERIVE, tmp_path, "--template", "gc-city")
    assert first.returncode == 0, first.stdout + first.stderr

    probes = tmp_path / ".gc" / "factory-audit" / "probes.yaml"
    assert "factory_name" in probes.read_text()
    probes.write_text(probes.read_text() + "\n# a hand edit\n")

    second = run(DERIVE, tmp_path, "--template", "gc-city")
    assert second.returncode == 3, second.stdout + second.stderr
    assert "a hand edit" in probes.read_text()


def test_derive_names_the_templates_it_has_when_asked_for_one_it_does_not(
    tmp_path: Path,
) -> None:
    install_stub_kit(tmp_path)
    result = run(DERIVE, tmp_path, "--template", "no-such-city")
    assert result.returncode == 64
    assert "gc-city" in result.stderr


def test_the_pack_ships_the_order_its_readme_promises(tmp_path: Path) -> None:
    """The live-gc suite asserts that every order a pack ships loads in a real
    city, and skips a pack that ships none. Deleting this pack's only order
    would turn that assertion into a skip, so the file's existence is pinned
    here where it is a fact about this pack rather than a shape shared by five.
    """
    assert (PACK / "orders" / "factory-drift.toml").is_file()


def _pin_values() -> dict[str, str]:
    """The pin file is sourced by shell, so read it the same way rather than
    parsing it with a regex that would disagree with what the scripts see."""
    out = subprocess.run(
        ["bash", "-c",
         f'. "{PACK}/kit.pin"; printf "%s\\n%s\\n%s\\n" '
         '"$KIT_REPO" "$KIT_COMMIT" "$KIT_COMMIT_SUMMARY"'],
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, f"kit.pin does not source cleanly: {out.stderr}"
    repo, commit, summary = out.stdout.rstrip("\n").split("\n")
    return {"repo": repo, "commit": commit, "summary": summary}


def test_the_pin_names_a_full_commit_and_says_what_it_is() -> None:
    """A short or empty pin never equals `git rev-parse HEAD`, so setup's
    already-at-the-pin check can never be true and every run re-clones while
    reporting success. The summary is what makes a stale pin visible to a
    reader who is not going to resolve the sha."""
    pin = _pin_values()
    assert len(pin["commit"]) == 40 and all(
        c in "0123456789abcdef" for c in pin["commit"]
    ), f"KIT_COMMIT is not a full lowercase sha: {pin['commit']!r}"
    assert pin["summary"].strip(), "KIT_COMMIT_SUMMARY is empty"
    assert pin["repo"].strip(), "KIT_REPO is empty"


def test_the_changelog_names_the_commit_the_pack_pins() -> None:
    """The pin went nine commits stale once, silently, because moving it is a
    one-line edit and nothing tied that line to a record anyone reads. This is
    that tie: the changelog has to name the pinned commit, so a pin move that
    skips the changelog fails here rather than in an installing city.

    It asserts the sha appears somewhere in the file, not that it appears in a
    particular section, because pinning the section shape would break on the
    first release that reorganises it and teach the next person to delete the
    test instead of updating the entry.
    """
    changelog = PACK / "CHANGELOG.md"
    assert changelog.is_file(), (
        "kit.pin's own instructions say to record a pin move in the pack "
        "CHANGELOG; there is no CHANGELOG.md"
    )
    commit = _pin_values()["commit"]
    text = changelog.read_text()
    assert commit[:7] in text, (
        f"the changelog does not mention the pinned commit {commit[:12]}; "
        "moving the pin without recording what changed in the kit is the "
        "failure this test exists for"
    )
