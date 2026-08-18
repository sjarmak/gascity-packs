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
kit_require

city=${GC_CITY_PATH:-$PWD}
out="$city/.gc/factory-audit"
contract="$out/factory.yaml"
strict=()

while [ $# -gt 0 ]; do
  case "$1" in
    --contract) contract=$2; shift ;;
    --strict) strict=(--strict) ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "gc factory audit: unknown argument $1" >&2; exit 64 ;;
  esac
  shift
done

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
status=${PIPESTATUS[0]}
set -e
printf '\nwrote %s and %s\n' "$out/audit.txt" "$out/findings.json"
exit "$status"
