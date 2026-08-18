#!/usr/bin/env bash
# gc <binding> instruments check — audit instruments against the contract.
#
# With no arguments this audits the city's whole enabled-order population,
# which is the standing reading. With paths, it audits exactly those files,
# which is what you want in a pre-commit or on a branch.
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc instruments check: missing Gas City pack context" >&2
  exit 1
fi

checker="$GC_PACK_DIR/assets/scripts/instrument-contract-check"
if [ ! -f "$checker" ]; then
  echo "gc instruments check: checker missing at $checker" >&2
  exit 1
fi

export GC_CITY_PATH="${GC_CITY_PATH:-$PWD}"

if [ "$#" -eq 0 ]; then
  exec python3 "$checker" --enabled-local-orders
fi

exec python3 "$checker" "$@"
