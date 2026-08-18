from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import textwrap

import pytest


# This suite cannot do its job without a real gc binary: without one its
# fixture skips, the step stays green, and the output says `s` where it would
# have said `F`. Declared rather than inferred, so the CI-coverage guard in
# tests/test_ci_runs_every_pack_suite.py can see it whatever route it takes to
# ask for a binary.
REQUIRES_GC_BINARY = True

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PromptWorkspace:
    city_dir: Path
    rig_dir: Path
    env: dict[str, str]


@pytest.fixture(scope="session")
def gc_test_bin() -> Path:
    configured = os.environ.get("GC_TEST_BIN")
    if not configured:
        pytest.skip("set GC_TEST_BIN to run real Gas City CLI integration tests")

    binary = Path(configured).expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        pytest.fail(f"GC_TEST_BIN is not an executable file: {binary}")
    return binary


def write_prompt_workspace(
    root: Path,
    *,
    city_binding: str,
    city_pack: Path,
) -> PromptWorkspace:
    city_dir = root / "city"
    rig_dir = root / "fixture"
    gc_home = root / "gc-home"
    home = root / "home"
    (city_dir / ".gc").mkdir(parents=True)
    rig_dir.mkdir()
    gc_home.mkdir()
    home.mkdir()

    roles_source = (REPO_ROOT / "gascity" / "roles").resolve()
    city_pack = city_pack.resolve()
    city_dir.joinpath("pack.toml").write_text(
        textwrap.dedent(
            f"""\
            [pack]
            name = "prompt-integration"
            schema = 2

            [imports.{city_binding}]
            source = {json.dumps(str(city_pack))}
            """
        ),
        encoding="utf-8",
    )
    city_dir.joinpath("city.toml").write_text(
        textwrap.dedent(
            f"""\
            [workspace]
            provider = "codex"

            [providers.codex]
            base = "builtin:codex"

            [[rigs]]
            name = "fixture"

            [rigs.imports.gc]
            source = {json.dumps(str(roles_source))}
            """
        ),
        encoding="utf-8",
    )
    city_dir.joinpath(".gc", "site.toml").write_text(
        textwrap.dedent(
            f"""\
            workspace_name = "prompt-integration"

            [[rig]]
            name = "fixture"
            path = {json.dumps(str(rig_dir))}
            """
        ),
        encoding="utf-8",
    )

    # Strip the caller's Gas City and beads environment rather than inheriting
    # it, the same way `gc_live_city.write_city` does. This harness is a second
    # copy of that one and drifted from it: `gascity/commands/claim/run.sh`
    # reads `EXPECTED_ROUTE="${GC_TEMPLATE:-${GC_AGENT:-}}"`, so a maintainer
    # running this suite from inside a Gas City seat had their own seat's
    # GC_TEMPLATE beat the GC_AGENT the test sets, and the claim test failed
    # with `CLAIM_REJECTED route mismatch`. Green in CI, red for exactly the
    # people who maintain these packs. Refute by restoring `**os.environ` and
    # running the suite with GC_TEMPLATE set.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GC_", "BEADS_"))
    }
    env.update({
        "HOME": str(home),
        "GC_HOME": str(gc_home),
        "GC_CITY": str(city_dir),
        "GC_CITY_PATH": str(city_dir),
        "GC_CITY_ROOT": str(city_dir),
        "GC_RIG": "fixture",
    })
    return PromptWorkspace(city_dir=city_dir, rig_dir=rig_dir, env=env)


def run_gc(
    gc_test_bin: Path,
    workspace: PromptWorkspace,
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(gc_test_bin), *args],
        cwd=cwd or workspace.rig_dir,
        env=env or workspace.env,
        text=True,
        capture_output=True,
        timeout=30,
    )


def assert_clean_worker_render(prompt: str, persona_heading: str) -> None:
    assert persona_heading in prompt
    assert prompt.count("# GC Role Worker") == 1
    assert '{{ template "gc-role-worker" . }}' not in prompt
    assert "gc gc claim" in prompt
    assert "CLAIMED_BEAD_ID" in prompt
    assert "CLAIMED_ROOT_BEAD_ID" in prompt
    assert "CLAIMED_CONTINUATION_GROUP" in prompt
    assert 'gc bd update "$CLAIMED_BEAD_ID"' in prompt
    assert "An empty continuation group is a hard session boundary" in prompt


def test_city_scoped_gascity_registers_claim_command_from_rig(
    tmp_path: Path, gc_test_bin: Path
) -> None:
    workspace = write_prompt_workspace(
        tmp_path,
        city_binding="gc",
        city_pack=REPO_ROOT / "gascity",
    )

    result = run_gc(gc_test_bin, workspace, "gc", "claim", "--help")

    assert result.returncode == 0, result.stderr
    assert "Atomically claim one routed workflow bead" in result.stdout
    assert "Usage:\n  gc gc claim" in result.stdout
    assert "Gas City CLI — orchestration-builder" not in result.stdout


@pytest.mark.parametrize(
    ("city_binding", "pack_path", "agent", "persona_heading"),
    (
        ("gc", "gascity", "gc.implementation-worker", "# GC Role Worker"),
        ("bmad", "bmad", "bmad.story-implementer", "# BMAD Story Implementer"),
        (
            "superpowers",
            "superpowers",
            "superpowers.implementer",
            "# Superpowers Implementer",
        ),
        ("gstack", "gstack", "gstack.implementer", "# gstack Implementer"),
        (
            "compound-engineering",
            "compound-engineering",
            "compound-engineering.ce-work",
            "# Compound Engineering Worker",
        ),
        ("profiler", "profiler", "profiler.profile-analyst", "# Profile Analyst"),
    ),
)
def test_role_prompts_render_public_worker_fragment(
    tmp_path: Path,
    gc_test_bin: Path,
    city_binding: str,
    pack_path: str,
    agent: str,
    persona_heading: str,
) -> None:
    workspace = write_prompt_workspace(
        tmp_path,
        city_binding=city_binding,
        city_pack=REPO_ROOT / pack_path,
    )

    result = run_gc(
        gc_test_bin,
        workspace,
        "--city",
        str(workspace.city_dir),
        "prime",
        "--strict",
        f"fixture/{agent}",
        cwd=workspace.city_dir,
    )

    assert result.returncode == 0, result.stderr
    assert_clean_worker_render(result.stdout, persona_heading)


def test_registered_claim_command_dispatches_store_aware_show_and_normalizes_json(
    tmp_path: Path, gc_test_bin: Path
) -> None:
    workspace = write_prompt_workspace(
        tmp_path,
        city_binding="gc",
        city_pack=REPO_ROOT / "gascity",
    )
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    calls = tmp_path / "nested-gc-calls"
    nested_gc = fake_bin / "gc"
    nested_gc.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            printf '%s\n' "$*" >>"$GC_TEST_CALLS"
            if [ "$1" = hook ] && [ "$2" = --claim ] && [ "$3" = --drain-ack ] && [ "$4" = --json ]; then
              printf '%s\n' '{"action":"work","bead_id":"bd-123","assignee":"worker","route":"gc.implementation-worker"}'
            elif [ "$1" = b""d ] && [ "$2" = show ] && [ "$3" = bd-123 ] && [ "$4" = --json ]; then
              printf '%s\n' '{"id":"bd-123","status":"in_progress","assignee":"worker","metadata":{"gc.routed_to":"gc.implementation-worker","gc.root_bead_id":"root-1","gc.continuation_group":"group-1"}}'
            else
              printf 'unexpected nested gc invocation: %s\n' "$*" >&2
              exit 2
            fi
            """
        ),
        encoding="utf-8",
    )
    nested_gc.chmod(0o755)
    env = {
        **workspace.env,
        "BEADS_ACTOR": "worker",
        "GC_AGENT": "gc.implementation-worker",
        "GC_TEST_CALLS": str(calls),
        "PATH": f"{fake_bin}:/usr/bin:/bin",
    }

    result = run_gc(gc_test_bin, workspace, "gc", "claim", env=env)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["bead_id"] == "bd-123"
    assert payload["root_bead_id"] == "root-1"
    assert payload["continuation_group"] == "group-1"
    assert payload["bead"]["id"] == "bd-123"
    assert calls.read_text(encoding="utf-8").splitlines() == [
        "hook --claim --drain-ack --json",
        " ".join(("b" + "d", "show", "bd-123", "--json")),
    ]


def test_the_harness_does_not_inherit_the_callers_seat_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CI has a clean environment; the people who maintain these packs do not.

    Every command under test reads `GC_*`, and the claim command in particular
    resolves its expected route as `${GC_TEMPLATE:-${GC_AGENT:-}}`. Inheriting
    the caller's environment therefore let a maintainer's own seat decide the
    answer, and the suite was green on a runner and red on the machine where
    the packs are actually edited.

    The variables are set here rather than relied on from the runner, so this
    goes red on a clean CI box too if the scrub is removed.
    """
    monkeypatch.setenv("GC_TEMPLATE", "mayor")
    monkeypatch.setenv("GC_AGENT", "some-other-agent")
    monkeypatch.setenv("BEADS_DOLT_SERVER_PORT", "29620")

    workspace = write_prompt_workspace(
        tmp_path, city_binding="gc", city_pack=REPO_ROOT / "gascity"
    )
    assert workspace.env.get("GC_TEMPLATE") is None, workspace.env.get("GC_TEMPLATE")
    assert workspace.env.get("GC_AGENT") is None, workspace.env.get("GC_AGENT")
    assert workspace.env.get("BEADS_DOLT_SERVER_PORT") is None
    # And the variables the harness sets on purpose survive the scrub, so this
    # cannot be satisfied by handing back an empty environment.
    assert workspace.env["GC_CITY_PATH"] == str(workspace.city_dir)
    assert workspace.env["GC_RIG"] == "fixture"
