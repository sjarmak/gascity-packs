"""Print the word a user types after `gc` to reach this pack, or nothing.

Gas City hands a pack command GC_PACK_NAME, which is the PACK's own name, and
nothing that carries the BINDING -- the key under `[imports.<name>]` in the
city's pack.toml. Those are the same word only when the operator happened to
bind the pack under its own name. Every message this pack printed telling a
user to "run gc factory-audit factory setup" was therefore a command that
errors with `unknown command` for anyone who bound it as anything else.

So the binding is recovered from the city's own pack.toml: the import whose
source resolves to GC_PACK_DIR. Exactly one match is an answer. Zero (the pack
is reached some other way) or several (bound twice) is not, and this prints
nothing and exits 1 so the caller can fall back to the `<binding>` placeholder
the README uses. A guess would be worse than the placeholder: a placeholder is
visibly a placeholder, and a wrong concrete name is not.

Environment: GC_CITY_PATH, GC_PACK_DIR (both set by gc).
Exit: 0 printed one binding; 1 could not determine exactly one.
"""

from __future__ import annotations

import os
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11: no parser, so no answer.
    sys.exit(1)


def import_tables(manifest: dict) -> list[dict]:
    """City-scoped and rig-scoped import tables, whichever are present.

    A pack bound only at rig scope is still reached by its rig-scoped name, and
    its instructions are just as wrong, so both are read.
    """
    tables = [manifest.get("imports")]
    rigs = manifest.get("rigs")
    if isinstance(rigs, dict):
        tables.append(rigs.get("imports"))
    return [table for table in tables if isinstance(table, dict)]


def bindings_for(manifest: dict, city: str, pack_dir: str) -> set[str]:
    """Import names whose source resolves to `pack_dir`.

    Sources are resolved against the city, because that is what a real pack.toml
    mostly holds, and realpath is applied to both sides so a symlinked checkout
    or a trailing slash does not read as a different pack.
    """
    want = os.path.realpath(pack_dir)
    names = set()
    for table in import_tables(manifest):
        for name, entry in table.items():
            source = entry.get("source") if isinstance(entry, dict) else None
            if not isinstance(source, str):
                continue
            resolved = os.path.realpath(
                os.path.join(city, os.path.expanduser(source))
            )
            if resolved == want:
                names.add(name)
    return names


def main() -> int:
    city = os.environ.get("GC_CITY_PATH") or ""
    pack_dir = os.environ.get("GC_PACK_DIR") or ""
    if not city or not pack_dir:
        return 1
    try:
        with open(os.path.join(city, "pack.toml"), "rb") as handle:
            manifest = tomllib.load(handle)
    except (OSError, ValueError):
        return 1
    if not isinstance(manifest, dict):
        return 1

    names = bindings_for(manifest, city, pack_dir)
    # A pack bound twice has two correct answers and no way to pick between
    # them, so it gets the placeholder rather than whichever one sorted first.
    if len(names) != 1:
        return 1
    print(next(iter(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
