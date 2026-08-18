package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestRootHelpOnNoArgs pins the gc-slack-cli convention that bare
// invocation prints usage rather than running silently. Cobra
// auto-promotes help when no Run is defined on the root, but a
// future contributor adding a default Run could regress it; this
// test guards the contract from gc-wj70y.
func TestRootHelpOnNoArgs(t *testing.T) {
	t.Setenv("GC_CITY_PATH", "")
	t.Setenv("GC_PACK_DIR", "")
	cmd := newRootCmd()
	var out bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetErr(&out)
	cmd.SetArgs(nil)
	if err := cmd.Execute(); err != nil {
		t.Fatalf("Execute() with no args: unexpected error: %v", err)
	}
	got := out.String()
	if !strings.Contains(got, filepath.Base(os.Args[0])) {
		t.Errorf("usage output missing binary name: %q", got)
	}
	if !strings.Contains(got, "Usage:") {
		t.Errorf("usage output missing 'Usage:' header: %q", got)
	}
}

func TestRootUseNamesPackCommandInsideGC(t *testing.T) {
	packDir := t.TempDir()
	scriptDir := filepath.Join(packDir, "assets", "scripts")
	if err := os.MkdirAll(scriptDir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(scriptDir, "gc_binding.py"), []byte("print('team-chat')\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("GC_CITY_PATH", t.TempDir())
	t.Setenv("GC_PACK_DIR", packDir)

	cmd := newRootCmd()
	if got := cmd.DisplayName(); got != "gc team-chat" {
		t.Fatalf("root display name = %q, want %q", got, "gc team-chat")
	}
	var out bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetArgs([]string{"map-rig", "--help"})
	if err := cmd.Execute(); err != nil {
		t.Fatalf("map-rig help: %v", err)
	}
	if !strings.Contains(out.String(), "gc team-chat map-rig <rig-name>") {
		t.Fatalf("child usage does not name the bound command: %q", out.String())
	}
}

func TestRootUseFallsBackToPlaceholderInsideGC(t *testing.T) {
	t.Setenv("GC_CITY_PATH", t.TempDir())
	t.Setenv("GC_PACK_DIR", t.TempDir())

	if got := newRootCmd().DisplayName(); got != "gc <binding>" {
		t.Fatalf("root display name = %q, want %q", got, "gc <binding>")
	}
}

// TestPackDirFor covers the fallback the adapter measurement forced: gc sets
// GC_PACK_DIR for pack commands, not for every way a pack binary is started,
// so the binary's own location under <pack>/cli/ is the second source.
func TestPackDirFor(t *testing.T) {
	if got := packDirFor("/packs/slack-full", "/elsewhere/cli/gc-slack-cli"); got != "/packs/slack-full" {
		t.Errorf("packDirFor with env = %q, want the env value", got)
	}
	if got := packDirFor("", "/packs/slack-full/cli/gc-slack-cli"); got != "/packs/slack-full" {
		t.Errorf("packDirFor derived from the binary = %q, want /packs/slack-full", got)
	}
	if got := packDirFor("", ""); got != "" {
		t.Errorf("packDirFor with nothing to go on = %q, want empty", got)
	}
}

func TestRootUseNamesBinaryOutsideGC(t *testing.T) {
	t.Setenv("GC_CITY_PATH", "")
	t.Setenv("GC_PACK_DIR", "")
	if got := rootCommandUse("/opt/slack/gc-slack-cli"); got != "gc-slack-cli" {
		t.Fatalf("rootCommandUse outside gc = %q, want %q", got, "gc-slack-cli")
	}
}

// TestRootRejectsUnknownSubcommand pins the contract that an unknown
// subcommand exits non-zero. Cobra's default behavior surfaces this
// as a non-nil Execute error; main() translates that into os.Exit(1).
func TestRootRejectsUnknownSubcommand(t *testing.T) {
	cmd := newRootCmd()
	var out bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetErr(&out)
	cmd.SetArgs([]string{"definitely-not-a-real-subcommand"})
	err := cmd.Execute()
	if err == nil {
		t.Fatal("Execute() with unknown subcommand: want error, got nil")
	}
	if !strings.Contains(err.Error(), "definitely-not-a-real-subcommand") {
		t.Errorf("error %q does not mention the unknown subcommand", err)
	}
}

// TestRunSuccessExitCode covers the run() wrapper's success path —
// no-args invocation prints help and returns 0.
func TestRunSuccessExitCode(t *testing.T) {
	var stderr bytes.Buffer
	got := run(nil, &stderr)
	if got != 0 {
		t.Errorf("run(nil) = %d, want 0", got)
	}
	if stderr.Len() != 0 {
		t.Errorf("run(nil) stderr = %q, want empty", stderr.String())
	}
}

// TestRunErrorExitCode covers the run() wrapper's failure path:
// non-zero exit code and a "gc-slack-cli:"-prefixed stderr line so
// downstream operator tooling can grep on it consistently.
func TestRunErrorExitCode(t *testing.T) {
	var stderr bytes.Buffer
	got := run([]string{"definitely-not-a-real-subcommand"}, &stderr)
	if got != 1 {
		t.Errorf("run(unknown) = %d, want 1", got)
	}
	if !strings.HasPrefix(stderr.String(), "gc-slack-cli:") {
		t.Errorf("stderr %q missing 'gc-slack-cli:' prefix", stderr.String())
	}
	if !strings.Contains(stderr.String(), "definitely-not-a-real-subcommand") {
		t.Errorf("stderr %q does not mention the unknown subcommand", stderr.String())
	}
}
