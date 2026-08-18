#!/usr/bin/env bash
# Resolve the reliability kit this pack runs against, and say which one it is.
#
# Sourced by every command in the pack. Sets KIT_DIR and KIT_ACTUAL_COMMIT, or
# exits non-zero with an instruction. It never installs anything: `gc <binding>
# factory setup` is the only thing that writes, so a scheduled order can never
# silently pull code onto the machine.

set -euo pipefail

PACK_DIR=${GC_PACK_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}

# shellcheck disable=SC1091
. "$PACK_DIR/kit.pin"

# The word a user types after `gc` to reach this pack. gc sets GC_PACK_NAME to
# the PACK's name and exposes nothing carrying the BINDING, so a pack bound as
# `[imports.fa]` was told to run `gc factory-audit factory setup`, which exits
# with `unknown command`. Recovered from the city's pack.toml, with the README's
# placeholder as the answer when it cannot be determined. See gc_binding.py.
gc_binding() {
  local name
  if name=$(python3 "$PACK_DIR/assets/scripts/gc_binding.py" 2>/dev/null) \
     && [ -n "$name" ]; then
    printf '%s' "$name"
  else
    printf '<binding>'
  fi
}

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

  Run:  gc $(gc_binding) factory setup

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

# --- verification receipt ----------------------------------------------------
#
# `factory audit` scores the contract and cannot tell whether the contract is
# TRUE; only reconcile reads the code. The two commands run at different times,
# often by different people, so audit needs a durable record of what the last
# reconcile said about THIS contract. That record is this file.
#
# It stores digests, not paths. The question audit asks is whether the document
# that was checked is the document being scored, and editing the contract after
# a clean reconcile is exactly the case that must stop reading as verified.

file_digest() {
  if [ ! -f "$1" ]; then
    printf 'missing'
    return 0
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    printf 'unhashable'
  fi
}

receipt_path() {
  printf '%s\n' "$1/reconcile.receipt"
}

receipt_field() {
  # Parsed, never sourced. The file lives in the city and a `key=$(rm ...)`
  # line in it would execute on the next audit if this were a `.` include.
  sed -n "s/^$2=//p" "$1" | sed -n 1p
}

receipt_write() {
  local out=$1 contract=$2 probes=$3 installation=$4 status=$5
  local tmp="$out/.reconcile.receipt.$$"
  {
    printf 'receipt_version=1\n'
    printf 'checked_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'kit_commit=%s\n' "${KIT_ACTUAL_COMMIT:-unknown}"
    printf 'kit_tree=%s\n' "${KIT_TREE_STATE:-unknown}"
    printf 'installation=%s\n' "$installation"
    printf 'contract_path=%s\n' "$contract"
    printf 'contract_sha256=%s\n' "$(file_digest "$contract")"
    printf 'probes_path=%s\n' "$probes"
    printf 'probes_sha256=%s\n' "$(file_digest "$probes")"
    printf 'status=%s\n' "$status"
  } >"$tmp"
  mv -f "$tmp" "$(receipt_path "$out")"
}

# One of: none stale drifted errored confirmed.
#
# `stale` covers every way "this reading no longer applies": the contract
# changed, the probe pack that decided what reconcile could see changed, or the
# checker that produced the reading is not the one installed now. A receipt
# whose digests cannot be computed is stale too, because an unverifiable receipt
# and a verified contract must never produce the same word.
#
# What it is NOT: an attestation. The receipt sits in the city and anything that
# can write the city can write it, so a forged CONFIRMED is available to anyone
# who could equally have edited the contract itself. There is no key this pack
# could hold that the same actor could not read. It is a record of what the last
# reconcile found, and it is worth exactly what the rest of the city's `.gc`
# directory is worth.
receipt_state() {
  local out=$1 contract=$2 receipt want got probes
  receipt=$(receipt_path "$out")
  if [ ! -f "$receipt" ]; then
    printf 'none\n'
    return 0
  fi
  want=$(receipt_field "$receipt" contract_sha256)
  got=$(file_digest "$contract")
  if [ "$got" = missing ] || [ "$got" = unhashable ] || [ "$want" != "$got" ]; then
    printf 'stale\n'
    return 0
  fi
  probes=$(receipt_field "$receipt" probes_path)
  if [ -n "$probes" ] \
     && [ "$(receipt_field "$receipt" probes_sha256)" != "$(file_digest "$probes")" ]; then
    printf 'stale\n'
    return 0
  fi
  # The checker that produced the reading has to be the one installed now. Its
  # rules and its probers both decide what reconcile was able to see, so a pin
  # move ages a reading exactly the way a probe-pack edit does. Recording this
  # field and never reading it left a guard that could not go red, which is the
  # shape of every check in this pack that turned out to be decoration.
  #
  # The tree state is deliberately NOT part of this. An operator pointing
  # FACTORY_KIT_HOME at a checkout they are editing is the documented workflow;
  # holding that permanently STALE would report the workflow as a fault and bury
  # the signal, and the banner already names a modified checkout on every run.
  if [ "$(receipt_field "$receipt" kit_commit)" != "${KIT_ACTUAL_COMMIT:-unknown}" ]; then
    printf 'stale\n'
    return 0
  fi
  case "$(receipt_field "$receipt" status)" in
    0) printf 'confirmed\n' ;;
    1) printf 'drifted\n' ;;
    *) printf 'errored\n' ;;
  esac
}
