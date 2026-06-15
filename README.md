# SmartBubble

A small web service for demoing SMS integrations. Solution Engineers open a unique session URL (anything after the slash), show a phone-style message UI (iOS or Android), and wire integrations against a simple JSON API.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.13+

## Run

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/ and enter a session name, or go directly to http://localhost:8000/your-demo-name.

## Sessions

No login. The path segment is the session id, e.g. `/alice` and `/bob` are isolated in-memory conversations. State resets when the server restarts.

## Phone UI

- **GET /** — landing page
- **GET /{session_id}** — chat UI with HTMX polling every 1.5s
- **POST /{session_id}/reply** — form field `body` simulates the user replying on the phone

Toggle **iOS** / **Android** in the header; the choice is stored in `localStorage`.

## JSON API

Integrations send SMS into the phone and poll for user replies.

### Send message (into the phone)

```bash
curl -X POST http://localhost:8000/api/sessions/alice/messages \
  -H 'Content-Type: application/json' \
  -d '{"body":"Your code is 123456","from":"+15550000"}'
```

| Field  | Required | Description                          |
|--------|----------|--------------------------------------|
| `body` | yes      | Message text shown on the phone      |
| `from` | no       | Sender label for incoming bubbles    |

Returns the stored message object (`id`, `direction`, `body`, `from`, `created_at`).

### Poll replies (from the phone)

```bash
curl 'http://localhost:8000/api/sessions/alice/replies?since=0'
```

| Query    | Default | Description                                      |
|----------|---------|--------------------------------------------------|
| `since`  | `0`     | Only return `from_phone` messages with `id > since` |

Response:

```json
{
  "messages": [
    {
      "id": 2,
      "direction": "from_phone",
      "body": "Thanks!",
      "from": null,
      "created_at": "2026-06-04T10:00:00+00:00"
    }
  ],
  "next_cursor": 2
}
```

Pass `next_cursor` as `since` on the next poll. CORS is open for browser-based demos.

## Demo flow

1. Open `http://localhost:8000/my-demo` in a browser for the customer-facing phone.
2. POST a message via the API — it appears as an incoming bubble.
3. Type a reply in the UI — integrations see it on `GET .../replies?since=...`.
