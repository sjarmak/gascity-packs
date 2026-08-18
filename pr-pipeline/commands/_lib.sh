#!/bin/sh
# Shared helpers for the pr-pipeline verb wrappers. This file is SOURCED by
# the four run.sh scripts, never run as a command: it is not a directory
# holding a run.sh, so gc does not expose it as a verb.
#
# It exists because the alternative is four copies of gc_binding() in four
# scripts that must not drift, and because the "run --help" hint below has to
# read the same on every failure or it is a hint about which error path the
# author happened to be looking at.

# gc_binding prints the word a user types after `gc` to reach this pack, or
# the literal `<binding>` when that cannot be determined. See
# assets/scripts/gc_binding.py for why a placeholder beats a guess.
gc_binding() {
    if _gc_binding_name=$(python3 "$GC_PACK_DIR/assets/scripts/gc_binding.py" 2>/dev/null) \
       && [ -n "$_gc_binding_name" ]; then
        printf '%s' "$_gc_binding_name"
    else
        printf '<binding>'
    fi
}

# pr_help VERB — print a verb's help.md with the binding filled in.
#
# The help files are written with the literal `gc <binding> pr ...` so they
# read correctly as source, and the placeholder is replaced here at print
# time. Only that one token is substituted; the `<scope>`, `<issue-number>`
# and `<pr-number-or-url>` placeholders in the same files are left alone.
pr_help() {
    sed 's/<binding>/'"$(gc_binding)"'/g' "$GC_PACK_DIR/commands/pr/$1/help.md"
}

# pr_die VERB MESSAGE [EXIT] — report which command failed, then say how to
# read its help.
#
# The message deliberately does NOT start with `gc `: it names the failing
# command rather than something to type, and after that rule any `gc ` this
# pack prints is an instruction and has to carry the binding. The hint is the
# instruction, and it is printed on every failure rather than on the ones
# whose text happens to look like a usage error.
pr_die() {
    _pr_verb="$1"
    shift
    echo "pr-pipeline pr $_pr_verb: $1" >&2
    pr_hint "$_pr_verb"
    exit "${2:-2}"
}

# pr_hint VERB — the "how to read the help" line on its own, for the one
# failure that prints an explanation between the message and the hint. It is a
# function rather than a second copy of the string so the two cannot drift.
pr_hint() {
    echo "Run: gc $(gc_binding) pr $1 --help" >&2
}
