package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
)

// Sites where a literal `gc slack` is correct. Empty, and it should stay that
// way; an entry here must explain why the string can never reach a user.
var allowedHardcodedBindings = map[string]map[int]string{}

func hardcodedBindingSites(roots ...string) ([]string, error) {
	var hits []string
	for _, root := range roots {
		err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if entry.IsDir() || !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
				return nil
			}
			fileHits, err := hardcodedBindingSitesInFile(path)
			if err != nil {
				return err
			}
			hits = append(hits, fileHits...)
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	sort.Strings(hits)
	return hits, nil
}

func hardcodedBindingSitesInFile(path string) ([]string, error) {
	fset := token.NewFileSet()
	tree, err := parser.ParseFile(fset, path, nil, 0)
	if err != nil {
		return nil, err
	}
	allowed := allowedHardcodedBindings[filepath.Clean(path)]
	var hits []string
	ast.Inspect(tree, func(node ast.Node) bool {
		literal, ok := node.(*ast.BasicLit)
		if !ok || literal.Kind != token.STRING {
			return true
		}
		value, err := strconv.Unquote(literal.Value)
		if err != nil || !strings.Contains(value, "gc slack") {
			return true
		}
		position := fset.Position(literal.Pos())
		if _, ok := allowed[position.Line]; !ok {
			hits = append(hits, fmt.Sprintf("%s:%d", path, position.Line))
		}
		return true
	})
	return hits, nil
}

func TestNoRuntimeStringHardcodesTheBinding(t *testing.T) {
	hits, err := hardcodedBindingSites(".", "../cli")
	if err != nil {
		t.Fatalf("scan Go layer: %v", err)
	}
	if len(hits) != 0 {
		t.Fatalf("runtime string literals hardcode `gc slack` at:\n  %s\nbuild pack instructions with the resolved binding, or add a documented allowance", strings.Join(hits, "\n  "))
	}
}

// TestHardcodedBindingGuardFixture proves BOTH rails on fixtures, because a
// guard that has only ever been seen agreeing is indistinguishable from one
// that cannot disagree. The dirty fixture also carries `gc slack` inside a
// comment on a different line: the assertion on the exact line number is what
// pins that comments are exempt, so a future switch to parser.ParseComments
// fails here rather than silently flagging every explanatory comment.
func TestHardcodedBindingGuardFixture(t *testing.T) {
	clean, err := hardcodedBindingSitesInFile("testdata/no_hardcoded_binding/clean.go.txt")
	if err != nil {
		t.Fatalf("scan clean fixture: %v", err)
	}
	if len(clean) != 0 {
		t.Errorf("clean fixture reported hits: %v", clean)
	}

	dirty, err := hardcodedBindingSitesInFile("testdata/no_hardcoded_binding/hardcoded.go.txt")
	if err != nil {
		t.Fatalf("scan dirty fixture: %v", err)
	}
	want := []string{"testdata/no_hardcoded_binding/hardcoded.go.txt:5"}
	if len(dirty) != len(want) || dirty[0] != want[0] {
		t.Fatalf("dirty fixture hits = %v, want %v (the guard must flag the string literal and only it)", dirty, want)
	}
}
