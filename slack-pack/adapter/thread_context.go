package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
)

// gc-px8.5 — first-mention thread-context forwarding.
//
// When a Slack inbound carries thread_ts and the adapter has not
// previously forwarded thread context for that (channel, thread_ts)
// pair, we fetch the thread's earlier replies via Slack's
// conversations.replies endpoint and prepend a compact "Thread
// context (N earlier messages):" preamble onto the bridge-mail body.
// On subsequent inbounds in the same thread the cache short-circuits
// the fetch and emits no preamble — once the receiving agent has
// been seeded, additional context-paste is redundant and would
// pointlessly inflate every reply round-trip.

// defaultThreadContextLimit caps how many thread replies the adapter
// asks Slack for when seeding context. Slack itself silently caps
// conversations.replies at 1000; we want a smaller window so a long-
// running thread doesn't dump a megabyte of history into a single
// bridge-mail body. 20 is generous for the priority-feature use case
// (a freshly-mentioned mayor seeing the recent decision-making) and
// is overrideable via SLACK_THREAD_CONTEXT_LIMIT.
const defaultThreadContextLimit = 20

// threadContextFetchTimeout bounds the conversations.replies HTTP
// round-trip. Slack's API typically responds in well under a second;
// 5s is comfortable headroom and keeps a stuck fetch from blocking
// the dispatch goroutine indefinitely while still holding the
// dispatchSem slot.
const threadContextFetchTimeout = 5 * time.Second

// threadContextCache tracks (channel, thread_ts) pairs the adapter
// has already attempted to fetch context for, so a subsequent
// inbound on the same thread doesn't re-fetch and doesn't re-prepend
// the same preamble. Process-lifetime; no eviction. Workload is
// bounded by the count of distinct active threads, which is small
// relative to per-message memory budgets.
//
// "Already attempted" — not "already succeeded." The cache marks the
// pair seen BEFORE issuing the fetch, so a transient Slack 5xx or a
// missing-scope 401 doesn't get retried on every subsequent inbound
// in that thread. Operators see one error log per thread instead of
// per inbound; the trade-off is that a transient-only failure
// permanently loses context for that thread (the next inbound is the
// signal to investigate).
type threadContextCache struct {
	mu   sync.Mutex
	seen map[string]struct{}
}

func newThreadContextCache() *threadContextCache {
	return &threadContextCache{seen: make(map[string]struct{})}
}

// firstSighting returns true on the first observation of a
// (channel, threadTS) pair and marks the pair seen atomically.
// Subsequent calls for the same pair return false. Safe for
// concurrent callers. A nil receiver returns false (no-op cache).
func (c *threadContextCache) firstSighting(channel, threadTS string) bool {
	if c == nil {
		return false
	}
	if channel == "" || threadTS == "" {
		return false
	}
	key := channel + "|" + threadTS
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, ok := c.seen[key]; ok {
		return false
	}
	c.seen[key] = struct{}{}
	return true
}

// slackThreadMessage is the subset of the conversations.replies
// message shape the adapter consumes when building the preamble.
// Other fields are deliberately ignored to keep the JSON contract
// surface narrow.
type slackThreadMessage struct {
	User string `json:"user"`
	Text string `json:"text"`
	TS   string `json:"ts"`
	// BotID is set when the message came from a bot rather than a
	// human user. Bot-authored messages are skipped from the
	// preamble — they're often the adapter's own outbound replies
	// reflected back, which would create feedback loops if a peer
	// agent re-quoted them.
	BotID string `json:"bot_id,omitempty"`
}

// slackConversationsRepliesResp is the top-level conversations.replies
// JSON response.
type slackConversationsRepliesResp struct {
	OK       bool                 `json:"ok"`
	Error    string               `json:"error,omitempty"`
	Messages []slackThreadMessage `json:"messages,omitempty"`
}

// fetchThreadReplies calls Slack's conversations.replies to retrieve
// messages in the thread rooted at threadTS. limit caps the response
// size; non-positive limits fall back to defaultThreadContextLimit.
//
// Returns the message slice exactly as Slack returned it (oldest-
// first by Slack's contract). The caller filters: drop the current
// message and any later replies before formatting.
func fetchThreadReplies(ctx context.Context, token, channel, threadTS string, limit int) ([]slackThreadMessage, error) {
	if token == "" {
		return nil, fmt.Errorf("slack token empty")
	}
	if channel == "" || threadTS == "" {
		return nil, fmt.Errorf("channel and thread_ts required")
	}
	if limit <= 0 {
		limit = defaultThreadContextLimit
	}
	q := url.Values{}
	q.Set("channel", channel)
	q.Set("ts", threadTS)
	q.Set("limit", strconv.Itoa(limit))

	reqURL := slackAPIBase + "/conversations.replies?" + q.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("build conversations.replies request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("conversations.replies: %w", err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, fmt.Errorf("read conversations.replies body: %w", err)
	}
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("conversations.replies HTTP %d: %s", resp.StatusCode, clipBodyForLog(body))
	}
	var sr slackConversationsRepliesResp
	if err := json.Unmarshal(body, &sr); err != nil {
		return nil, fmt.Errorf("decode conversations.replies: %w (body=%s)", err, clipBodyForLog(body))
	}
	if !sr.OK {
		return nil, fmt.Errorf("conversations.replies not ok: %s", sr.Error)
	}
	return sr.Messages, nil
}

// formatThreadContextPreamble builds the bridge-mail preamble from
// prior messages in the thread. "Prior" means strictly earlier than
// currentTS (Slack ts strings are lexically comparable when in the
// same canonical "<seconds>.<microseconds>" format) and not bot-
// authored. Returns "" when no priors survive filtering — the
// caller MUST treat that case as no-op (gc-px8.5 contract: empty/
// short threads carry no preamble overhead).
func formatThreadContextPreamble(replies []slackThreadMessage, currentTS string) string {
	var prior []slackThreadMessage
	for _, m := range replies {
		if m.TS == "" {
			continue
		}
		if currentTS != "" && m.TS >= currentTS {
			continue
		}
		if m.BotID != "" {
			continue
		}
		if strings.TrimSpace(m.Text) == "" {
			continue
		}
		prior = append(prior, m)
	}
	if len(prior) == 0 {
		return ""
	}
	var b strings.Builder
	fmt.Fprintf(&b, "Thread context (%d earlier message", len(prior))
	if len(prior) != 1 {
		b.WriteByte('s')
	}
	b.WriteString("):\n")
	for _, m := range prior {
		author := m.User
		if author == "" {
			author = "?"
		}
		// Collapse internal newlines to " | " so each prior message
		// stays on a single line — the preamble is meant to be
		// scannable, not a verbatim transcript reproduction.
		text := strings.ReplaceAll(strings.TrimSpace(m.Text), "\n", " | ")
		fmt.Fprintf(&b, "@%s: %s\n", author, text)
	}
	b.WriteString("\n---\n\n")
	return b.String()
}

// clipBodyForLog truncates a Slack response body for inclusion in an
// error message. Slack error bodies are typically tiny; the cap is
// defensive against an unexpectedly large response.
func clipBodyForLog(body []byte) string {
	const maxLen = 256
	if len(body) <= maxLen {
		return string(body)
	}
	return string(body[:maxLen]) + "…"
}
