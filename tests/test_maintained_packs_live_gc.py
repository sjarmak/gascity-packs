"""Every pack we maintain, stood up in a city and asked about by a real `gc`.

These five are the packs users actually install, and the ones we have committed
to keeping working. Each is imported on its own here, because each is imported
on its own by a user -- nobody installs "the maintained set". The whole point of
running them separately is that a break in one is attributed to that one.

What each pack gets:

* its declared surfaces, derived from its own directory rather than listed here,
  resolved through a running `gc` in a city that imports it;
* a `gc doctor` delta against a baseline city, asserted by set EQUALITY against
  what that pack is currently expected to add. Equality rather than emptiness
  because a legitimate finding exists (an adapter binary a pack cannot ship
  built), and equality rather than `assertFalse` on new items because a finding
  that DISAPPEARS is also news: it means either the pack stopped declaring
  something or `gc` stopped checking it.

The control lives in `test_the_doctor_delta_can_surface_a_finding` and every
delta assertion here depends on it. An empty or unchanged delta is also what a
doctor that stopped reporting produces.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit
from pathlib import Path

import pytest

from gc_live_city import (
    CANARY_BINDING,
    CANARY_CHECK,
    REPO_ROOT,
    attributable,
    declares_a_rig_scoped_session,
    declares_a_service,
    discover_agents,
    discover_command_words,
    discover_formulas,
    discover_orders,
    gc_output,
    gc_test_bin,  # noqa: F401 -- pytest fixture, used by name
    registered_orders,
    write_canary_pack,
    write_city,
)


# The packs this city owns the maintenance of. Adding a pack here is the whole
# cost of bringing it under live-gc coverage; everything below derives from the
# pack's own contents.
# This suite cannot do its job without a real gc binary: without one its
# fixture skips, the step stays green, and the output says `s` where it would
# have said `F`. Declared rather than inferred, so the CI-coverage guard in
# tests/test_ci_runs_every_pack_suite.py can see it whatever route it takes to
# ask for a binary.
REQUIRES_GC_BINARY = True

MAINTAINED_PACKS = (
    "factory-audit",
    "oversight-rig",
    "pr-pipeline",
    "slack-channel",
    "slack-full",
    "slack-mini",
)

# Doctor findings each pack is currently expected to add to a city, with the
# reason it is legitimate. An entry here is a claim that a user installing the
# pack meets this message and that we have decided it is correct for them to.
# Anything not written down is a regression, and removing an entry without
# removing its cause is caught too, because the assertion is equality.
EXPECTED_DOCTOR_DELTA: dict[str, frozenset[str]] = {
    "factory-audit": frozenset(),
    "oversight-rig": frozenset(),
    "pr-pipeline": frozenset(),
    "slack-channel": frozenset(),
    # Both of these are the correct messages for a fresh install, and both come
    # from checks only `slack-full` ships. `binaries`: the pack ships its Slack
    # adapter as source, and the user builds it during setup. `env`: the
    # adapter's credentials live in a config file the user writes during setup,
    # and it does not exist yet. `slack-channel` and `slack-mini` ship the same
    # unbuilt adapter and no check that notices, which is why their entries are
    # empty rather than matching.
    "slack-full": frozenset({"slack-full:binaries", "slack-full:env"}),
    "slack-mini": frozenset(),
}

# Findings whose presence is a property of the machine, not of the pack. These
# are set aside before the equality above and PRINTED whenever they are, so a
# run always shows what it stopped asserting on -- a silent subtraction and a
# check that stopped reporting read identically.
#
# Keep this set as small as the evidence forces. It is not a waiver list: the
# bar is that no import of the pack can decide the outcome, so the equality
# assertion could not be green on every machine at once.
HOST_DEPENDENT: dict[str, frozenset[str]] = {
    # slack-full/doctor/check-funnel.sh inspects the host's Tailscale Funnel
    # rules. With tailscale absent it prints a note and exits 0; with tailscale
    # present and no rule forwarding to the adapter port it exits 2. Both are
    # correct messages for the machine they ran on, and neither is caused by
    # importing the pack -- a developer's laptop and a CI runner cannot both
    # satisfy one recorded value.
    "slack-full": frozenset({"slack-full:funnel"}),
}


def pack_dir(pack: str) -> Path:
    return REPO_ROOT / pack


IMPORT_KEY = re.compile(r"^\[imports\.([A-Za-z0-9_-]+)\]", re.M)

# A pack's own changelog records what a verb was called when it shipped.
# Rewriting history to match today's binding would be a lie, so it is not
# evidence of drift and is excluded from the scan.
NOT_INSTRUCTIONS = ("CHANGELOG.md",)

INSTRUCTED_SUFFIXES = (
    ".md", ".sh", ".bash", ".py", ".go", ".toml", ".json", ".txt",
)


def readme_import_key(pack: str) -> str | None:
    """The binding a pack's README tells a user to install it under.

    This is the whole contract under test: gc registers a pack's verbs under
    the IMPORT KEY, and neither the pack directory nor `pack.toml [pack] name`
    participates. Measured -- a pack imported as `chatops` answers to
    `gc chatops <verb>` and to nothing else.
    """
    readme = pack_dir(pack) / "README.md"
    keys = IMPORT_KEY.findall(readme.read_text(encoding="utf-8"))
    assert len(keys) <= 1, (
        f"{pack}/README.md documents {len(keys)} import keys {keys}; this guard "
        f"compares the pack's instructions against ONE documented binding, and "
        f"cannot tell which of several a reader would use."
    )
    return keys[0] if keys else None


def instructed_bindings(pack: str) -> dict[tuple[str, str], int]:
    """Every `gc <literal> <verb>` pair the pack instructs, and how often.

    The VERB is carried alongside the literal because it is what makes a
    sibling-pack reference distinguishable from a mistake: `gc slack-mini
    post-message` inside slack-full is a true statement about slack-mini, while
    `gc slack-mini bind-room` names a verb slack-mini does not ship and is
    simply wrong. A literal alone cannot tell those apart.

    Derived from the verbs the pack actually ships rather than from a list, so
    a pack that grows a command is covered without touching this file. Keyed on
    a shipped verb specifically because `gc records the upload` is prose, not an
    instruction, and a bare `gc <word>` scan cannot tell the two apart.
    """
    verbs = {words[0] for words in discover_command_words(pack_dir(pack))}
    if not verbs:
        return {}
    pattern = re.compile(
        r"\bgc ([a-z][a-z0-9_-]*) (%s)\b" % "|".join(re.escape(v) for v in sorted(verbs))
    )
    counts: dict[tuple[str, str], int] = {}
    for path in sorted(pack_dir(pack).rglob("*")):
        if not path.is_file() or path.suffix not in INSTRUCTED_SUFFIXES:
            continue
        if path.name in NOT_INSTRUCTIONS:
            continue
        # A test asserting the string `gc fa setup` is a fixture pinning an
        # expected output, not an instruction a user will read and type.
        # Counting it would make a pack that TESTS this contract look like a
        # pack that violates it -- which is exactly backwards.
        if "/tests/" in path.as_posix() or path.name.startswith("test_"):
            continue
        for literal, verb in pattern.findall(
            path.read_text(encoding="utf-8", errors="replace")
        ):
            counts[(literal, verb)] = counts.get((literal, verb), 0) + 1
    return counts


def wiring(pack: str) -> tuple[dict[str, Path], dict[str, Path]]:
    """City-scope and rig-scope bindings for one pack, as its manifest requires.

    Not a choice. A pack declaring a `[[service]]` is rejected at rig scope, and
    a pack declaring a rig-scoped `[[named_session]]` leaves `rig-pack-coverage`
    reported unless it is bound per rig. Both are read from the pack, so a pack
    that changes its manifest changes how this suite installs it.
    """
    directory = pack_dir(pack)
    has_service = declares_a_service(directory)
    needs_rig = declares_a_rig_scoped_session(directory)

    assert not (has_service and needs_rig), (
        f"{pack} declares both a [[service]] (city scope only) and a rig-scoped "
        "[[named_session]] (needs a rig binding). There is no wiring that "
        "satisfies both, so this suite cannot describe how to install it."
    )

    return {pack: directory}, ({pack: directory} if needs_rig else {})


@pytest.fixture(scope="session")
def canary_delta(tmp_path_factory, gc_test_bin: Path) -> frozenset[str]:  # noqa: F811
    """The control, run once: a pack that earns a finding on purpose.

    Every delta assertion in this file is a statement about a subtraction. If
    the subtraction cannot surface anything -- because doctor stopped reporting,
    because the fixture city fails to load before doctor reaches its packs,
    because the binary changed its output shape -- then every one of those
    statements holds vacuously and this suite goes green having measured
    nothing. This fixture is what makes the greens mean something.
    """
    root = tmp_path_factory.mktemp("canary")
    canary = write_canary_pack(root / "fixture")
    return frozenset(attributable(gc_test_bin, root / "city", {CANARY_BINDING: canary}))


def test_the_doctor_delta_can_surface_a_finding(canary_delta: frozenset[str]) -> None:
    assert CANARY_CHECK in canary_delta, (
        'a pack whose formula declares the deprecated `contract = "graph.v2"` '
        f"did not add {CANARY_CHECK!r} to the doctor delta, so every delta "
        f"asserted in this file proves nothing. Delta was: {sorted(canary_delta)}"
    )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_pack_adds_only_the_doctor_findings_we_have_accepted(
    pack: str, tmp_path: Path, gc_test_bin: Path, canary_delta: frozenset[str]  # noqa: F811
) -> None:
    imports, rig_imports = wiring(pack)
    found = attributable(gc_test_bin, tmp_path, imports, rig_imports)
    expected = EXPECTED_DOCTOR_DELTA[pack]

    host = HOST_DEPENDENT.get(pack, frozenset())
    for check in sorted(found & host):
        print(
            f"[host-dependent] {check} reported on this machine and is not "
            f"asserted on; see HOST_DEPENDENT in {Path(__file__).name}"
        )
    found -= host

    assert found == expected, (
        f"installing {pack} changes what gc doctor reports, against what this "
        f"suite records as accepted.\n"
        f"  new (a user installing {pack} now meets this): {sorted(found - expected)}\n"
        f"  gone (recorded as expected, no longer reported): {sorted(expected - found)}\n"
        f"Run `gc doctor` in a city importing {pack} to read the messages. A new "
        f"finding is a defect in the pack unless it is deliberate, in which case "
        f"it goes in EXPECTED_DOCTOR_DELTA with the reason. A finding that went "
        f"away is fixed work: delete the entry in the same change."
    )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_pack_registers_the_command_verbs_it_ships(
    pack: str, tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    """Pack commands are discovered by convention, so nothing declares them.

    That makes the surface easy to lose silently: a moved directory or a renamed
    leaf script drops a verb with no error anywhere. `gc <pack> ... --help` is
    where a user would notice, so it is where this asserts.
    """
    leaves = discover_command_words(pack_dir(pack))
    if not leaves:
        pytest.skip(f"{pack} ships no commands")

    imports, rig_imports = wiring(pack)
    workspace = write_city(tmp_path, imports, rig_imports)

    # One `--help` per level of nesting: pr-pipeline puts its leaves under `pr`,
    # the slack packs put theirs directly under the pack.
    by_parent: dict[tuple[str, ...], set[str]] = {}
    for words in leaves:
        by_parent.setdefault(words[:-1], set()).add(words[-1])

    for parent, expected in sorted(by_parent.items()):
        listed = set(gc_output(gc_test_bin, workspace, pack, *parent, "--help").split())
        missing = expected - listed
        assert not missing, (
            f"gc {pack} {' '.join(parent)} --help did not offer verbs the pack "
            f"ships: " + ", ".join(sorted(missing))
        )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_pack_formulas_resolve_through_a_city(
    pack: str, tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    expected = discover_formulas(pack_dir(pack))
    if not expected:
        pytest.skip(f"{pack} ships no formulas")

    imports, rig_imports = wiring(pack)
    workspace = write_city(tmp_path, imports, rig_imports)
    listed = set(gc_output(gc_test_bin, workspace, "formula", "list").split())

    missing = expected - listed
    assert not missing, (
        f"formulas {pack} ships did not resolve in a city that imports it: "
        + ", ".join(sorted(missing))
    )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_pack_agents_resolve_through_a_city(
    pack: str, tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    expected = discover_agents(pack_dir(pack))
    if not expected:
        pytest.skip(f"{pack} ships no agents")

    imports, rig_imports = wiring(pack)
    workspace = write_city(tmp_path, imports, rig_imports)
    listed = gc_output(gc_test_bin, workspace, "agent", "list")

    missing = {name for name in expected if name not in listed}
    assert not missing, (
        f"agent roles {pack} ships did not resolve in a city that imports it: "
        + ", ".join(sorted(missing))
        + f"\nOutput:\n{listed}"
    )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_pack_orders_load_in_a_running_city(
    pack: str, tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    """An order file that parses as TOML is not an order gc will run.

    `gc lint` reports `ok` on a pack whose order sets `cooldown = "24h"` under a
    cooldown trigger; the running binary refuses the same file with `cooldown
    trigger requires interval` and drops it. Nothing else in this suite would
    notice, because a dropped order changes no command, no agent, and no doctor
    finding -- the scheduled surface simply is not there.

    Measured on factory-audit while it was being written, which is why this test
    exists at all.
    """
    shipped = discover_orders(pack_dir(pack))
    if not shipped:
        pytest.skip(f"{pack} ships no orders")

    imports, rig_imports = wiring(pack)
    workspace = write_city(tmp_path, imports, rig_imports)
    loaded = registered_orders(gc_test_bin, workspace)

    missing = shipped - loaded
    assert not missing, (
        f"{pack} ships orders/ files that a running gc did not register: "
        f"{sorted(missing)}. It loaded {sorted(loaded)}. Run `gc order list` in "
        f"a city importing {pack} to read why -- a rejected order is reported "
        f"there and nowhere else."
    )


# --- the API base URL a pack falls back to when nothing sets it -------------

# `gc` sets GC_API_BASE_URL nowhere in its own source, so a pack's hardcoded
# fallback is what runs on a fresh install. Ours is masked: the supervisor on
# this machine is launched with the variable already set, so every pack works
# here whatever it declares.
# The three shapes a *fallback* takes in these packs: shell parameter
# expansion, a Go envOr-style second argument, and a Go const. Deliberately
# NOT matched: `env["GC_API_BASE_URL"] = "..."`, which SETS the variable
# rather than defaulting it -- a test fixture pinning a value is not a
# finding, and matching it would make this red for a reason that is not the
# bug.
API_FALLBACKS = (
    re.compile(r"GC_API_BASE_URL:-(http://[^}\s\"']+)"),
    re.compile(r'GC_API_BASE_URL"\s*,\s*"(http://[^"]+)"'),
    re.compile(r'defaultGCAPIBase\s*=\s*"(http://[^"]+)"'),
)

# Only files a city executes. Documentation may show any example it likes.
FALLBACK_SUFFIXES = (".sh", ".bash", ".py", ".go")

# A fourth shape, and the one that matters most: the default is a NAMED
# CONSTANT rather than a literal, so no single-line regex sees the URL.
# `slack-full/scripts/slack_intake_common.py` and
# `oversight-rig/assets/scripts/resolve_rig_channel.py` both use it. Missing
# this class is how slack-full read clean while its adapter carried the bug.
INDIRECT_FALLBACK = re.compile(
    r"""GC_API_BASE_URL["']\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,)]"""
)


def _resolve_constant(name: str, text: str) -> str:
    """The URL a module-level constant holds, or a value that FAILS the check.

    Fail-closed on purpose: an indirection this cannot follow is a blind spot,
    and a blind spot must be loud. Returning the sentinel makes the port
    assertion red and names the constant, rather than silently dropping the
    site the way a `continue` would.
    """
    found = re.search(
        r"""^[ \t]*%s\s*=\s*["'](http://[^"']+)["']""" % re.escape(name),
        text,
        re.M,
    )
    return found.group(1) if found else f"<unresolved constant {name}>"

# `Supervisor.PortOrDefault()` in internal/supervisor. See the docstring on
# test_pack_falls_back_to_the_port_this_gc_actually_serves for why this is
# pinned rather than asked for, and what that costs.
EXPECTED_API_PORT = "8372"


def declared_api_fallbacks(pack: str) -> dict[str, str]:
    """Every executable fallback in a pack, keyed by repo-relative path."""
    found: dict[str, str] = {}
    for path in sorted(pack_dir(pack).rglob("*")):
        if not path.is_file() or path.suffix not in FALLBACK_SUFFIXES:
            continue
        if (
            "/tests/" in path.as_posix()
            or path.name.endswith("_test.go")
            or path.name.startswith("test_")
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(REPO_ROOT))
        for pattern in API_FALLBACKS:
            for match in pattern.finditer(text):
                found[rel] = match.group(1)
        for match in INDIRECT_FALLBACK.finditer(text):
            found[rel] = _resolve_constant(match.group(1), text)
    return found


def test_some_pack_declares_an_api_fallback_at_all() -> None:
    """The control for the test below.

    The check is a derivation over pack contents. If the derivation stops
    finding anything -- a renamed variable, a moved directory, a suffix list
    that no longer matches -- every per-pack assertion passes over an empty set
    and the suite reports that all fallbacks are correct because none was read.
    """
    total = {p: declared_api_fallbacks(p) for p in MAINTAINED_PACKS}
    assert any(total.values()), (
        "no maintained pack declares a GC_API_BASE_URL fallback, so the port "
        f"check below asserts nothing. Searched: {sorted(total)}"
    )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_pack_falls_back_to_the_port_this_gc_actually_serves(
    pack: str, tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    """A fallback pointing at a dead port is a broken install, not a default.

    Which port, and why it is not `[api] port`: gc has TWO API listeners. A
    standalone controller (`gc controller` / `gc serve`) binds `cfg.API.Port`,
    which `gc init` writes as 9443. A supervisor-managed city is reached on
    `cfg.Supervisor.PortOrDefault()` instead, 8372 when unset
    (`internal/api/effective_api_url.go`), and the two serve different route
    sets. Every URL these packs build is `/v0/city/{cityName}/...`, which is
    the supervisor's city-scoped set (`internal/api/supervisor_city_routes.go`,
    `internal/api/supervisor.go`). So the supervisor port is the one they must
    default to. `[api] port` is not dead config -- it is a different server,
    and a pack that defaults to it is addressing the wrong one.

    What this cannot do: no read-only `gc` command reports the resolved
    supervisor port in a city whose supervisor is not running, and starting one
    in a scratch city would contend for the port under test. So the expected
    value is pinned here rather than asked for, and the pin is cross-checked
    against a live answer whenever this runs somewhere a supervisor IS up. If
    gc moves the default and no live city is around to notice, this test keeps
    passing on the old value -- stated so nobody reads it as stronger than it
    is. Refute the pin with `gc dashboard --no-open` in a running city.
    """
    fallbacks = declared_api_fallbacks(pack)
    if not fallbacks:
        pytest.skip(f"{pack} hardcodes no API fallback")

    expected = EXPECTED_API_PORT

    # Opportunistic live rail: only when a supervisor is actually serving.
    imports, rig_imports = wiring(pack)
    workspace = write_city(tmp_path, imports, rig_imports)
    reported = gc_output(gc_test_bin, workspace, "dashboard", "--no-open")
    live = re.search(r"http://[\d.]+:(\d+)", reported)
    if live:
        assert live.group(1) == expected, (
            f"a running gc serves port {live.group(1)}, but this test pins "
            f"{expected}. gc moved the default; update EXPECTED_API_PORT and "
            f"every pack fallback with it."
        )

    wrong = {
        path: url
        for path, url in fallbacks.items()
        if urlsplit(url.rstrip("/")).port != int(expected)
    }
    assert not wrong, (
        f"{pack} falls back to a port gc does not serve (it serves {expected}). "
        f"Nothing sets GC_API_BASE_URL on a fresh install -- gc's own source "
        f"never sets it -- so these run against nothing:\n"
        + "\n".join(f"  {path} -> {url}" for path, url in sorted(wrong.items()))
    )


def test_the_detector_resolves_a_named_constant_default() -> None:
    """A control for the indirection, because the direct patterns would mask it.

    `oversight-rig` declares its API default ONLY as a named constant. If
    `_resolve_constant` regresses, this pack silently reverts to "declares no
    fallback" and its port check turns into a skip -- green, and measuring
    nothing. slack-full is the same shape and already did exactly that once.
    """
    fallbacks = declared_api_fallbacks("oversight-rig")
    assert fallbacks, (
        "oversight-rig declares an API default via a named constant; the "
        "detector no longer sees it, so its port check has become a skip"
    )
    assert all(
        url.startswith("http://") for url in fallbacks.values()
    ), f"a constant went unresolved: {fallbacks}"


def test_an_unresolvable_constant_fails_closed() -> None:
    """The blind spot must be loud. Proves the sentinel path still fails."""
    unresolved = _resolve_constant("NAME_THAT_IS_NOT_DEFINED", "x = 1\n")
    assert urlsplit(unresolved.rstrip("/")).port != int(EXPECTED_API_PORT), (
        "an unresolvable constant now satisfies the port check, so a fallback "
        "the detector cannot follow would pass as correct"
    )

@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_the_binding_a_pack_documents_is_the_one_its_instructions_use(pack: str) -> None:
    """A pack whose README and examples disagree is broken on its own happy path.

    gc registers a pack's verbs under the IMPORT KEY. Neither the pack directory
    nor `pack.toml [pack] name` participates, so a README that says
    `[imports.slack-full]` above 310 examples reading `gc slack ...` documents an
    install in which none of its own examples work. Found exactly that, live.

    Two shapes satisfy this, and the second is the better one:

    1. The README names one key and every instruction uses it.
    2. The README names no key (`gc <binding> ...` placeholders) and the pack
       hardcodes no literal, resolving the binding at runtime instead. This is
       the only shape that is correct for a user who binds the pack under a name
       of their own choosing, which gc allows and which nothing warns about.

    Why this is not merely untidy: the failure is silent. An unbound verb prints
    gc's root help and exits 0, so a user following the README sees help text
    rather than an error, and a test asserting on exit status sees green.
    """
    if not discover_command_words(pack_dir(pack)):
        # No commands means no verbs to bind, so there is no binding to get
        # wrong. Skipped rather than passed: a pack that LOSES its commands
        # would otherwise start passing this the moment it broke.
        pytest.skip(f"{pack} ships no commands, so no binding is under test")

    documented = readme_import_key(pack)
    instructed = instructed_bindings(pack)

    # A sibling pack's key is exempt only where that sibling SHIPS the verb it
    # is paired with -- "see `gc slack-mini post-message`" is a true statement
    # about slack-mini. Exempting the literal alone would let `gc slack-mini
    # bind-room`, which names a verb slack-mini does not have, ride through as a
    # cross-reference; the exemption has to be provenance-checked per pair.
    sibling_verbs = {
        (key, words[0])
        for other in MAINTAINED_PACKS
        if other != pack and (key := readme_import_key(other)) is not None
        for words in discover_command_words(pack_dir(other))
    }
    offenders = {
        pair: count
        for pair, count in instructed.items()
        if pair[0] != documented and pair not in sibling_verbs
    }

    if documented is None:
        # A pack claiming the placeholder shape has to be SHOWING placeholders.
        # Without this, a scan that matched nothing at all would read exactly
        # like a pack that correctly hardcodes nothing.
        readme = (pack_dir(pack) / "README.md").read_text(encoding="utf-8")
        assert re.search(r"\bgc <[a-z-]+>", readme), (
            f"{pack}/README.md documents no `[imports.<key>]` and shows no "
            f"`gc <binding> ...` placeholder either, so there is nothing telling "
            f"a user how to reach this pack's verbs -- and this guard would pass "
            f"it vacuously, having found no instruction to disagree with."
        )
        assert not offenders, (
            f"{pack}/README.md documents no import key -- it uses `gc <binding>` "
            f"placeholders, which is the shape that survives a user-chosen "
            f"binding -- but the pack still hardcodes {offenders}. Every one of "
            f"those is an instruction that fails for anyone who binds the pack "
            f"under any other name, and fails by printing gc's root help with "
            f"exit 0. Resolve the binding at runtime (see "
            f"factory-audit/assets/scripts/gc_binding.py) or document one key."
        )
        return

    # A documented key with no instruction found anywhere means the scan is
    # looking at the wrong thing, not that the pack is clean.
    assert instructed, (
        f"{pack}/README.md documents `[imports.{documented}]`, but no "
        f"`gc <literal> <verb>` instruction was found in the pack at all. The "
        f"derivation is broken or the verbs moved; either way this pack's "
        f"compliance here would be vacuous."
    )
    assert not offenders, (
        f"{pack}/README.md tells a user to install as `[imports.{documented}]`, "
        f"but the pack instructs {offenders}. Under the documented install those "
        f"commands do not exist, and gc answers them with its root help and exit "
        f"0 rather than an error. Either change the documented key or the "
        f"instructions -- whichever is the outlier; `pack.toml`'s own header "
        f"comment is usually the tiebreak, since it states the intended verb "
        f"surface."
    )


@pytest.mark.parametrize("pack", MAINTAINED_PACKS)
def test_the_documented_import_key_actually_resolves_the_packs_verbs(
    pack: str, tmp_path: Path, gc_test_bin: Path  # noqa: F811
) -> None:
    """The static check above, proven against the real binary, for EVERY verb.

    Compared against a CONTROL -- the same verb under a binding nothing was
    imported as -- rather than against gc's help text. Both invocations exit 0,
    so what a verb prints is the only thing separating resolved from unresolved,
    and pinning gc's root-help wording here would make this fail on an unrelated
    copy edit upstream.

    The control is itself checked: two DIFFERENT unimported bindings must print
    the same thing. That is what makes "unresolved" a stable signature rather
    than an accident of the particular name chosen, and it is the answer to
    "could both sides be equal for some reason other than the verb being
    unregistered?" -- if they could, these two would not agree either.
    """
    words = sorted(discover_command_words(pack_dir(pack)))
    if not words:
        pytest.skip(f"{pack} ships no commands, so no binding is under test")

    # A pack using the placeholder shape has no documented key by design; any
    # key must work, which is the property being asserted.
    binding = readme_import_key(pack) or "chosen-by-the-operator"
    workspace = write_city(tmp_path, {binding: pack_dir(pack)})

    probe = words[0]
    unbound = gc_output(
        gc_test_bin, workspace, "a-binding-nothing-was-imported-as", *probe, "--help"
    )
    also_unbound = gc_output(
        gc_test_bin, workspace, "another-unimported-binding", *probe, "--help"
    )
    assert unbound == also_unbound, (
        "two different unimported bindings printed different things, so "
        "'prints the same as an unimported binding' is not a reliable signature "
        "for an unregistered verb and every assertion below rests on it"
    )

    unresolved = sorted(
        verb
        for verb in words
        if gc_output(gc_test_bin, workspace, binding, *verb, "--help") == unbound
    )
    assert not unresolved, (
        f"installed exactly as {pack}/README.md instructs "
        f"(`[imports.{binding}]`), {len(unresolved)} of {len(words)} verbs "
        f"printed the same thing as a binding nothing was imported as: "
        f"{[' '.join(v) for v in unresolved]}. Those verbs are not registered, "
        f"and gc reports that by printing its root help and exiting 0 -- there "
        f"is no error to notice."
    )
