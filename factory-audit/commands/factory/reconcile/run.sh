#!/usr/bin/env bash
# gc <binding> factory reconcile — check the contract against the installation.
#
# This is the command that can catch you lying to yourself. `factory audit`
# reads only the contract, so a contract that says every effect is idempotent
# scores perfectly whether or not that is true. Reconcile runs the probes
# against the real tree and reports, per effect:
#
#   DRIFT        the contract claims an identity the call sites do not carry
#   UNDECLARED   the installation performs an effect the contract omits
#   unverified   the contract says nothing, but the call sites do carry one
#   confirmed    contract and call sites agree
#   open         neither the contract nor the code settles it
#
# Exits nonzero on DRIFT or UNDECLARED. Those are the two that mean the
# document is wrong, and a document that is wrong about safety is worse than
# no document.
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc factory reconcile: missing Gas City pack context" >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$GC_PACK_DIR/assets/scripts/kit.sh"

need_operand() {
  # Under `set -u` a bare $2 aborts with bash's own message and exit 1, so a
  # typo in a flag reads as an internal error rather than as bad input.
  if [ "$#" -lt 2 ]; then
    printf '%s: %s needs a value\n' "$0" "$1" >&2
    exit 64
  fi
}


city=${GC_CITY_PATH:-$PWD}
out="$city/.gc/factory-audit"
contract="$out/factory.yaml"
probes="$out/probes.yaml"

while [ $# -gt 0 ]; do
  case "$1" in
    --contract) need_operand "$@"; contract=$2; shift ;;
    --probes) need_operand "$@"; probes=$2; shift ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "gc factory reconcile: unknown argument $1" >&2; exit 64 ;;
  esac
  shift
done

kit_require

for f in "$contract" "$probes"; do
  if [ ! -f "$f" ]; then
    printf 'gc factory reconcile: missing %s\n\n' "$f" >&2
    printf 'Run `gc %s factory derive` first; it writes the probe pack and a\n' \
      "${GC_PACK_NAME:-factory-audit}" >&2
    printf 'derived contract you can start from.\n' >&2
    exit 2
  fi
done

mkdir -p "$out"
kit_banner
printf 'contract: %s\nprobes:   %s\n\n' "$contract" "$probes"

set +e
kit_run reconcile "$contract" "$city" --probes "$probes" | tee "$out/reconcile.txt"
# One statement. Reading ${PIPESTATUS[0]} into a variable is itself a command,
# and it replaces PIPESTATUS -- so a second line reading ${PIPESTATUS[1]} aborts
# under `set -u` instead of reporting the pipe's status.
pipe=("${PIPESTATUS[@]}")
status=${pipe[0]}
wrote=${pipe[1]}
set -e

if [ "$wrote" -ne 0 ]; then
  printf '\ngc factory reconcile: could not write %s (tee exited %d)\n' \
    "$out/reconcile.txt" "$wrote" >&2
  exit 5
fi
printf '\nwrote %s\n' "$out/reconcile.txt"
exit "$status"
