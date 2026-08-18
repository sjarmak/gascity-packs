#!/usr/bin/env bash
# gc <binding> factory audit — run the rule catalog against your contract.
#
# Reads the contract you maintain (default <city>/.gc/factory-audit/factory.yaml)
# and reports FAIL and WARN findings. This is the check that answers "is what we
# say we do internally consistent and safe" — it does not look at the city.
#
# It will not tell you whether the contract is TRUE. `gc factory reconcile`
# does that, and a green audit over a contract nobody derived is worth nothing.
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc factory audit: missing Gas City pack context" >&2
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
strict=()

while [ $# -gt 0 ]; do
  case "$1" in
    --contract) need_operand "$@"; contract=$2; shift ;;
    --strict) strict=(--strict) ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "gc factory audit: unknown argument $1" >&2; exit 64 ;;
  esac
  shift
done

kit_require

if [ ! -f "$contract" ]; then
  cat >&2 <<MSG
gc factory audit: no contract at $contract

Start from what your city actually does rather than from a blank file:

  gc ${GC_PACK_NAME:-factory-audit} factory setup
  gc ${GC_PACK_NAME:-factory-audit} factory derive
  cp $out/factory.derived.yaml $contract

Then edit it. The derived file records what the code does today, including the
parts you are not happy with; the contract is what you are willing to stand
behind, and reconcile is where the difference shows up.
MSG
  exit 2
fi

mkdir -p "$out"
kit_banner
printf 'contract: %s\n\n' "$contract"

# The kit exits nonzero on FAIL. That is the useful behaviour for an order, so
# let it through rather than swallowing it into a summary line.
set +e
kit_run review "$contract" --out "$out" "${strict[@]+"${strict[@]}"}" | tee "$out/audit.txt"
# One statement. Reading ${PIPESTATUS[0]} into a variable is itself a command,
# and it replaces PIPESTATUS -- so a second line reading ${PIPESTATUS[1]} aborts
# under `set -u` instead of reporting the pipe's status.
pipe=("${PIPESTATUS[@]}")
status=${pipe[0]}
wrote=${pipe[1]}
set -e

# A full disk fails `tee` while the checker succeeds. Announcing the report
# anyway sends someone to read a file that is missing or truncated, and the
# command that told them it existed exited 0.
if [ "$wrote" -ne 0 ]; then
  printf '\ngc factory audit: could not write %s (tee exited %d)\n' \
    "$out/audit.txt" "$wrote" >&2
  exit 5
fi
printf '\nwrote %s and %s\n' "$out/audit.txt" "$out/findings.json"
exit "$status"
