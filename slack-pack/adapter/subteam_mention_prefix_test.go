package main

import "testing"

// TestParseSubteamMentionPrefix exercises the Slack User Group ("subteam")
// mention parser added in bead gpk-2zi. The parser recognizes the token
// Slack emits when a human picks a User Group from native @-autocomplete:
//
//	<!subteam^TEAMID|@handle>
//
// and extracts `handle` + the trailing remainder. The unlabeled form
// `<!subteam^TEAMID>` must NOT match — the adapter is intentionally
// ignorant of TEAMID values and routes purely on the `@handle` label.
//
// Mirroring parseHandlePrefix where the rules apply, the parser:
//   - tolerates leading whitespace before the token,
//   - consumes one optional `:` after the closing `>` and one leading
//     whitespace byte after that,
//   - rejects labels with invalid handle characters.
func TestParseSubteamMentionPrefix(t *testing.T) {
	cases := []struct {
		name          string
		text          string
		wantHandle    string
		wantRemainder string
		wantOK        bool
	}{
		{
			name:          "labelled token with space remainder",
			text:          "<!subteam^S012|@mayor> please ack",
			wantHandle:    "mayor",
			wantRemainder: "please ack",
			wantOK:        true,
		},
		{
			name:          "labelled token with colon-space remainder",
			text:          "<!subteam^S012|@mayor>: status?",
			wantHandle:    "mayor",
			wantRemainder: "status?",
			wantOK:        true,
		},
		{
			name:          "labelled token with colon-no-space remainder",
			text:          "<!subteam^S012|@cos>:hello",
			wantHandle:    "cos",
			wantRemainder: "hello",
			wantOK:        true,
		},
		{
			name:          "labelled token no remainder",
			text:          "<!subteam^S012|@mayor>",
			wantHandle:    "mayor",
			wantRemainder: "",
			wantOK:        true,
		},
		{
			name:          "leading whitespace permitted",
			text:          "  <!subteam^S012|@lead> hi",
			wantHandle:    "lead",
			wantRemainder: "hi",
			wantOK:        true,
		},
		{
			name:          "label with dash",
			text:          "<!subteam^S012|@gc-pl> x",
			wantHandle:    "gc-pl",
			wantRemainder: "x",
			wantOK:        true,
		},
		{
			name:          "label with underscore",
			text:          "<!subteam^S012|@probe_pl> x",
			wantHandle:    "probe_pl",
			wantRemainder: "x",
			wantOK:        true,
		},
		{
			name:          "newline separator after closer",
			text:          "<!subteam^S012|@mayor>\nfoo",
			wantHandle:    "mayor",
			wantRemainder: "foo",
			wantOK:        true,
		},
		{
			name:          "tab separator after closer",
			text:          "<!subteam^S012|@mayor>\tfoo",
			wantHandle:    "mayor",
			wantRemainder: "foo",
			wantOK:        true,
		},
		{
			name:          "TEAMID with non-alphanumeric characters tolerated",
			text:          "<!subteam^S-abc.123|@mayor> ok",
			wantHandle:    "mayor",
			wantRemainder: "ok",
			wantOK:        true,
		},
		{
			name:          "unlabeled subteam token rejected",
			text:          "<!subteam^S012> please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "label missing leading at sign rejected",
			text:          "<!subteam^S012|mayor> hi",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "empty label rejected",
			text:          "<!subteam^S012|@> hi",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "label with invalid char rejected",
			text:          "<!subteam^S012|@bad.handle> hi",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "label with slash rejected",
			text:          "<!subteam^S012|@bad/handle> hi",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "missing closer rejected",
			text:          "<!subteam^S012|@mayor please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "missing pipe rejected",
			text:          "<!subteam^S012@mayor> please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "closer before pipe rejected",
			text:          "<!subteam^S012>|@mayor please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "user mention (not subteam) does not match",
			text:          "<@U0123|mayor> please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "channel mention (not subteam) does not match",
			text:          "<#C0123|general> please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "token not at start does not match",
			text:          "hello <!subteam^S012|@mayor> please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "plain text does not match",
			text:          "plain text with no token",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "empty input does not match",
			text:          "",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "single-at prefix (not a subteam token) does not match",
			text:          "@mayor please ack",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			gotHandle, gotRemainder, gotOK := parseSubteamMentionPrefix(tc.text)
			if gotOK != tc.wantOK {
				t.Errorf("ok = %v, want %v", gotOK, tc.wantOK)
			}
			if gotHandle != tc.wantHandle {
				t.Errorf("handle = %q, want %q", gotHandle, tc.wantHandle)
			}
			if gotRemainder != tc.wantRemainder {
				t.Errorf("remainder = %q, want %q", gotRemainder, tc.wantRemainder)
			}
		})
	}
}
