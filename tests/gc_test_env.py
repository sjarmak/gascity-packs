"""The environment a scratch city gets, with the caller's own city kept out.

Its own module rather than a function in `gc_live_city`, because that module
runs a real `gc` and every file importing it is inferred to need one
(`test_ci_runs_every_pack_suite.py`). This function needs nothing but
`os.environ`, and declaring otherwise to quiet an over-reporting inference
would put a false statement in the tree to make a check go green.
"""

from __future__ import annotations

import os
from pathlib import Path


def scrubbed_environ(home: Path) -> dict[str, str]:
    """The caller's environment with everything that could reach a real city out.

    Strip the caller's Gas City and beads variables rather than inheriting
    them. `BEADS_DOLT_SERVER_PORT` in particular overrides what a city's own
    metadata names, so a developer running this suite inside a live city would
    have these scratch invocations reach that city's canonical store.

    The `GC_` half is not only about writes. `GC_TEMPLATE` and `GC_SESSION_NAME`
    are read by pack code as the identity of the running seat, so a suite that
    inherits them is asking a different question depending on who ran it:
    `gascity/commands/claim/run.sh` takes `EXPECTED_ROUTE` from `GC_TEMPLATE`,
    and inside a live agent that is the agent's own template rather than the
    fixture's, which rejects the claim under a route mismatch. Green on CI, red
    on the machine that has the city.

    Pinning HOME is not enough. Pack code that resolves config the portable way
    reads `${XDG_CONFIG_HOME:-$HOME/.config}`, and a set XDG_CONFIG_HOME beats
    the pinned HOME, so the scratch city reads the developer's real dotfiles.
    Caught by CI, not locally: `slack-full`'s doctor/check-env.sh found this
    operator's ~/.config/gc-slack-adapter/env and passed here, while a clean
    runner with no such file reported `slack-full:env`. Redirect the whole XDG
    set, since data/state/cache override HOME identically.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GC_", "BEADS_", "XDG_"))
    }
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
        }
    )
    return env
