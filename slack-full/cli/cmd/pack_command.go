package cmd

import "sync/atomic"

const bindingPlaceholder = "<binding>"

var activePackBinding atomic.Value

func init() {
	activePackBinding.Store(bindingPlaceholder)
}

// SetPackBinding gives leaf commands the single binding resolved by the root.
func SetPackBinding(binding string) {
	if binding == "" {
		binding = bindingPlaceholder
	}
	activePackBinding.Store(binding)
}

func packCommand(verb string) string {
	return "gc " + activePackBinding.Load().(string) + " " + verb
}
