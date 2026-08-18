package main

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const bindingPlaceholder = "<binding>"

// packDirFor answers where this pack lives on disk. See the long comment on
// the adapter's copy: gc sets GC_PACK_DIR for pack COMMANDS and not for every
// way this pack's binaries get run, so the binary's own location — it sits at
// <pack>/cli/gc-slack-cli — is the fallback. exePath is a parameter so a test
// can point it at a fixture instead of the test binary.
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
	if binding == "" || len(strings.Fields(binding)) != 1 {
		return bindingPlaceholder
	}
	return binding
}

// rootCommandUse is what usage lines call this program.
//
// Outside a city there is no binding to name and the operator genuinely typed
// the binary, so the binary is the honest answer. Inside one, every usage line
// is an instruction and has to name the word that city reaches the pack by.
func rootCommandUse(invokedAs string) string {
	if strings.TrimSpace(os.Getenv("GC_CITY_PATH")) == "" {
		return filepath.Base(invokedAs)
	}
	exePath, err := os.Executable()
	if err != nil {
		exePath = invokedAs
	}
	return "gc " + resolvePackBinding(packDirFor(os.Getenv("GC_PACK_DIR"), exePath))
}
