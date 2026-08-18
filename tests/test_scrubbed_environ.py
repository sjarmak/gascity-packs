"""The scratch-city harness must ask the same question whoever runs it.

`scrubbed_environ` is the reason a suite run inside a live Gas City agent gets
the same answer as a run on a clean CI machine. It has already been the
difference between green and red twice, in opposite directions:

  * `slack-full`'s `doctor/check-env.sh` found this operator's real
    `~/.config/gc-slack-adapter/env` through an inherited `XDG_CONFIG_HOME` and
    passed locally, while CI reported `slack-full:env`.
  * `gascity/commands/claim/run.sh` takes `EXPECTED_ROUTE` from `GC_TEMPLATE`.
    Inside a live agent that is the agent's own template rather than the
    fixture's, so the claim is rejected on a route mismatch:
    `test_registered_claim_command_dispatches_store_aware_show_and_normalizes_json`
    was green on CI and red on every machine that had a city on it.

Both directions matter, which is why this sets the variables itself rather than
reading whatever the runner happens to have. A test that only fails on the
maintainer's laptop is not a guard; it is a coincidence with good timing.
"""

from pathlib import Path

from gc_test_env import scrubbed_environ

# One per prefix the helper strips, each a variable that actually steers
# behaviour rather than a synthetic name: BEADS_DOLT_SERVER_PORT overrides a
# city's own metadata.json, GC_TEMPLATE decides a claim's expected route, and
# XDG_CONFIG_HOME beats a pinned HOME for any pack reading config portably.
LEAKS = {
    "GC_TEMPLATE": "mayor",
    "GC_SESSION_NAME": "mayor",
    "BEADS_DOLT_SERVER_PORT": "29620",
    "XDG_CONFIG_HOME": "/etc/somewhere-real",
}


def test_a_live_city_environment_does_not_reach_the_scratch_city(
    monkeypatch, tmp_path: Path
) -> None:
    for key, value in LEAKS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    env = scrubbed_environ(tmp_path)

    leaked = {k: env[k] for k, v in LEAKS.items() if env.get(k) == v}
    assert not leaked, (
        f"these reached the scratch city unchanged: {leaked}. Every one of them "
        f"makes the suite's answer depend on who ran it."
    )
    assert env["HOME"] == str(tmp_path)
    assert env["XDG_CONFIG_HOME"] == str(tmp_path / ".config")
    # Unrelated variables are the point of inheriting at all -- a scratch city
    # with no PATH runs nothing.
    assert env["PATH"] == "/usr/bin:/bin"


def test_the_xdg_set_is_redirected_whole(monkeypatch, tmp_path: Path) -> None:
    """DATA/STATE/CACHE override HOME the same way CONFIG does.

    Pinning only XDG_CONFIG_HOME would leave three doors open, and the failure
    it produces is a pack reading the operator's real state directory while
    every assertion in the suite still passes.
    """
    for key in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, "/etc/somewhere-real")

    env = scrubbed_environ(tmp_path)

    assert env["XDG_DATA_HOME"] == str(tmp_path / ".local" / "share")
    assert env["XDG_STATE_HOME"] == str(tmp_path / ".local" / "state")
    assert env["XDG_CACHE_HOME"] == str(tmp_path / ".cache")
