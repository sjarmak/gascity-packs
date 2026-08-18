package main

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync/atomic"
	"time"
)

const bindingPlaceholder = "<binding>"

var activePackBinding atomic.Value

func init() {
	activePackBinding.Store(bindingPlaceholder)
}

// packDirFor answers where this pack lives on disk.
//
// The adapter is NOT started as a pack command. It is a `proxy_process`
// service, and `internal/workspacesvc/proxy_process.go` builds that child's
// environment by hand: it sets GC_CITY_PATH and the GC_SERVICE_* set, and it
// sets no GC_PACK_DIR at all. Measured on the running adapter, 2026-08-18:
// `tr '\0' '\n' < /proc/<pid>/environ | grep -oE '^GC_[A-Z_]+'` lists 23 keys
// and GC_PACK_DIR is not among them. A resolver that only reads that variable
// therefore falls back to the placeholder on every message this service ever
// sends, which is exactly the surface that matters most — the instructions in
// dispatchToAliasedSession go into an autonomous agent's context.
//
// So the environment is the preferred answer and not the only one: the binary
// itself is inside the pack, at <pack>/adapter/gc-slack-adapter, so its own
// location names the pack directory whether or not gc said so. exePath is a
// parameter rather than an os.Executable() call inside this function because
// under `go test` the executable is a temp file and no fixture could reach it.
func packDirFor(envPackDir, exePath string) string {
	if dir := strings.TrimSpace(envPackDir); dir != "" {
		return dir
	}
	if exePath == "" {
		return ""
	}
	resolved, err := filepath.EvalSymlinks(exePath)
	if err != nil {
		resolved = exePath
	}
	return filepath.Dir(filepath.Dir(resolved))
}

// resolvePackBinding runs the pack's own resolver, which reads the city's
// pack.toml and answers with the import name whose source is this pack.
// GC_PACK_DIR is passed explicitly because the caller may have derived it
// rather than inherited it, and the script reads it from the environment.
func resolvePackBinding(packDir string) string {
	if packDir == "" {
		return bindingPlaceholder
	}
	script := filepath.Join(packDir, "assets", "scripts", "gc_binding.py")
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "python3", script)
	cmd.Env = append(os.Environ(), "GC_PACK_DIR="+packDir)
	out, err := cmd.Output()
	if err != nil {
		return bindingPlaceholder
	}
	binding := strings.TrimSpace(string(out))
	// One field, because the answer is a word a user types after `gc`. The
	// script applies the same rule; this repeats it because what arrives here
	// is bytes from a subprocess, not a value that came through a contract.
	if binding == "" || len(strings.Fields(binding)) != 1 {
		return bindingPlaceholder
	}
	return binding
}

func refreshPackBinding() {
	if strings.TrimSpace(os.Getenv("GC_CITY_PATH")) == "" {
		activePackBinding.Store(bindingPlaceholder)
		return
	}
	exePath, err := os.Executable()
	if err != nil {
		exePath = ""
	}
	activePackBinding.Store(resolvePackBinding(packDirFor(os.Getenv("GC_PACK_DIR"), exePath)))
}

func packCommand(verb string) string {
	return "gc " + activePackBinding.Load().(string) + " " + verb
}
