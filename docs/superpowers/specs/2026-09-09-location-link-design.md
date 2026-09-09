# Location Link — Design

**Date:** 2026-09-09

## Goal

Let a Solution Engineer demo the flow a breakdown company uses to locate a
stranded customer: an SMS arrives containing a link, the customer taps it, a
branded page asks for their location, the phone prompts for permission, and the
integration reads the shared position back over the JSON API.

## Scope

- The URL in the message is **fake**. Nothing resolves it; the page it "opens"
  is simulated entirely in the browser.
- The shared coordinates are **configured client side, ahead of time**, in a
  settings panel in the phone UI.
- Integrations read the result from **one new endpoint**. The existing
  `/replies` stream stays text-only.

## Behaviour

### Sending the link

The integration sends an ordinary message whose body happens to contain a URL:

```bash
curl -X POST http://localhost:8000/api/sessions/alice/messages \
  -H 'Content-Type: application/json' \
  -d '{"body":"AA Assist: tap to share your location https://aa-assist.co.uk/loc/x7k2","from":"AA Assist"}'
```

No API change is needed to send one. **Any** `http(s)` URL in a body renders as
a tappable link, and tapping **any** of them opens the simulated location page —
there is no pattern to match and no token to mint.

### Tapping the link

The click is intercepted with `preventDefault()`, so the browser never attempts
to resolve the URL. An overlay slides up inside the phone frame:

- Fake browser chrome — Done button, padlock, **the hostname parsed from the
  tapped URL**, reload glyph.
- Beneath it, the branded page: company name, headline and button text taken
  from settings.

### Asking for permission

The page button opens a styled permission dialog naming that same hostname,
themed to match the current `data-theme`:

- **iOS:** centred alert — *"aa-assist.co.uk" Would Like To Use Your Current
  Location* — with **Don't Allow** / **Allow**.
- **Android:** bottom-anchored dialog with its own copy and buttons.

**Allow** posts the configured coordinates and swaps the page to a confirmation
state showing the label, coordinates and a small non-interactive map.
**Don't Allow** posts a denial and swaps to a "we couldn't locate you" state.

`Esc` or **Done** closes the overlay at any point.

### Settings

A sheet sliding up inside the phone frame, opened by a ⚙ button beside **Clear**
in the session row:

- **Map picker** (~180px): tap or drag the pin to set coordinates. The latitude
  and longitude number inputs stay in sync **both ways**, so typing works too.
- **Fields:** latitude, longitude, accuracy (m), place label, company name,
  headline, button text.
- **Use my real location** — fills the coordinate inputs from the browser's own
  geolocation. A setup convenience only; it is not what the demo shares.
- **Cancel** discards; **Save** writes to `localStorage`.

Settings are stored under `smartbubble-settings` and are **global to the
browser**, like the existing theme preference — not per session.

Defaults ship in code so the feature demos correctly with **zero
configuration**: a Bristol coordinate, label `M32 J2, Bristol`, company
`AA Assist`, headline `We need your exact location to send a patrol`, button
`Share my location`.

Leaflet and OpenStreetMap tiles load from unpkg, matching how htmx is already
loaded. **If Leaflet or the tiles fail to load, the map area shows a short "map
unavailable" note and every input still works.** The panel degrades; it never
blocks. The confirmation state falls back to text-only coordinates the same way.

## API

### Read the shared location

```bash
curl http://localhost:8000/api/sessions/alice/location
```

Always returns **200** — there is no 404 to special-case in a polling loop.
One of three shapes:

```json
{"status": "none"}
```
```json
{"status": "granted", "latitude": 51.4816, "longitude": -2.5885,
 "accuracy_m": 12, "label": "M32 J2, Bristol",
 "shared_at": "2026-09-09T10:04:11+00:00"}
```
```json
{"status": "denied", "shared_at": "2026-09-09T10:04:11+00:00"}
```

Only the latest share is kept — sharing again overwrites the previous result.
The existing **Clear** button also resets the location to `"none"`, since it
exists to reset a demo.

### Write (used by the phone UI)

`POST /{session_id}/location` — sits alongside `POST /{session_id}/clear` as a
UI route, not part of the documented integration API. Body is
`{"status": "granted", "latitude": …, "longitude": …, "accuracy_m": …,
"label": …}` or `{"status": "denied"}`. Latitude and longitude are validated to
their real ranges; out-of-range values are rejected with 422.

The route trusts whatever coordinates the client sends. That is inherent to a
simulator whose location is configured client side.

## Architecture

Three pieces, each understandable on its own:

- **Server (small).** One field on `Session` holding the latest share, one write
  route the phone calls, one read route integrations poll. It knows nothing
  about the fake company, the fake URL, or the overlay.
- **Linkify (template side).** URLs are turned into anchors when
  `_messages.html` renders. This **must** be server side: HTMX replaces
  `#messages` wholesale every 1.5s, so anything the client decorated would be
  wiped by the next poll. The click is caught by a **delegated** listener on the
  container, which survives the swaps. The overlay lives outside `#messages`, so
  polling cannot disturb it.
- **Client (the bulk).** ES modules, with `app.js` as the entry point.

## Changes

### `app/models.py`
- `LocationReport` — inbound: `status` (`granted` | `denied`), optional
  `latitude` (-90..90), `longitude` (-180..180), `accuracy_m`, `label`.
- `LocationState` — outbound: the three response shapes above, `shared_at`
  serialised as ISO-8601.

### `app/store.py`
- `Session.location: LocationState | None`.
- `async def set_location(...)` — takes the session lock, stamps `shared_at`,
  overwrites any previous value.
- `async def get_location(...)`.
- `clear()` additionally sets `location = None`.

### `app/main.py`
- `POST /{session_id}/location` and `GET /api/sessions/{session_id}/location`.
  The API route is registered **before** the catch-all `/{session_id}` route,
  as `/health` and the other API routes already are.
- Register a `linkify` Jinja filter: escapes the body, wraps `https?://[^\s<>"]+`
  in an anchor carrying the raw URL in a data attribute, and leaves trailing
  punctuation (`.,;:!?)`) outside the anchor.

### `app/templates/_messages.html`
- Render bodies through `linkify`.

### `app/templates/chat.html`
- ⚙ button in the session row; markup for the overlay, permission dialog and
  settings sheet; Leaflet CSS/JS includes.

### `app/static/js/`
- Split the current single file into `theme.js` (today's code, moved),
  `settings.js`, `browser.js`, `location.js`, and `app.js` as the entry point
  wiring them together.

### `app/static/css/`
- Overlay, sheet and dialog styles in `base.css`; iOS and Android specifics in
  their existing theme files.

### `README.md`
- Document the demo flow and the new endpoint.

## Testing

Pytest with `TestClient`, following the style of `tests/test_clear.py`, in a new
`tests/test_location.py`:

- `linkify` escapes HTML in the body, wraps `http(s)` URLs, leaves trailing
  punctuation outside the anchor, and passes plain text through untouched.
- Store: set then get; a second share overwrites the first; the denied state
  carries no coordinates; `clear()` resets to none; sessions stay isolated.
- Endpoints: an unshared session returns `{"status":"none"}`; a granted report
  round-trips its coordinates; a denied report carries none; out-of-range
  latitude or longitude is rejected with 422.

The repo has no JavaScript test setup and this design does not add one. The
client side is covered by a written manual check instead: send a message with a
link, tap it, allow, confirm the endpoint reports the configured coordinates;
repeat with deny; confirm the 1.5s poll does not disturb the open overlay.

## Non-goals

- Real device geolocation as the value that gets shared (the settings helper is
  for setup only).
- Simulated page types other than the location request.
- Persistence across server restarts.
- Per-session settings.
- Location history — only the latest share is kept.
- Surfacing the location through `/replies` or as a chat bubble.
