#!/usr/bin/env bash
# gc <binding> factory derive — read this installation and write what it does.
#
# Two steps, both read-only against the city:
#
#   probes-init   scan the tree for outbound-effect call sites and scaffold a
#                 probe pack naming where each effect is performed
#   infer         run those probes and report, per effect, whether the call
#                 sites actually carry an identity a retry could dedupe on
#
# The output is a description of the installation, not a decision about it.
# `gc factory reconcile` is what compares it to a contract you wrote.
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc factory derive: missing Gas City pack context" >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$GC_PACK_DIR/assets/scripts/kit.sh"
kit_require

city=${GC_CITY_PATH:-$PWD}
out="$city/.gc/factory-audit"
probes="$out/probes.yaml"
rewrite=0
extra=()

while [ $# -gt 0 ]; do
  case "$1" in
    --rewrite-probes) rewrite=1 ;;
    --exclude) extra+=(--exclude "$2"); shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "gc factory derive: unknown argument $1" >&2; exit 64 ;;
  esac
  shift
done

mkdir -p "$out"
kit_banner

# A probe pack is a starting point that gets HAND-EDITED: the scaffold finds
# candidate call sites and guesses the flag that would carry an identity, and
# only a person can say which guesses are right. So it is written once and then
# left alone. Overwriting it on every run would silently discard that work,
# which is the whole reason --rewrite-probes has to be asked for.
if [ ! -f "$probes" ] || [ "$rewrite" -eq 1 ]; then
  if [ -f "$probes" ]; then
    cp "$probes" "$probes.$(date -u +%Y%m%dT%H%M%SZ).bak"
    printf 'kept your previous probes.yaml alongside the new one (.bak)\n'
  fi
  kit_run probes-init "$city" --write "$probes" "${extra[@]+"${extra[@]}"}"
else
  printf 'probes: %s (kept; --rewrite-probes to re-scaffold)\n' "$probes"
fi

kit_run infer "$city" --probes "$probes" \
  --out "$out" --write "$out/factory.derived.yaml" | tee "$out/derived.txt"

cat <<MSG

wrote $out/factory.derived.yaml   what this installation actually does
      $out/evidence.json          the call sites behind every line of it
      $out/derived.txt            the same reading in prose

The derived contract is a description, not a target. Copy the lines you agree
with into your own factory.yaml, argue with the ones you do not, then run
  gc ${GC_PACK_NAME:-factory-audit} factory reconcile
to see where the two disagree.
MSG
