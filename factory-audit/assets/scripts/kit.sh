#!/usr/bin/env bash
# Resolve the reliability kit this pack runs against, and say which one it is.
#
# Sourced by every command in the pack. Sets KIT_DIR and KIT_ACTUAL_COMMIT, or
# exits non-zero with an instruction. It never installs anything: `gc factory
# setup` is the only thing that writes, so a scheduled order can never
# silently pull code onto the machine.

set -euo pipefail

PACK_DIR=${GC_PACK_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}

# shellcheck disable=SC1091
. "$PACK_DIR/kit.pin"

kit_default_dir() {
  printf '%s\n' "${GC_CITY_PATH:-$PWD}/.gc/factory-kit"
}

# Where the kit is, in precedence order. An operator override wins so you can
# point the pack at a checkout you are editing; that is the whole reason the
# env var exists, and the commit report below is what keeps it honest.
kit_resolve() {
  if [ -n "${FACTORY_KIT_HOME:-}" ]; then
    printf '%s\n' "$FACTORY_KIT_HOME"
    return 0
  fi
  kit_default_dir
}

kit_require() {
  KIT_DIR=$(kit_resolve)
  if [ ! -f "$KIT_DIR/src/factory_check.py" ]; then
    cat >&2 <<MSG
factory-audit: no reliability kit at $KIT_DIR

  Run:  gc factory setup

  That clones $KIT_REPO at the commit pinned in the pack (kit.pin) into the
  city, once. Nothing else in this pack writes to disk or reaches the network.
  To use a checkout you already have, set FACTORY_KIT_HOME to its root.
MSG
    return 2
  fi
  KIT_ACTUAL_COMMIT=$(git -C "$KIT_DIR" rev-parse HEAD 2>/dev/null || printf 'unknown')
  # The checker is executed from the working tree, so the commit alone does not
  # identify what ran. A tree edited at the pinned commit reported "(pinned)"
  # until this was added, which made the pin a decoration rather than a claim.
  if [ -n "$(git -C "$KIT_DIR" status --porcelain 2>/dev/null)" ]; then
    KIT_TREE_STATE=modified
  else
    KIT_TREE_STATE=clean
  fi
  KIT_IS_OVERRIDE=$([ -n "${FACTORY_KIT_HOME:-}" ] && printf yes || printf no)
  export KIT_DIR KIT_ACTUAL_COMMIT KIT_TREE_STATE KIT_IS_OVERRIDE
}

# Print which kit actually ran, on every command, and say so when it is not the
# pinned one. A drift line in the output is the point: a report that does not
# name its own checker is a report you cannot reproduce.
kit_banner() {
  if [ "$KIT_ACTUAL_COMMIT" = "$KIT_COMMIT" ] \
     && [ "$KIT_TREE_STATE" = clean ] && [ "$KIT_IS_OVERRIDE" = no ]; then
    printf 'kit %s (pinned) at %s\n' "${KIT_COMMIT:0:12}" "$KIT_DIR"
    return 0
  fi

  printf 'kit %s at %s\n' "${KIT_ACTUAL_COMMIT:0:12}" "$KIT_DIR"
  if [ "$KIT_IS_OVERRIDE" = yes ]; then
    printf 'DRIFT: FACTORY_KIT_HOME is set, so the pack pin (%s) is not enforced\n' \
      "${KIT_COMMIT:0:12}"
  elif [ "$KIT_ACTUAL_COMMIT" != "$KIT_COMMIT" ]; then
    printf 'DRIFT: pack pins %s; this checkout is %s\n' \
      "${KIT_COMMIT:0:12}" "${KIT_ACTUAL_COMMIT:0:12}"
  fi
  if [ "$KIT_TREE_STATE" = modified ]; then
    printf 'DRIFT: the checkout has local modifications; what ran is not any commit\n'
  fi
}

kit_run() {
  python3 "$KIT_DIR/src/factory_check.py" "$@"
}
