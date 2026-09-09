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
- **POST /{session_id}/clear** — empties this session's conversation (backs the header **Clear** button)
- **POST /{session_id}/location** — the phone reporting the customer's answer to the location prompt (used by the UI, not by integrations)

Toggle **iOS** / **Android** in the header; the choice is stored in `localStorage`.

Use the **Clear** button in the header to wipe the current session's messages mid-demo (it asks for confirmation first). It only affects the session you're viewing; other sessions are untouched. Message ids keep counting up, so any integration mid-poll on `/replies` stays in sync.

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
      "created_at": "2026-09-09T10:13:07.375826Z"
    }
  ],
  "next_cursor": 2
}
```

Pass `next_cursor` as `since` on the next poll. CORS is open for browser-based demos.

### Location link

Text the phone a link and the customer can "share" their location with you —
the classic breakdown-company flow.

The URL is **fake**: nothing resolves it, and the page it opens is simulated in
the browser. Send an ordinary message with a URL in the body:

```bash
curl -X POST http://localhost:8000/api/sessions/alice/messages \
  -H 'Content-Type: application/json' \
  -d '{"body":"AA Assist: tap to share your location https://aa-assist.co.uk/loc/x7k2","from":"AA Assist"}'
```

Any `http(s)` URL in a body becomes tappable, and tapping it opens the simulated
page. Set the coordinates it reports, and the page's wording, in the phone's ⚙
**Settings** sheet beforehand — drop a pin on the map or type coordinates. The
settings are stored in `localStorage` and shared by every session in that
browser.

Read the result back:

```bash
curl http://localhost:8000/api/sessions/alice/location
```

Always returns 200, in one of three shapes:

```json
{"status": "none"}
```
```json
{"status": "granted", "latitude": 51.4816, "longitude": -2.5885,
 "accuracy_m": 12.0, "label": "M32 J2, Bristol",
 "shared_at": "2026-09-09T10:10:09.308545Z"}
```
```json
{"status": "denied", "shared_at": "2026-09-09T10:10:09.319847Z"}
```

Only the latest share is kept, and the **Clear** button resets it to `none`.
The `/replies` stream is unaffected — a shared location never appears there.

Dismissing the permission prompt with **Done** or **Escape** records a
**denial**, the same as tapping "Don't allow" — this matches native browser
behaviour but can surprise an SE mid-demo, so know it before you stand in
front of a customer.

The map on the request/confirmation pages is drawn from external CDNs
(Leaflet and OpenStreetMap tiles). If either is unreachable it degrades to
typed/plain coordinates, so the feature still demos on a locked-down network.

## Demo flow

1. Open `http://localhost:8000/my-demo` in a browser for the customer-facing phone.
2. POST a message via the API — it appears as an incoming bubble.
3. Type a reply in the UI — integrations see it on `GET .../replies?since=...`.
