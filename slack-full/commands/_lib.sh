# Shared helpers for slack-full's 26 command wrappers.
#
# Sourced, never executed. gc reaches a command through the `run` key of its
# command.toml and no command.toml names this file, so it does not appear in
# `gc <binding> --help` and `gc <binding> _lib` is an unknown command.

# Where the pack lives. gc sets GC_PACK_DIR; the fallback keeps the helpers
# usable in the one case the guard below exists for.
SF_PACK_DIR=${GC_PACK_DIR:-$(cd "$(dirname "$0")/.." && pwd)}

# Say which command failed, and do not let that line be mistaken for one to
# type. Naming the failure `gc slack post-message: ...` was wrong twice over:
# it reads as an instruction, and `slack` is one city's import name rather than
# anything this pack knows. The pack's own name identifies it without inviting
# a copy-paste.
sf_die() {
    _sf_verb=$1
    _sf_msg=$2
    shift 2
    echo "slack-full $_sf_verb: $_sf_msg" >&2
    for _sf_line in "$@"; do
        echo "$_sf_line" >&2
    done
    exit 1
}

sf_require_pack_context() {
    [ -n "${GC_PACK_DIR:-}" ] && return 0
    sf_die "$1" "missing Gas City pack context" \
        "GC_PACK_DIR is unset. gc sets it when it runs a pack command, so this" \
        "wrapper was started some other way. Reach it as a gc command instead."
}

# The six Go-backed commands need a binary the pack ships as source. Without
# this the wrapper's `exec` reported `not found` against a path inside the pack
# -- true, and no help at all to someone who has never built it.
#
# The path is single-quoted inside the printed command because it is a path the
# operator chose: a checkout under `/work/Gas City/` splits `cd` across two
# words and the copied line fails, or worse, does something else.
sf_require_cli() {
    [ -x "$SF_PACK_DIR/cli/gc-slack-cli" ] && return 0
    sf_die "$1" "the operator CLI is not built" \
        "This pack ships its two binaries as source. Build this one with:" \
        "  (cd '$SF_PACK_DIR'/cli && go build -o gc-slack-cli .)" \
        "gc doctor reports the same thing as the slack-full:binaries check."
}
