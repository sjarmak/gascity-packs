#!/usr/bin/env bash
# Order body: reconcile the contract against the installation, and report.
#
# Deliberately NOT `factory audit`. Audit reads the contract alone, so it
# reports the same findings every run until someone edits a document — a
# scheduled version of that is a reminder, not a check. Reconcile reads the
# code, so its result changes when the code changes, which is the only thing
# worth waking up for.
#
# Exits nonzero when the contract has gone out of date with the installation.
# gc surfaces that as an actionable order result; nothing here posts, files, or
# pushes anything.

set -euo pipefail

PACK_DIR=${GC_PACK_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}
# shellcheck disable=SC1091
. "$PACK_DIR/assets/scripts/kit.sh"

city=${GC_CITY_PATH:-$PWD}
out="$city/.gc/factory-audit"

# Not set up, or never derived, is not a drift finding. Say so and stay green:
# an order that goes red because a human has not run a one-time command trains
# people to ignore it.
if ! kit_require 2>/dev/null; then
  printf 'factory-audit: kit not installed; run `gc factory setup` to enable this check\n'
  exit 0
fi
if [ ! -f "$out/factory.yaml" ] || [ ! -f "$out/probes.yaml" ]; then
  printf 'factory-audit: no contract yet; run `gc factory derive` to enable this check\n'
  exit 0
fi

kit_banner

# `set -e` with pipefail exits on the failing pipeline before any line after it
# runs, so the explicit propagation this used to end with was unreachable. It
# happened to produce the right status while `tee` succeeded, which is the kind
# of accident that survives until the day it does not.
set +e
kit_run reconcile "$out/factory.yaml" "$city" --probes "$out/probes.yaml" \
  | tee "$out/reconcile.txt"
# One statement. Reading ${PIPESTATUS[0]} into a variable is itself a command,
# and it replaces PIPESTATUS -- so a second line reading ${PIPESTATUS[1]} aborts
# under `set -u` instead of reporting the pipe's status.
pipe=("${PIPESTATUS[@]}")
status=${pipe[0]}
wrote=${pipe[1]}
set -e

if [ "$wrote" -ne 0 ]; then
  printf 'factory-audit: could not write %s (tee exited %d)\n' \
    "$out/reconcile.txt" "$wrote" >&2
  exit 5
fi
exit "$status"
