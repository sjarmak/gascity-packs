package main

import (
	"os"
	"path/filepath"
	"testing"
)

// newFixturePack lays out a city and a pack the real resolver can answer for,
// and returns (cityPath, packDir). The resolver under test is the pack's own
// gc_binding.py, copied rather than stubbed: a stub would agree with whatever
// the Go side expects and prove nothing about the two halves fitting together.
func newFixturePack(t *testing.T, binding string) (string, string) {
	t.Helper()
	root := t.TempDir()
	city := filepath.Join(root, "city")
	packDir := filepath.Join(root, "packs", "slack-full")
	scripts := filepath.Join(packDir, "assets", "scripts")
	if err := os.MkdirAll(scripts, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(packDir, "adapter"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(city, 0o700); err != nil {
		t.Fatal(err)
	}
	source, err := os.ReadFile(filepath.Join("..", "assets", "scripts", "gc_binding.py"))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(scripts, "gc_binding.py"), source, 0o600); err != nil {
		t.Fatal(err)
	}
	manifest := "[imports." + binding + "]\nsource = \"" + packDir + "\"\n"
	if err := os.WriteFile(filepath.Join(city, "pack.toml"), []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}
	return city, packDir
}

// TestPackDirFromExecutableWhenGCDoesNotSayComes straight from the measurement
// that motivated this file: the adapter runs as a proxy_process service and
// that child never gets GC_PACK_DIR, so deriving the directory from the
// binary's own location is the path production actually takes.
func TestPackDirFor(t *testing.T) {
	tests := []struct {
		name       string
		envPackDir string
		exePath    string
		want       string
	}{
		{
			name:       "gc said so",
			envPackDir: "/packs/slack-full",
			exePath:    "/elsewhere/adapter/gc-slack-adapter",
			want:       "/packs/slack-full",
		},
		{
			name:    "derived from the binary when gc did not",
			exePath: "/packs/slack-full/adapter/gc-slack-adapter",
			want:    "/packs/slack-full",
		},
		{
			name:       "whitespace-only env is not an answer",
			envPackDir: "   ",
			exePath:    "/packs/slack-full/adapter/gc-slack-adapter",
			want:       "/packs/slack-full",
		},
		{
			name: "nothing to go on",
			want: "",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := packDirFor(tc.envPackDir, tc.exePath); got != tc.want {
				t.Fatalf("packDirFor(%q, %q) = %q, want %q", tc.envPackDir, tc.exePath, got, tc.want)
			}
		})
	}
}

func TestResolvePackBinding(t *testing.T) {
	city, packDir := newFixturePack(t, "team-chat")
	t.Setenv("GC_CITY_PATH", city)

	if got := resolvePackBinding(packDir); got != "team-chat" {
		t.Fatalf("resolvePackBinding = %q, want %q", got, "team-chat")
	}
	// No pack directory, an unreadable one, and a city that never imported
	// this pack all have the same honest answer.
	if got := resolvePackBinding(""); got != bindingPlaceholder {
		t.Errorf("resolvePackBinding(\"\") = %q, want the placeholder", got)
	}
	if got := resolvePackBinding(filepath.Join(city, "not-a-pack")); got != bindingPlaceholder {
		t.Errorf("resolvePackBinding(missing) = %q, want the placeholder", got)
	}
}

// TestRefreshPackBindingWithoutGCPackDir is the production path: GC_CITY_PATH
// is set, GC_PACK_DIR is not, and the answer still has to be the binding.
// Reverting packDirFor to `return envPackDir` turns this red.
func TestRefreshPackBindingWithoutGCPackDir(t *testing.T) {
	city, packDir := newFixturePack(t, "team-chat")
	t.Setenv("GC_CITY_PATH", city)
	t.Setenv("GC_PACK_DIR", "")

	exe := filepath.Join(packDir, "adapter", "gc-slack-adapter")
	if got := resolvePackBinding(packDirFor("", exe)); got != "team-chat" {
		t.Fatalf("binding derived from the binary = %q, want %q", got, "team-chat")
	}
	if got := packCommandFor("team-chat", "react"); got != "gc team-chat react" {
		t.Fatalf("packCommand = %q, want %q", got, "gc team-chat react")
	}
}

// packCommandFor is packCommand with the stored value made explicit, so the
// formatting can be asserted without reaching into package state.
func packCommandFor(binding, verb string) string {
	activePackBinding.Store(binding)
	defer activePackBinding.Store(bindingPlaceholder)
	return packCommand(verb)
}

func TestRefreshPackBindingOutsideACity(t *testing.T) {
	t.Setenv("GC_CITY_PATH", "")
	refreshPackBinding()
	if got := packCommand("react"); got != "gc <binding> react" {
		t.Fatalf("packCommand outside a city = %q, want the placeholder form", got)
	}
}
