package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// withTimeout returns a context bounded by d, with a Cleanup-style
// cancel that the caller can defer. Test-only helper.
func withTimeout(t *testing.T, d time.Duration) (context.Context, context.CancelFunc) {
	t.Helper()
	return context.WithTimeout(context.Background(), d)
}

// Tests for gc-px8.5 — first-mention thread-context forwarding.
//
// The processSlackEvent paths are exercised end-to-end against an
// httptest stub for both Slack's conversations.replies endpoint
// (overriding slackAPIBase) and gc's inbound endpoint
// (cfg.gcAPIBase). The captured POST body to gc is the assertion
// surface — the bridge-mail Text either carries the preamble or
// doesn't, depending on the cache state.

// withSlackAPIStub installs a slackAPIBase override pointing at the
// supplied test server and returns a restore closure. Pattern matches
// what other slack-API tests in this package do.
func withSlackAPIStub(t *testing.T, srv *httptest.Server) {
	t.Helper()
	prev := slackAPIBase
	slackAPIBase = srv.URL
	t.Cleanup(func() { slackAPIBase = prev })
}

// inboundCapture is a thin gc-stub that records each posted inbound
// message body so tests can assert on Text content without parsing
// raw bytes inline.
type inboundCapture struct {
	mu       sync.Mutex
	messages []externalInboundMessage
}

func (c *inboundCapture) handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var env struct {
			Message externalInboundMessage `json:"message"`
		}
		if err := json.Unmarshal(body, &env); err == nil {
			c.mu.Lock()
			c.messages = append(c.messages, env.Message)
			c.mu.Unlock()
		}
		w.WriteHeader(http.StatusAccepted)
	}
}

func (c *inboundCapture) snapshot() []externalInboundMessage {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := make([]externalInboundMessage, len(c.messages))
	copy(out, c.messages)
	return out
}

// fakeSlackRepliesServer returns an httptest server that replies to
// /conversations.replies with the supplied messages, counting how
// many times it was called.
func fakeSlackRepliesServer(t *testing.T, messages []slackThreadMessage) (*httptest.Server, *int32) {
	t.Helper()
	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/conversations.replies") {
			http.Error(w, "unexpected path "+r.URL.Path, http.StatusNotFound)
			return
		}
		atomic.AddInt32(&calls, 1)
		resp := slackConversationsRepliesResp{OK: true, Messages: messages}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}))
	t.Cleanup(srv.Close)
	return srv, &calls
}

func TestThreadContext_FirstMentionPrependsPreamble(t *testing.T) {
	prior := []slackThreadMessage{
		{User: "U_ALICE", Text: "should we ship this?", TS: "100.000001"},
		{User: "U_BOB", Text: "lgtm — open the PR", TS: "100.000002"},
	}
	slackStub, calls := fakeSlackRepliesServer(t, prior)
	withSlackAPIStub(t, slackStub)

	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:               gcStub.URL,
		cityName:                "test-city",
		provider:                "slack",
		accountID:               "T1",
		handlePrefix:            "@",
		slackBotToken:           "xoxb-fake",
		slackThreadContextLimit: 20,
		threadContextCache:      newThreadContextCache(),
	}
	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  "C1",
		User:     "U_ALICE",
		TS:       "100.000003",
		ThreadTS: "100.000001",
		Text:     "@mayor please weigh in",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, env, func() {})

	if got := atomic.LoadInt32(calls); got != 1 {
		t.Fatalf("conversations.replies calls = %d, want 1", got)
	}
	msgs := capture.snapshot()
	if len(msgs) != 1 {
		t.Fatalf("captured %d inbound messages, want 1", len(msgs))
	}
	body := msgs[0].Text
	if !strings.HasPrefix(body, "Thread context (2 earlier messages):\n") {
		t.Errorf("body missing preamble; got %q", body)
	}
	if !strings.Contains(body, "@U_ALICE: should we ship this?") {
		t.Errorf("body missing U_ALICE prior message; got %q", body)
	}
	if !strings.Contains(body, "@U_BOB: lgtm — open the PR") {
		t.Errorf("body missing U_BOB prior message; got %q", body)
	}
	// The "@mayor" handle prefix is stripped by parseHandlePrefix
	// before the preamble is prepended; the literal mention text
	// "please weigh in" must still appear after the preamble.
	if !strings.Contains(body, "please weigh in") {
		t.Errorf("body missing original text after preamble; got %q", body)
	}
	if msgs[0].ExplicitTarget != "mayor" {
		t.Errorf("ExplicitTarget = %q, want %q", msgs[0].ExplicitTarget, "mayor")
	}
}

func TestThreadContext_SecondMentionDoesNotRefetchOrPrepend(t *testing.T) {
	prior := []slackThreadMessage{
		{User: "U_ALICE", Text: "context line", TS: "200.000001"},
	}
	slackStub, calls := fakeSlackRepliesServer(t, prior)
	withSlackAPIStub(t, slackStub)

	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:               gcStub.URL,
		cityName:                "test-city",
		provider:                "slack",
		accountID:               "T1",
		handlePrefix:            "@",
		slackBotToken:           "xoxb-fake",
		slackThreadContextLimit: 20,
		threadContextCache:      newThreadContextCache(),
	}

	first, _ := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  "C1",
		User:     "U_BOB",
		TS:       "200.000002",
		ThreadTS: "200.000001",
		Text:     "@mayor first mention",
	})
	second, _ := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  "C1",
		User:     "U_BOB",
		TS:       "200.000003",
		ThreadTS: "200.000001",
		Text:     "@mayor follow-up question",
	})

	aliasReg := newTestHandleAliasRegistry(t)
	processSlackEvent(cfg, aliasReg, nil, nil, slackEventEnvelope{Type: "event_callback", Event: first}, func() {})
	processSlackEvent(cfg, aliasReg, nil, nil, slackEventEnvelope{Type: "event_callback", Event: second}, func() {})

	if got := atomic.LoadInt32(calls); got != 1 {
		t.Errorf("conversations.replies calls = %d, want 1 (cache should suppress second fetch)", got)
	}
	msgs := capture.snapshot()
	if len(msgs) != 2 {
		t.Fatalf("captured %d inbound messages, want 2", len(msgs))
	}
	if !strings.HasPrefix(msgs[0].Text, "Thread context (1 earlier message):\n") {
		t.Errorf("first inbound missing preamble; got %q", msgs[0].Text)
	}
	if strings.Contains(msgs[1].Text, "Thread context") {
		t.Errorf("second inbound carried preamble; got %q", msgs[1].Text)
	}
	if !strings.HasPrefix(msgs[1].Text, "follow-up question") {
		t.Errorf("second inbound text unexpected; got %q", msgs[1].Text)
	}
}

func TestThreadContext_NonThreadInboundSkipsFetch(t *testing.T) {
	slackStub, calls := fakeSlackRepliesServer(t, nil)
	withSlackAPIStub(t, slackStub)

	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:               gcStub.URL,
		cityName:                "test-city",
		provider:                "slack",
		accountID:               "T1",
		handlePrefix:            "@",
		slackBotToken:           "xoxb-fake",
		slackThreadContextLimit: 20,
		threadContextCache:      newThreadContextCache(),
	}
	// thread_ts empty: not a reply; no preamble path.
	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U_ALICE",
		TS:      "300.000001",
		Text:    "standalone message",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, env, func() {})

	if got := atomic.LoadInt32(calls); got != 0 {
		t.Errorf("conversations.replies calls = %d, want 0", got)
	}
	msgs := capture.snapshot()
	if len(msgs) != 1 {
		t.Fatalf("captured %d inbound messages, want 1", len(msgs))
	}
	if strings.Contains(msgs[0].Text, "Thread context") {
		t.Errorf("non-thread inbound carried preamble; got %q", msgs[0].Text)
	}
}

func TestThreadContext_ThreadParentSkipsFetch(t *testing.T) {
	// thread_ts == ts: this IS the thread parent. No priors exist.
	slackStub, calls := fakeSlackRepliesServer(t, nil)
	withSlackAPIStub(t, slackStub)

	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:               gcStub.URL,
		cityName:                "test-city",
		provider:                "slack",
		accountID:               "T1",
		handlePrefix:            "@",
		slackBotToken:           "xoxb-fake",
		slackThreadContextLimit: 20,
		threadContextCache:      newThreadContextCache(),
	}
	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  "C1",
		User:     "U_ALICE",
		TS:       "400.000001",
		ThreadTS: "400.000001",
		Text:     "kicking off a new thread",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, env, func() {})

	if got := atomic.LoadInt32(calls); got != 0 {
		t.Errorf("conversations.replies calls = %d, want 0", got)
	}
	msgs := capture.snapshot()
	if len(msgs) != 1 {
		t.Fatalf("captured %d inbound messages, want 1", len(msgs))
	}
	if strings.Contains(msgs[0].Text, "Thread context") {
		t.Errorf("thread-parent inbound carried preamble; got %q", msgs[0].Text)
	}
}

func TestThreadContext_NoPriorsAfterFilteringEmitsNoPreamble(t *testing.T) {
	// Slack returns only the current message and a bot-authored
	// reply. Both are filtered; no priors → no preamble.
	currentTS := "500.000005"
	prior := []slackThreadMessage{
		{User: "U_ALICE", Text: "first", TS: "500.000001"},
		{BotID: "B0", User: "", Text: "bot reply", TS: "500.000002"},
		// The current message itself; conversations.replies includes it.
		{User: "U_BOB", Text: "@mayor question", TS: currentTS},
	}
	// First inbound has TS = "500.000001" — making U_ALICE's message
	// not "prior" (it's the current one). Other entries are bot or
	// later. So preamble should NOT be emitted.
	slackStub, calls := fakeSlackRepliesServer(t, prior)
	withSlackAPIStub(t, slackStub)

	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:               gcStub.URL,
		cityName:                "test-city",
		provider:                "slack",
		accountID:               "T1",
		handlePrefix:            "@",
		slackBotToken:           "xoxb-fake",
		slackThreadContextLimit: 20,
		threadContextCache:      newThreadContextCache(),
	}
	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  "C1",
		User:     "U_ALICE",
		TS:       "500.000001",
		ThreadTS: "500.000000",
		Text:     "@mayor first mention",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, env, func() {})

	if got := atomic.LoadInt32(calls); got != 1 {
		t.Errorf("conversations.replies calls = %d, want 1 (one fetch attempted, no preamble emitted)", got)
	}
	msgs := capture.snapshot()
	if len(msgs) != 1 {
		t.Fatalf("captured %d inbound messages, want 1", len(msgs))
	}
	if strings.Contains(msgs[0].Text, "Thread context") {
		t.Errorf("inbound carried preamble despite no priors after filter; got %q", msgs[0].Text)
	}
}

func TestThreadContext_FetchFailureMarksSeenAndDoesNotRetry(t *testing.T) {
	// Slack stub returns 500 on every call. The cache should still
	// mark the (channel, thread_ts) seen so subsequent inbounds
	// don't hammer the API. The bridge-mail body is still posted —
	// just without a preamble.
	var calls int32
	failingSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&calls, 1)
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	t.Cleanup(failingSrv.Close)
	withSlackAPIStub(t, failingSrv)

	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:               gcStub.URL,
		cityName:                "test-city",
		provider:                "slack",
		accountID:               "T1",
		handlePrefix:            "@",
		slackBotToken:           "xoxb-fake",
		slackThreadContextLimit: 20,
		threadContextCache:      newThreadContextCache(),
	}
	mk := func(ts string) []byte {
		raw, _ := json.Marshal(slackMessageEvent{
			Type: "message", Channel: "C1", User: "U_ALICE",
			TS: ts, ThreadTS: "600.000001", Text: "@mayor x",
		})
		return raw
	}
	aliasReg := newTestHandleAliasRegistry(t)
	processSlackEvent(cfg, aliasReg, nil, nil, slackEventEnvelope{Type: "event_callback", Event: mk("600.000002")}, func() {})
	processSlackEvent(cfg, aliasReg, nil, nil, slackEventEnvelope{Type: "event_callback", Event: mk("600.000003")}, func() {})

	if got := atomic.LoadInt32(&calls); got != 1 {
		t.Errorf("conversations.replies calls = %d, want 1 (failure must not be retried per inbound)", got)
	}
	msgs := capture.snapshot()
	if len(msgs) != 2 {
		t.Fatalf("captured %d inbound messages, want 2", len(msgs))
	}
	for i, m := range msgs {
		if strings.Contains(m.Text, "Thread context") {
			t.Errorf("inbound %d carried preamble despite fetch failure; got %q", i, m.Text)
		}
	}
}

// Direct unit tests for the helpers without going through processSlackEvent.

func TestThreadContextCache_FirstSightingAtomic(t *testing.T) {
	t.Parallel()
	c := newThreadContextCache()
	if !c.firstSighting("C1", "T1") {
		t.Fatal("first call should return true")
	}
	if c.firstSighting("C1", "T1") {
		t.Fatal("second call on same pair should return false")
	}
	if !c.firstSighting("C1", "T2") {
		t.Error("different thread on same channel should return true")
	}
	if !c.firstSighting("C2", "T1") {
		t.Error("same thread on different channel should return true")
	}

	// Nil receiver is safe.
	var nilCache *threadContextCache
	if nilCache.firstSighting("C", "T") {
		t.Error("nil cache should return false")
	}

	// Empty channel/thread short-circuits.
	if c.firstSighting("", "T1") {
		t.Error("empty channel should return false")
	}
	if c.firstSighting("C1", "") {
		t.Error("empty thread should return false")
	}
}

func TestThreadContextCache_FirstSightingConcurrent(t *testing.T) {
	t.Parallel()
	c := newThreadContextCache()
	const workers = 16
	var wins int32
	var wg sync.WaitGroup
	wg.Add(workers)
	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()
			if c.firstSighting("C1", "T1") {
				atomic.AddInt32(&wins, 1)
			}
		}()
	}
	wg.Wait()
	if got := atomic.LoadInt32(&wins); got != 1 {
		t.Errorf("wins = %d, want exactly 1 (race-safe atomic check-and-set)", got)
	}
}

func TestFormatThreadContextPreamble_FiltersAndFormats(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name     string
		replies  []slackThreadMessage
		current  string
		want     string
		wantNoOp bool
	}{
		// All ts strings are 17-char Slack format
		// "<10-digit-seconds>.<6-digit-microseconds>". Lexical order
		// matches numeric order at this fixed length, which is what
		// formatThreadContextPreamble's filter relies on.
		{
			name:     "no replies",
			replies:  nil,
			current:  "1700000100.000000",
			wantNoOp: true,
		},
		{
			name: "only current message",
			replies: []slackThreadMessage{
				{User: "U1", Text: "hi", TS: "1700000100.000000"},
			},
			current:  "1700000100.000000",
			wantNoOp: true,
		},
		{
			name: "only later replies after current",
			replies: []slackThreadMessage{
				{User: "U1", Text: "future", TS: "1700000200.000000"},
			},
			current:  "1700000100.000000",
			wantNoOp: true,
		},
		{
			name: "only bot replies",
			replies: []slackThreadMessage{
				{BotID: "B0", Text: "bot noise", TS: "1700000050.000000"},
			},
			current:  "1700000100.000000",
			wantNoOp: true,
		},
		{
			name: "only whitespace replies",
			replies: []slackThreadMessage{
				{User: "U1", Text: "   ", TS: "1700000050.000000"},
			},
			current:  "1700000100.000000",
			wantNoOp: true,
		},
		{
			name: "single prior",
			replies: []slackThreadMessage{
				{User: "U1", Text: "earlier", TS: "1700000050.000000"},
			},
			current: "1700000100.000000",
			want:    "Thread context (1 earlier message):\n@U1: earlier\n\n---\n\n",
		},
		{
			name: "two priors with newline collapse",
			replies: []slackThreadMessage{
				{User: "U1", Text: "line1\nline2", TS: "1700000050.000000"},
				{User: "U2", Text: "alright", TS: "1700000060.000000"},
			},
			current: "1700000100.000000",
			want:    "Thread context (2 earlier messages):\n@U1: line1 | line2\n@U2: alright\n\n---\n\n",
		},
		{
			name: "empty user falls back to ?",
			replies: []slackThreadMessage{
				{User: "", Text: "anon", TS: "1700000050.000000"},
			},
			current: "1700000100.000000",
			want:    "Thread context (1 earlier message):\n@?: anon\n\n---\n\n",
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			got := formatThreadContextPreamble(tc.replies, tc.current)
			if tc.wantNoOp {
				if got != "" {
					t.Errorf("expected empty preamble, got %q", got)
				}
				return
			}
			if got != tc.want {
				t.Errorf("preamble:\ngot:  %q\nwant: %q", got, tc.want)
			}
		})
	}
}

// TestFetchThreadReplies_QueryAndAuth — cannot t.Parallel because
// it overwrites the package-level slackAPIBase var.
func TestFetchThreadReplies_QueryAndAuth(t *testing.T) {
	var (
		mu             sync.Mutex
		capturedAuth   string
		capturedQuery  string
	)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		capturedAuth = r.Header.Get("Authorization")
		capturedQuery = r.URL.RawQuery
		mu.Unlock()
		_ = json.NewEncoder(w).Encode(slackConversationsRepliesResp{OK: true})
	}))
	t.Cleanup(srv.Close)
	prev := slackAPIBase
	slackAPIBase = srv.URL
	t.Cleanup(func() { slackAPIBase = prev })

	ctx, cancel := withTimeout(t, 5*time.Second)
	defer cancel()
	if _, err := fetchThreadReplies(ctx, "xoxb-test", "C1", "1700000100.000000", 5); err != nil {
		t.Fatalf("fetchThreadReplies: %v", err)
	}
	mu.Lock()
	gotAuth, gotQuery := capturedAuth, capturedQuery
	mu.Unlock()
	if gotAuth != "Bearer xoxb-test" {
		t.Errorf("Authorization = %q, want %q", gotAuth, "Bearer xoxb-test")
	}
	if !strings.Contains(gotQuery, "channel=C1") ||
		!strings.Contains(gotQuery, "ts=1700000100.000000") ||
		!strings.Contains(gotQuery, "limit=5") {
		t.Errorf("query string %q missing expected fields", gotQuery)
	}
}

func TestFetchThreadReplies_RejectsEmptyArgs(t *testing.T) {
	t.Parallel()
	ctx, cancel := withTimeout(t, time.Second)
	defer cancel()
	cases := []struct {
		name              string
		token, ch, thread string
	}{
		{"empty token", "", "C1", "T1"},
		{"empty channel", "xoxb", "", "T1"},
		{"empty thread", "xoxb", "C1", ""},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			if _, err := fetchThreadReplies(ctx, tc.token, tc.ch, tc.thread, 5); err == nil {
				t.Error("expected error, got nil")
			}
		})
	}
}

// TestFetchThreadReplies_NotOK — cannot t.Parallel because it
// overwrites the package-level slackAPIBase var.
func TestFetchThreadReplies_NotOK(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(slackConversationsRepliesResp{OK: false, Error: "missing_scope"})
	}))
	t.Cleanup(srv.Close)
	prev := slackAPIBase
	slackAPIBase = srv.URL
	t.Cleanup(func() { slackAPIBase = prev })

	ctx, cancel := withTimeout(t, time.Second)
	defer cancel()
	_, err := fetchThreadReplies(ctx, "xoxb", "C1", "1700000100.000000", 5)
	if err == nil {
		t.Fatal("expected error on ok=false")
	}
	if !strings.Contains(err.Error(), "missing_scope") {
		t.Errorf("error %v missing slack error code", err)
	}
}
