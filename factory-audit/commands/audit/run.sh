#!/usr/bin/env bash
# gc <binding> audit — run the rule catalog against your contract.
#
# Reads the contract you maintain (default <city>/.gc/factory-audit/factory.yaml)
# and reports FAIL and WARN findings. This is the check that answers "is what we
# say we do internally consistent and safe" — it does not look at the city.
#
# It cannot tell you whether the contract is TRUE. `gc <binding> reconcile`
# does that, and it leaves a receipt behind; this command reads that receipt and
# states, above the score, whether the score has been checked against the code:
# NONE, STALE, DRIFTED, ERRORED, VACUOUS or CONFIRMED. A DRIFTED contract exits
# 4 however clean the findings are, because a perfect score over a document the
# code contradicts is the failure this pack exists to catch. VACUOUS is the
# quieter version of the same trap: reconcile ran, contradicted nothing, and
# confirmed nothing either, because the contract left every effect undecided.
#
#   --strict            treat WARN findings as failures
#   --require-verified  also exit 4 when the contract has never been reconciled,
#                       or was edited since it last was
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "factory-audit audit: missing Gas City pack context" >&2
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
require_verified=no

while [ $# -gt 0 ]; do
  case "$1" in
    --contract) need_operand "$@"; contract=$2; shift ;;
    --strict) strict=(--strict) ;;
    --require-verified) require_verified=yes ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "factory-audit audit: unknown argument $1" >&2; exit 64 ;;
  esac
  shift
done

kit_require

if [ ! -f "$contract" ]; then
  cat >&2 <<MSG
factory-audit audit: no contract at $contract

Start from what your city actually does rather than from a blank file:

  gc $(gc_binding) setup
  gc $(gc_binding) derive
  cp $out/factory.derived.yaml $contract

Then edit it. The derived file records what the code does today, including the
parts you are not happy with; the contract is what you are willing to stand
behind, and reconcile is where the difference shows up.
MSG
  exit 2
fi

mkdir -p "$out"

# Read the receipt BEFORE the score is printed. A reader who sees the number
# first has already formed a view of it, and the whole point of this line is
# that the number does not mean what it appears to mean until reconcile has run.
state=$(receipt_state "$out" "$contract")
receipt=$(receipt_path "$out")
when=""
if [ -f "$receipt" ]; then
  when=$(receipt_field "$receipt" checked_at)
fi

print_verification() {
  case "$state" in
    none)
      printf 'verification: NONE. Nothing has checked this contract against your code.\n'
      printf '              The score below is a property of the document alone.\n'
      printf '              Run: gc %s reconcile\n' "$(gc_binding)"
      ;;
    stale)
      printf 'verification: STALE. The contract or the probe pack changed after the\n'
      printf '              last reconcile (%s), so that result no longer applies.\n' "${when:-unknown}"
      printf '              Run: gc %s reconcile\n' "$(gc_binding)"
      ;;
    drifted)
      printf 'verification: DRIFTED. The last reconcile (%s) found the installation\n' "${when:-unknown}"
      printf '              contradicts this contract. Read %s.\n' "$out/reconcile.txt"
      ;;
    errored)
      printf 'verification: ERRORED. The last reconcile (%s) did not complete, so\n' "${when:-unknown}"
      printf '              nothing here has been compared against the code.\n'
      printf '              Run: gc %s reconcile\n' "$(gc_binding)"
      ;;
    vacuous)
      # The breakdown rather than a summary word, because the two ways to reach
      # zero confirmed want different work: an effect left undecided in the
      # contract is yours to decide, and one the probes could not settle is a
      # gap in what this pack can see. Reporting "undecided" for both sends
      # half the readers to edit a file that is already correct.
      printf 'verification: VACUOUS. The last reconcile (%s) contradicted nothing\n' "${when:-unknown}"
      printf '              and confirmed nothing: 0 of %s declared effects\n' \
        "$(receipt_field "$receipt" declared)"
      printf '              confirmed, %s undecided in the contract, %s the\n' \
        "$(receipt_field "$receipt" open)" "$(receipt_field "$receipt" unverified)"
      printf '              probes could not settle.\n'
      printf '              A clean exit over a contract that asserts nothing\n'
      printf '              checkable is not evidence. Read %s.\n' "$out/reconcile.txt"
      ;;
    confirmed)
      printf 'verification: CONFIRMED. Reconciled against %s at %s, no drift.\n' \
        "$(receipt_field "$receipt" installation)" "${when:-unknown}"
      ;;
  esac
}

kit_banner
printf 'contract: %s\n' "$contract"
print_verification
printf '\n'

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
  printf '\nfactory-audit audit: could not write %s (tee exited %d)\n' \
    "$out/audit.txt" "$wrote" >&2
  exit 5
fi
printf '\nwrote %s and %s\n' "$out/audit.txt" "$out/findings.json"

# Repeated after the score, not only above it. The summary line is the part
# people quote, and a clean one quoted without this sentence is the exact claim
# this pack tells other people not to make.
print_verification
if [ "$state" = drifted ] && [ "$status" -eq 0 ]; then
  printf '\nfactory-audit audit: clean findings over a contract the installation\n' >&2
  printf 'contradicts. Exiting 4; reconcile is the command that clears this.\n' >&2
  status=4
elif [ "$require_verified" = yes ] && [ "$status" -eq 0 ] \
     && [ "$state" != confirmed ]; then
  printf '\nfactory-audit audit: --require-verified and the contract is %s.\n' "$state" >&2
  printf 'Exiting 4.\n' >&2
  status=4
fi
exit "$status"
