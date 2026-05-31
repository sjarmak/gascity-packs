package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
)

// statusForError maps a server-layer error to an HTTP status. Persistence
// failures (errPersistence) are operational 500s; everything else is treated
// as a caller error (400). Decode and required-field checks are handled
// inline by each handler before reaching the server layer.
func statusForError(err error) int {
	if errors.Is(err, errPersistence) {
		return http.StatusInternalServerError
	}
	return http.StatusBadRequest
}

type bindRequest struct {
	ChannelID  string   `json:"channel_id"`
	Kind       string   `json:"kind"`
	SessionIDs []string `json:"session_ids"`
}

type identityRequest struct {
	SessionID string `json:"session_id"`
	Username  string `json:"username,omitempty"`
	IconURL   string `json:"icon_url,omitempty"`
	IconEmoji string `json:"icon_emoji,omitempty"`
}

type handleAliasRequest struct {
	Handle    string `json:"handle"`
	SessionID string `json:"session_id,omitempty"`
}

// handleBind persists a channel→sessions binding (bind-dm / bind-room).
func (s *server) handleBind() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req bindRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		rec, err := s.upsertBinding(req.ChannelID, req.Kind, req.SessionIDs)
		if err != nil {
			writeJSONError(w, statusForError(err), err.Error())
			return
		}
		log.Printf("bind: channel=%s kind=%s sessions=%s", rec.ChannelID, rec.Kind, strings.Join(rec.SessionIDs, ","))
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "binding": rec})
	}
}

// handleIdentitySet registers or updates a per-session identity override.
func (s *server) handleIdentitySet() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req identityRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		rec, err := s.upsertIdentity(req.SessionID, req.Username, req.IconURL, req.IconEmoji)
		if err != nil {
			writeJSONError(w, statusForError(err), err.Error())
			return
		}
		log.Printf("identity set: session=%s username=%q", rec.SessionID, rec.Username)
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "identity": rec})
	}
}

// handleIdentityRemove deletes a session's identity override. Idempotent.
func (s *server) handleIdentityRemove() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req identityRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		if strings.TrimSpace(req.SessionID) == "" {
			writeJSONError(w, http.StatusBadRequest, "session_id is required")
			return
		}
		removed, err := s.removeIdentity(req.SessionID)
		if err != nil {
			writeJSONError(w, statusForError(err), err.Error())
			return
		}
		log.Printf("identity remove: session=%s removed=%v", req.SessionID, removed)
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "removed": removed})
	}
}

// handleAliasSet registers or updates a handle→session alias.
func (s *server) handleAliasSet() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req handleAliasRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		rec, err := s.upsertHandleAlias(req.Handle, req.SessionID)
		if err != nil {
			writeJSONError(w, statusForError(err), err.Error())
			return
		}
		log.Printf("handle-alias set: handle=%s session=%s", rec.Handle, rec.SessionID)
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "alias": rec})
	}
}

// handleAliasRemove deletes a handle alias. Idempotent.
func (s *server) handleAliasRemove() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req handleAliasRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		if normalizeHandle(req.Handle) == "" {
			writeJSONError(w, http.StatusBadRequest, "handle is required")
			return
		}
		removed, err := s.removeHandleAlias(req.Handle)
		if err != nil {
			writeJSONError(w, statusForError(err), err.Error())
			return
		}
		log.Printf("handle-alias remove: handle=%s removed=%v", normalizeHandle(req.Handle), removed)
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "removed": removed})
	}
}
