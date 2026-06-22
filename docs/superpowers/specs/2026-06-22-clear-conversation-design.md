# Clear Conversation — Design

**Date:** 2026-06-22

## Goal

Let a Solution Engineer wipe the message history of the session they're
viewing, so a demo can be restarted from a clean phone screen without
restarting the server.

## Scope

- **Current session only.** Clearing `/alice` leaves `/bob` untouched.
- Triggered by a **button in the phone UI** (no separate "clear all" control,
  no public API endpoint).

## Behaviour

- The session's stored messages are emptied.
- `next_id` is **kept monotonic** (not reset to 1). An integration still
  polling `GET /{session}/replies?since=N` keeps working — new ids stay above
  any cursor it already holds. The screen simply empties.

## Changes

### `app/store.py`
- Add `async def clear(self, session_id: str) -> None`: acquires the session
  lock and sets `session.messages = []`. Leaves `next_id` unchanged.

### `app/main.py`
- Add route `POST /{session_id}/clear`. Calls `store.clear(...)`, then returns
  the re-rendered `_messages.html` partial (now empty) using the existing
  `_messages_context` helper — identical response shape to `/reply`, so HTMX
  swaps it straight into `#messages`.

### `app/templates/chat.html`
- Add a **Clear** button in the phone header with:
  - `hx-post="/{{ session_id }}/clear"`
  - `hx-target="#messages"`
  - `hx-swap="outerHTML"`
  - `hx-confirm="Clear this conversation?"` (built-in HTMX confirm; no JS)

## Non-goals

- Clearing all sessions at once.
- A DELETE/REST API endpoint for clearing.
- Resetting `next_id` / message ids to 1.

## Testing

- `store.clear` empties messages and preserves `next_id` (a message added
  after a clear gets the next sequential id, not 1).
- `POST /{session}/clear` returns 200 and a body with no message bubbles;
  `GET /{session}` afterwards shows an empty conversation.
