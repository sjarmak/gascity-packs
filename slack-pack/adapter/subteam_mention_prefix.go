package main

import "strings"

// parseSubteamMentionPrefix recognizes a Slack User Group ("subteam")
// mention token at the start of the trimmed text and extracts its
// `@handle` label plus the trailing remainder. The token shape Slack
// delivers when a human picks a User Group from native @-autocomplete is:
//
//	<!subteam^TEAMID|@handle>
//
// where TEAMID is the workspace-side User Group ID (e.g. "S0123ABCD")
// and the `@handle` portion is the User Group's display name as a
// `@`-prefixed label. The bare unlabeled form `<!subteam^TEAMID>` does
// NOT match — without the label we cannot map to a handle, and the
// adapter is explicitly designed to be ignorant of TEAMID values
// (the workspace admin manages the alias-to-TEAMID binding out of
// band; see bead gpk-2zi).
//
// Semantics (mirroring parseHandlePrefix where they apply):
//
//   - Leading whitespace is tolerated; the token must start at the
//     trimmed text's first byte.
//   - The label is the longest run of [A-Za-z0-9_-] following the `@`.
//     Empty label, or a label containing other characters, returns
//     ok=false.
//   - After the closing `>`, any leading colon (`:`) is trimmed —
//     matching parseHandlePrefix's "colon is optional but consumed if
//     present" rule — followed by one leading whitespace byte.
//   - TEAMID may contain any non-`|` non-`>` characters; the parser
//     does not validate it. The bead's contract is "map by handle
//     label, ignore TEAMID."
//
// Cases that return ("", "", false):
//
//   - text whose trimmed head is not `<!subteam^`
//   - missing `|@` separator between TEAMID and label
//   - missing closing `>`
//   - empty label (`<!subteam^X|@>`)
//   - label with an invalid character (`<!subteam^X|@bad.handle>`)
//
// On any non-match the returned strings are empty so the caller cannot
// accidentally consume input from a miss — same discipline as
// parseDoubleHandlePrefix.
func parseSubteamMentionPrefix(text string) (handle, remainder string, ok bool) {
	const head = "<!subteam^"
	trimmed := strings.TrimLeft(text, " \t")
	if !strings.HasPrefix(trimmed, head) {
		return "", "", false
	}
	rest := trimmed[len(head):]

	// The team ID is everything up to the `|` that introduces the
	// label. A `>` before any `|` means the unlabeled form
	// `<!subteam^TEAMID>` — reject (no handle to extract).
	pipe := strings.IndexByte(rest, '|')
	closer := strings.IndexByte(rest, '>')
	if pipe < 0 || closer < 0 || closer < pipe {
		return "", "", false
	}

	// Label must begin with `@` to match the format Slack emits when a
	// User Group is selected from autocomplete. The label sits between
	// the `|` and the closing `>`.
	label := rest[pipe+1 : closer]
	if len(label) == 0 || label[0] != '@' {
		return "", "", false
	}
	candidate := label[1:]

	// Scan the longest run of valid handle characters. The full label
	// after `@` must consist only of those characters — a label like
	// `@bad.handle` is rejected (not an address token, same stance as
	// parseHandlePrefix).
	handleEnd := 0
	for i := 0; i < len(candidate); i++ {
		r := candidate[i]
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') ||
			(r >= '0' && r <= '9') || r == '-' || r == '_' {
			handleEnd = i + 1
		} else {
			break
		}
	}
	if handleEnd == 0 || handleEnd != len(candidate) {
		return "", "", false
	}

	body := rest[closer+1:]
	if body == "" {
		return candidate, "", true
	}
	// Optional `:` separator after the token, mirroring parseHandlePrefix
	// ("@handle:" vs "@handle ").
	if body[0] == ':' {
		body = body[1:]
	}
	// One leading whitespace byte trimmed, again mirroring parseHandlePrefix.
	if len(body) > 0 && (body[0] == ' ' || body[0] == '\t' || body[0] == '\n') {
		body = body[1:]
	}
	return candidate, body, true
}
