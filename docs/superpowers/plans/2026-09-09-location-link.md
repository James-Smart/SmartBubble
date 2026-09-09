# Location Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Solution Engineer text the simulated phone a link that opens a
simulated breakdown-company page, prompts for location permission, and reports
the pre-configured coordinates back over the JSON API.

**Architecture:** The server gains one field on `Session` plus two routes (a UI
write route and an integration read route) and knows nothing about the fake
company or the fake URL. Message bodies are linkified **server side** in the
Jinja template, because HTMX replaces `#messages` wholesale every 1.5s and
anything the client decorated would be wiped by the next poll; the tap is caught
by a document-level delegated listener that survives those swaps. Everything
else — the browser overlay, the permission dialog, the branded page and the
settings panel — is client-side ES modules.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, Jinja2, pytest + `TestClient`,
htmx 2 (already loaded from unpkg), Leaflet 1.9.4 + OpenStreetMap tiles (new,
also from unpkg), vanilla ES modules, `localStorage`.

**Spec:** `docs/superpowers/specs/2026-09-09-location-link-design.md`

## Global Constraints

- **The URL in the message is fake.** Nothing may attempt to resolve it. Every
  link tap calls `preventDefault()`.
- **Any** `http(s)` URL in a message body is tappable, and tapping **any** of
  them opens the location page. No pattern matching, no minted tokens.
- `GET /api/sessions/{id}/location` **always returns 200**. Three shapes only:
  `{"status":"none"}`, `{"status":"granted", …}`, `{"status":"denied","shared_at":…}`.
- Only the **latest** share is kept; a new share overwrites the previous one.
- The existing **Clear** button also resets the location to `none`.
- The `/replies` stream stays **text-only**. No location bubble, no new message
  kind.
- Settings live in `localStorage` under `smartbubble-settings` and are **global
  to the browser**, not per session — matching the existing theme preference.
- **Defaults ship in code** so the feature demos with zero configuration:
  latitude `51.4816`, longitude `-2.5885`, accuracy `12`, label
  `M32 J2, Bristol`, company `AA Assist`, headline
  `We need your exact location to send a patrol`, button `Share my location`.
- **If Leaflet or its tiles fail to load, every input still works** and the map
  area shows a short "Map unavailable" note. This applies in *both* places a map
  appears: the settings picker and the confirmation state.
- Latitude is validated to -90..90 and longitude to -180..180; out-of-range
  values are rejected with 422.
- Run tests with `uv run pytest`. Run the app with
  `uv run uvicorn app.main:app --reload --port 8000`.

## File Structure

| File | Responsibility |
|---|---|
| `app/models.py` (modify) | `LocationReport` (inbound), `LocationState` (outbound) |
| `app/store.py` (modify) | `Session.location`, `set_location`, `get_location`; `clear` resets it |
| `app/linkify.py` (create) | Pure function turning a message body into safe HTML with anchors |
| `app/main.py` (modify) | Two routes; registers the `linkify` Jinja filter |
| `app/templates/_messages.html` (modify) | Renders bodies through `linkify` |
| `app/templates/chat.html` (modify) | ⚙ button, settings sheet, browser overlay, permission dialog, Leaflet includes |
| `app/static/js/app.js` (rewrite) | Entry point; wires the modules together |
| `app/static/js/theme.js` (create) | Today's theme toggle, moved out of `app.js` |
| `app/static/js/settings.js` (create) | Settings load/save + the settings sheet |
| `app/static/js/map.js` (create) | Thin Leaflet wrapper with the "unavailable" fallback, shared by the picker and the confirmation map |
| `app/static/js/browser.js` (create) | The in-phone browser overlay chrome and the permission dialog |
| `app/static/js/location.js` (create) | Link tap handling, the branded page, posting the result |
| `app/static/css/base.css` (modify) | Overlay, sheet, dialog, link styles |
| `app/static/css/ios.css` / `android.css` (modify) | Theme specifics for the dialog and chrome |
| `tests/test_location.py` (create) | Store + endpoint tests |
| `tests/test_linkify.py` (create) | Linkify unit tests |
| `README.md` (modify) | Documents the flow and the new endpoint |

`map.js` is a small addition to the module list in the spec. The spec requires
the same graceful degradation in two places (the settings picker and the
confirmation map); putting the Leaflet detail in one module is what stops that
requirement being implemented twice and half-forgotten in one of them.

---

### Task 1: Location state in the store

**Files:**
- Modify: `app/models.py`
- Modify: `app/store.py`
- Test: `tests/test_location.py`

**Interfaces:**
- Consumes: `Session`, `SessionStore` from `app/store.py` as they exist today.
- Produces:
  - `LocationReport(status: Literal["granted","denied"], latitude: float | None, longitude: float | None, accuracy_m: float | None, label: str | None)`
  - `LocationState(status: Literal["none","granted","denied"], latitude, longitude, accuracy_m, label, shared_at: datetime | None)`
  - `await store.set_location(session_id: str, report: LocationReport) -> LocationState`
  - `await store.get_location(session_id: str) -> LocationState`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_location.py`:

```python
import asyncio

from app.models import LocationReport
from app.store import SessionStore


def test_set_and_get_location_round_trips_coordinates():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice",
            LocationReport(
                status="granted",
                latitude=51.4816,
                longitude=-2.5885,
                accuracy_m=12,
                label="M32 J2, Bristol",
            ),
        )
        return await store.get_location("alice")

    state = asyncio.run(scenario())
    assert state.status == "granted"
    assert state.latitude == 51.4816
    assert state.longitude == -2.5885
    assert state.accuracy_m == 12
    assert state.label == "M32 J2, Bristol"
    assert state.shared_at is not None


def test_unshared_session_reports_none():
    store = SessionStore()
    state = asyncio.run(store.get_location("nobody"))
    assert state.status == "none"
    assert state.latitude is None
    assert state.shared_at is None


def test_second_share_overwrites_the_first():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=1.0, longitude=2.0)
        )
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=3.0, longitude=4.0)
        )
        return await store.get_location("alice")

    state = asyncio.run(scenario())
    assert state.latitude == 3.0
    assert state.longitude == 4.0


def test_denied_state_carries_no_coordinates():
    store = SessionStore()

    async def scenario():
        # A client could send coordinates alongside a denial; they must be dropped.
        await store.set_location(
            "alice", LocationReport(status="denied", latitude=1.0, longitude=2.0)
        )
        return await store.get_location("alice")

    state = asyncio.run(scenario())
    assert state.status == "denied"
    assert state.latitude is None
    assert state.longitude is None
    assert state.shared_at is not None


def test_clear_resets_location():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=1.0, longitude=2.0)
        )
        await store.clear("alice")
        return await store.get_location("alice")

    assert asyncio.run(scenario()).status == "none"


def test_sessions_have_independent_locations():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=1.0, longitude=2.0)
        )
        return await store.get_location("bob")

    assert asyncio.run(scenario()).status == "none"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_location.py -v`
Expected: FAIL — `ImportError: cannot import name 'LocationReport' from 'app.models'`

- [ ] **Step 3: Add the models**

Append to `app/models.py`:

```python
class LocationReport(BaseModel):
    """What the phone UI posts when the customer answers the permission prompt."""

    status: Literal["granted", "denied"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    label: str | None = None


class LocationState(BaseModel):
    """What integrations read back. `none` until the customer answers."""

    status: Literal["none", "granted", "denied"]
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    label: str | None = None
    shared_at: datetime | None = None
```

- [ ] **Step 4: Add the store methods**

In `app/store.py`, extend the import to
`from app.models import LocationReport, LocationState, Message`, then add the
field to `Session`:

```python
@dataclass
class Session:
    messages: list[Message] = field(default_factory=list)
    next_id: int = 1
    location: LocationState | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
```

Add the methods to `SessionStore`:

```python
    async def set_location(
        self, session_id: str, report: LocationReport
    ) -> LocationState:
        session = await self.get_or_create(session_id)
        granted = report.status == "granted"
        async with session.lock:
            session.location = LocationState(
                status=report.status,
                # A denial never carries coordinates, whatever the client sent.
                latitude=report.latitude if granted else None,
                longitude=report.longitude if granted else None,
                accuracy_m=report.accuracy_m if granted else None,
                label=report.label if granted else None,
                shared_at=datetime.now(timezone.utc),
            )
            return session.location

    async def get_location(self, session_id: str) -> LocationState:
        session = await self.get_or_create(session_id)
        async with session.lock:
            return session.location or LocationState(status="none")
```

In `clear()`, add `session.location = None` beneath the existing
`session.messages.clear()`, keeping the existing `next_id` comment intact.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS — the six new tests plus the two existing clear tests.

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/store.py tests/test_location.py
git commit -m "Add per-session location state to the store"
```

---

### Task 2: Location endpoints

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_location.py`

**Interfaces:**
- Consumes: `LocationReport`, `LocationState`, `store.set_location`,
  `store.get_location` from Task 1.
- Produces:
  - `GET /api/sessions/{session_id}/location` → `LocationState`, always 200
  - `POST /{session_id}/location` (JSON `LocationReport`) → `LocationState`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_location.py` (add
`from fastapi.testclient import TestClient` and `from app.main import app` to the
imports at the top):

```python
def test_location_endpoint_reports_none_before_any_share():
    client = TestClient(app)
    resp = client.get("/api/sessions/loc-fresh/location")
    assert resp.status_code == 200
    # `none` is exactly one key — nothing for a poller to unpack by mistake.
    assert resp.json() == {"status": "none"}


def test_granted_report_is_readable_from_the_api():
    client = TestClient(app)
    session = "loc-granted"

    post = client.post(
        f"/{session}/location",
        json={
            "status": "granted",
            "latitude": 51.4816,
            "longitude": -2.5885,
            "accuracy_m": 12,
            "label": "M32 J2, Bristol",
        },
    )
    assert post.status_code == 200

    body = client.get(f"/api/sessions/{session}/location").json()
    assert body["status"] == "granted"
    assert body["latitude"] == 51.4816
    assert body["longitude"] == -2.5885
    assert body["accuracy_m"] == 12
    assert body["label"] == "M32 J2, Bristol"
    assert "shared_at" in body


def test_denied_report_is_readable_and_has_no_coordinates():
    client = TestClient(app)
    session = "loc-denied"

    client.post(f"/{session}/location", json={"status": "denied"})

    body = client.get(f"/api/sessions/{session}/location").json()
    assert body["status"] == "denied"
    assert "latitude" not in body
    assert "shared_at" in body


def test_clear_endpoint_resets_the_shared_location():
    client = TestClient(app)
    session = "loc-cleared"

    client.post(
        f"/{session}/location",
        json={"status": "granted", "latitude": 1.0, "longitude": 2.0},
    )
    client.post(f"/{session}/clear")

    assert client.get(f"/api/sessions/{session}/location").json() == {"status": "none"}


def test_out_of_range_coordinates_are_rejected():
    client = TestClient(app)

    too_far_north = client.post(
        "/loc-invalid/location",
        json={"status": "granted", "latitude": 91.0, "longitude": 0.0},
    )
    too_far_east = client.post(
        "/loc-invalid/location",
        json={"status": "granted", "latitude": 0.0, "longitude": 181.0},
    )

    assert too_far_north.status_code == 422
    assert too_far_east.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_location.py -v`
Expected: FAIL — the new endpoint tests get 405/404 rather than 200.

- [ ] **Step 3: Add the routes**

In `app/main.py`, extend the import to
`from app.models import InboundMessage, LocationReport, LocationState, Message, RepliesResponse`.

Add the read route immediately after `get_replies`, so it sits with the other
`/api` routes that are registered **before** the catch-all `/{session_id}`:

```python
@app.get(
    "/api/sessions/{session_id}/location",
    response_model=LocationState,
    response_model_exclude_none=True,
)
async def get_location(session_id: str) -> LocationState:
    return await store.get_location(session_id)
```

Add the write route immediately after `chat_clear` — it is a UI route, the
sibling of `/clear`, not part of the documented integration API:

```python
@app.post(
    "/{session_id}/location",
    response_model=LocationState,
    response_model_exclude_none=True,
)
async def report_location(session_id: str, payload: LocationReport) -> LocationState:
    return await store.set_location(session_id, payload)
```

`response_model_exclude_none=True` is what makes an unshared session serialise
as exactly `{"status": "none"}` instead of a wall of nulls.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS — all tests.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_location.py
git commit -m "Add location report and read endpoints"
```

---

### Task 3: Linkify message bodies

**Files:**
- Create: `app/linkify.py`
- Modify: `app/main.py`
- Modify: `app/templates/_messages.html`
- Test: `tests/test_linkify.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `linkify(text: str) -> markupsafe.Markup`, registered as the Jinja
  filter `linkify`. Anchors it emits carry `class="sms-link"` and
  `data-url="<the raw URL>"` — Task 7's click handler keys off both.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_linkify.py`:

```python
from app.linkify import linkify


def test_plain_text_passes_through_unchanged():
    assert str(linkify("Your patrol is on the way")) == "Your patrol is on the way"


def test_html_in_the_body_is_escaped():
    # Message bodies come straight from the API; they must never inject markup.
    assert "<script>" not in str(linkify("<script>alert(1)</script>"))
    assert "&lt;script&gt;" in str(linkify("<script>alert(1)</script>"))


def test_url_becomes_an_anchor_carrying_the_raw_url():
    result = str(linkify("Tap https://aa-assist.co.uk/loc/x7k2 now"))
    assert 'class="sms-link"' in result
    assert 'data-url="https://aa-assist.co.uk/loc/x7k2"' in result
    assert result.startswith("Tap ")
    assert result.endswith(" now")


def test_trailing_punctuation_stays_outside_the_anchor():
    result = str(linkify("Go to https://aa-assist.co.uk/loc/x7k2."))
    assert 'data-url="https://aa-assist.co.uk/loc/x7k2"' in result
    assert result.endswith("</a>.")


def test_multiple_urls_are_all_linked():
    result = str(linkify("http://a.example/1 and https://b.example/2"))
    assert result.count('class="sms-link"') == 2


def test_quotes_in_a_url_cannot_break_out_of_the_attribute():
    result = str(linkify('https://evil.example/"onmouseover="x'))
    # The quote ends the URL match, and both quotes come back escaped, so no
    # attribute can be closed early.
    assert 'onmouseover="' not in result
    assert "&#34;" in result
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_linkify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.linkify'`

- [ ] **Step 3: Write the implementation**

Create `app/linkify.py`:

```python
import re

from markupsafe import Markup, escape

# Deliberately permissive: the URLs in a demo are fake, so the only job here is
# to find something that looks like a link and stop before whitespace or markup.
_URL_RE = re.compile(r'https?://[^\s<>"]+')

# Sentence punctuation that a URL at the end of a sentence should not swallow.
_TRAILING = ".,;:!?)]}'\""


def linkify(text: str) -> Markup:
    """Escape a message body and wrap any http(s) URLs in tappable anchors.

    Runs server side because HTMX swaps the whole message list every 1.5s;
    anything the client decorated would be wiped by the next poll.
    """
    parts: list[str] = []
    position = 0

    for match in _URL_RE.finditer(text):
        url = match.group(0)
        trailing = ""
        while url and url[-1] in _TRAILING:
            trailing = url[-1] + trailing
            url = url[:-1]

        parts.append(str(escape(text[position : match.start()])))
        if url:
            safe = escape(url)
            parts.append(f'<a class="sms-link" href="#" data-url="{safe}">{safe}</a>')
        parts.append(str(escape(trailing)))
        position = match.end()

    parts.append(str(escape(text[position:])))
    return Markup("".join(parts))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_linkify.py -v`
Expected: PASS — six tests.

- [ ] **Step 5: Register the filter and use it**

In `app/main.py`, add `from app.linkify import linkify` to the imports and,
directly beneath the `templates = Jinja2Templates(...)` line:

```python
templates.env.filters["linkify"] = linkify
```

In `app/templates/_messages.html`, replace the body line:

```html
          <p class="bubble-body">{{ msg.body }}</p>
```

with:

```html
          <p class="bubble-body">{{ msg.body | linkify }}</p>
```

- [ ] **Step 6: Write and run an end-to-end test for the rendered page**

Append to `tests/test_linkify.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_message_page_renders_a_url_as_a_tappable_link():
    client = TestClient(app)
    session = "linkify-page"

    client.post(
        f"/api/sessions/{session}/messages",
        json={"body": "AA Assist: https://aa-assist.co.uk/loc/x7k2", "from": "AA"},
    )

    page = client.get(f"/{session}")
    assert 'class="sms-link"' in page.text
    assert 'data-url="https://aa-assist.co.uk/loc/x7k2"' in page.text
```

Run: `uv run pytest -v`
Expected: PASS — all tests.

- [ ] **Step 7: Commit**

```bash
git add app/linkify.py app/main.py app/templates/_messages.html tests/test_linkify.py
git commit -m "Render URLs in message bodies as tappable links"
```

---

### Task 4: Split the client JavaScript into modules

Pure refactor — no behaviour change. It exists so the following four tasks each
land in a focused file rather than growing one 400-line blob.

**Files:**
- Create: `app/static/js/theme.js`
- Modify: `app/static/js/app.js`
- Modify: `app/templates/chat.html`

**Interfaces:**
- Consumes: the existing theme-toggle behaviour in `app/static/js/app.js`.
- Produces:
  - `initTheme(): void` — exported from `theme.js`
  - `currentTheme(): "ios" | "android"` — exported from `theme.js`, used by
    Task 7 to pick the permission-dialog copy
  - `document.body.dataset.sessionId` — the session id, read by Task 8

- [ ] **Step 1: Create `app/static/js/theme.js`**

```js
const STORAGE_KEY = "smartbubble-theme";

export function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "android"
    ? "android"
    : "ios";
}

export function initTheme() {
  const html = document.documentElement;
  const buttons = document.querySelectorAll(".theme-btn");

  function applyTheme(theme) {
    html.setAttribute("data-theme", theme);
    buttons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.theme === theme);
    });
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (_) {
      /* ignore */
    }
  }

  let saved = null;
  try {
    saved = localStorage.getItem(STORAGE_KEY);
  } catch (_) {
    /* ignore */
  }
  if (saved === "ios" || saved === "android") {
    applyTheme(saved);
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => applyTheme(btn.dataset.theme));
  });
}
```

- [ ] **Step 2: Replace `app/static/js/app.js` with the entry point**

```js
import { initTheme } from "./theme.js";

initTheme();
```

- [ ] **Step 3: Load it as a module**

In `app/templates/chat.html`, change the final script tag to:

```html
  <script type="module" src="/static/js/app.js"></script>
```

and add the session id to the body tag so later modules can read it:

```html
<body data-session-id="{{ session_id }}">
```

- [ ] **Step 4: Verify by hand**

Run: `uv run uvicorn app.main:app --reload --port 8000`
Open `http://localhost:8000/refactor-check`. Expected: the iOS/Android toggle
still switches theme, the choice still survives a reload, and the browser
console is free of module errors.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/theme.js app/static/js/app.js app/templates/chat.html
git commit -m "Split client JavaScript into ES modules"
```

---

### Task 5: Settings storage and panel

**Files:**
- Create: `app/static/js/settings.js`
- Modify: `app/static/js/app.js`
- Modify: `app/templates/chat.html`
- Modify: `app/static/css/base.css`

**Interfaces:**
- Consumes: `document.body.dataset.sessionId` (Task 4).
- Produces:
  - `DEFAULTS` — the object of default settings
  - `loadSettings(): {latitude, longitude, accuracyM, label, company, headline, buttonText}`
  - `saveSettings(values): void`
  - `initSettings(): void` — wires the ⚙ button and the sheet
  - `onSettingsPanelOpen(handler)` / `onSettingsCoordsChange(handler)` hooks used
    by Task 6 to attach the map without `settings.js` importing Leaflet

- [ ] **Step 1: Add the sheet markup**

In `app/templates/chat.html`, add a ⚙ button to the session row, beside Clear:

```html
        <div class="session-row">
          <p class="session-label">Session: <code>{{ session_id }}</code></p>
          <div class="session-actions">
            <button type="button" class="settings-btn" id="settings-open" aria-label="Settings">⚙</button>
            <button
              type="button"
              class="clear-btn"
              hx-post="/{{ session_id }}/clear"
              hx-target="#messages"
              hx-swap="outerHTML"
              hx-confirm="Clear this conversation?"
            >Clear</button>
          </div>
        </div>
```

Then, directly before the closing `</div>` of `.phone` (after `</footer>`), add
the sheet:

```html
      <div class="sheet" id="settings-sheet" role="dialog" aria-label="Settings">
        <div class="sheet-header">
          <h2>Settings</h2>
          <button type="button" class="sheet-close" id="settings-cancel">Cancel</button>
        </div>
        <form class="sheet-body" id="settings-form">
          <h3>Location shared by the phone</h3>
          <div class="map-holder" id="settings-map"></div>
          <div class="field-row">
            <label>Latitude<input type="number" step="any" name="latitude" required></label>
            <label>Longitude<input type="number" step="any" name="longitude" required></label>
          </div>
          <div class="field-row">
            <label>Accuracy (m)<input type="number" step="any" min="0" name="accuracyM"></label>
            <label>Place label<input type="text" name="label" autocomplete="off"></label>
          </div>
          <button type="button" class="secondary-btn" id="settings-real-location">
            Use my real location
          </button>
          <p class="field-note" id="settings-real-location-note"></p>

          <h3>Link page</h3>
          <label>Company<input type="text" name="company" autocomplete="off"></label>
          <label>Headline<input type="text" name="headline" autocomplete="off"></label>
          <label>Button text<input type="text" name="buttonText" autocomplete="off"></label>

          <button type="submit" class="primary-btn">Save</button>
        </form>
      </div>
```

- [ ] **Step 2: Write `app/static/js/settings.js`**

```js
const STORAGE_KEY = "smartbubble-settings";

// Ship a working demo with zero configuration.
export const DEFAULTS = {
  latitude: 51.4816,
  longitude: -2.5885,
  accuracyM: 12,
  label: "M32 J2, Bristol",
  company: "AA Assist",
  headline: "We need your exact location to send a patrol",
  buttonText: "Share my location",
};

const openHandlers = [];
const coordsHandlers = [];

export function onSettingsPanelOpen(handler) {
  openHandlers.push(handler);
}

export function onSettingsCoordsChange(handler) {
  coordsHandlers.push(handler);
}

export function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch (_) {
    return { ...DEFAULTS };
  }
}

export function saveSettings(values) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(values));
  } catch (_) {
    /* a demo box with storage disabled still works for this session */
  }
}

function readForm(form) {
  const data = new FormData(form);
  return {
    latitude: Number(data.get("latitude")),
    longitude: Number(data.get("longitude")),
    accuracyM: Number(data.get("accuracyM")) || 0,
    label: String(data.get("label") || ""),
    company: String(data.get("company") || DEFAULTS.company),
    headline: String(data.get("headline") || DEFAULTS.headline),
    buttonText: String(data.get("buttonText") || DEFAULTS.buttonText),
  };
}

function fillForm(form, values) {
  Object.entries(values).forEach(([key, value]) => {
    const input = form.elements[key];
    if (input) input.value = value;
  });
}

// Task 6 calls this to keep the pin and the number inputs in sync.
export function setFormCoords(latitude, longitude) {
  const form = document.getElementById("settings-form");
  if (!form) return;
  form.elements.latitude.value = latitude.toFixed(6);
  form.elements.longitude.value = longitude.toFixed(6);
}

export function initSettings() {
  const sheet = document.getElementById("settings-sheet");
  const form = document.getElementById("settings-form");
  const openBtn = document.getElementById("settings-open");
  const cancelBtn = document.getElementById("settings-cancel");
  const realBtn = document.getElementById("settings-real-location");
  const note = document.getElementById("settings-real-location-note");
  if (!sheet || !form) return;

  function open() {
    fillForm(form, loadSettings());
    note.textContent = "";
    sheet.classList.add("open");
    openHandlers.forEach((handler) => handler(loadSettings()));
  }

  function close() {
    sheet.classList.remove("open");
  }

  openBtn.addEventListener("click", open);
  cancelBtn.addEventListener("click", close);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    saveSettings(readForm(form));
    close();
  });

  // Typing coordinates moves the pin, just as dragging the pin fills the inputs.
  ["latitude", "longitude"].forEach((name) => {
    form.elements[name].addEventListener("change", () => {
      const latitude = Number(form.elements.latitude.value);
      const longitude = Number(form.elements.longitude.value);
      if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
        coordsHandlers.forEach((handler) => handler(latitude, longitude));
      }
    });
  });

  realBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      note.textContent = "This browser can't report a location.";
      return;
    }
    note.textContent = "Locating…";
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude, accuracy } = position.coords;
        setFormCoords(latitude, longitude);
        if (Number.isFinite(accuracy)) {
          form.elements.accuracyM.value = Math.round(accuracy);
        }
        coordsHandlers.forEach((handler) => handler(latitude, longitude));
        note.textContent = "Filled from this device.";
      },
      () => {
        note.textContent = "Couldn't read this device's location.";
      },
    );
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
}
```

- [ ] **Step 3: Wire it into the entry point**

`app/static/js/app.js`:

```js
import { initTheme } from "./theme.js";
import { initSettings } from "./settings.js";

initTheme();
initSettings();
```

- [ ] **Step 4: Style the sheet**

Append to `app/static/css/base.css`:

```css
/* --- Settings sheet ------------------------------------------------------ */

.session-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.settings-btn {
  flex-shrink: 0;
  margin-top: 0.35rem;
  padding: 0.2rem 0.5rem;
  border: none;
  border-radius: 8px;
  font-size: 0.75rem;
  cursor: pointer;
  background: rgba(128, 128, 128, 0.25);
  color: inherit;
}

.sheet {
  position: absolute;
  inset: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  background: #14161c;
  color: #e8eaed;
  transform: translateY(100%);
  visibility: hidden;
  transition: transform 0.25s ease, visibility 0.25s;
}

.sheet.open {
  transform: translateY(0);
  visibility: visible;
}

.sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1rem 0.5rem;
  flex-shrink: 0;
}

.sheet-header h2 {
  margin: 0;
  font-size: 1.05rem;
}

.sheet-close {
  border: none;
  background: none;
  color: #8ab4f8;
  font-size: 0.85rem;
  cursor: pointer;
}

.sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.sheet-body h3 {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.55;
}

.sheet-body label {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.7rem;
  opacity: 0.75;
}

.sheet-body input {
  padding: 0.45rem 0.6rem;
  border: 1px solid #3c4043;
  border-radius: 8px;
  background: #252830;
  color: #e8eaed;
  font-size: 0.85rem;
}

.field-row {
  display: flex;
  gap: 0.5rem;
}

.field-row label {
  flex: 1;
  min-width: 0;
}

.field-note {
  margin: 0;
  font-size: 0.7rem;
  opacity: 0.6;
  min-height: 1em;
}

.map-holder {
  height: 180px;
  border-radius: 10px;
  overflow: hidden;
  background: #252830;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  opacity: 0.7;
}

.primary-btn {
  margin-top: 0.5rem;
  padding: 0.6rem 1rem;
  border: none;
  border-radius: 10px;
  background: #8ab4f8;
  color: #0f1115;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
}

.secondary-btn {
  padding: 0.45rem 0.75rem;
  border: 1px solid #3c4043;
  border-radius: 10px;
  background: transparent;
  color: #e8eaed;
  font-size: 0.8rem;
  cursor: pointer;
}
```

- [ ] **Step 5: Verify by hand**

Run: `uv run uvicorn app.main:app --reload --port 8000`, open
`http://localhost:8000/settings-check`. Expected: ⚙ opens the sheet pre-filled
with the defaults (`51.4816`, `AA Assist`, …); editing a field and pressing Save
closes it, and reopening shows the edited values; Cancel discards an edit; `Esc`
closes the sheet. The map area shows an empty grey box for now.

- [ ] **Step 6: Commit**

```bash
git add app/static/js/settings.js app/static/js/app.js app/templates/chat.html app/static/css/base.css
git commit -m "Add settings sheet for the demo location and link page copy"
```

---

### Task 6: Map picker

**Files:**
- Create: `app/static/js/map.js`
- Modify: `app/static/js/app.js`
- Modify: `app/templates/chat.html`

**Interfaces:**
- Consumes: `onSettingsPanelOpen`, `onSettingsCoordsChange`, `setFormCoords`
  from Task 5.
- Produces:
  - `mapAvailable(): boolean`
  - `createPicker(element, {latitude, longitude}, onPick): {setCoords(lat, lng)} | null`
  - `createStaticMap(element, {latitude, longitude}): void` — used by Task 8
  - `initMapPicker(): void`

- [ ] **Step 1: Load Leaflet**

In `app/templates/chat.html`, beside the existing htmx script tag:

```html
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
```

Leaflet must load before the module runs, so keep it in `<head>` with htmx —
`<script type="module">` is deferred, so `window.L` is set by the time
`app.js` executes.

- [ ] **Step 2: Write `app/static/js/map.js`**

```js
import { onSettingsPanelOpen, onSettingsCoordsChange, setFormCoords } from "./settings.js";

const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION = "© OpenStreetMap";
const UNAVAILABLE = "Map unavailable — type coordinates instead.";

export function mapAvailable() {
  return typeof window.L !== "undefined";
}

function showUnavailable(element, message) {
  element.style.display = "";
  element.textContent = message;
}

function takeOver(element) {
  // The holders centre their fallback text with flex; Leaflet needs a plain
  // block box or its panes get squashed.
  element.style.display = "block";
  element.textContent = "";
}

export function createPicker(element, { latitude, longitude }, onPick) {
  if (!mapAvailable()) {
    showUnavailable(element, UNAVAILABLE);
    return null;
  }
  takeOver(element);
  const map = window.L.map(element).setView([latitude, longitude], 14);
  window.L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION }).addTo(map);
  const marker = window.L.marker([latitude, longitude], { draggable: true }).addTo(map);

  marker.on("dragend", () => {
    const { lat, lng } = marker.getLatLng();
    onPick(lat, lng);
  });
  map.on("click", (event) => {
    marker.setLatLng(event.latlng);
    onPick(event.latlng.lat, event.latlng.lng);
  });

  return {
    setCoords(lat, lng) {
      marker.setLatLng([lat, lng]);
      map.setView([lat, lng], map.getZoom());
    },
    refresh() {
      // The sheet is hidden when the map is built, so Leaflet needs a nudge
      // once it becomes visible or the tiles render as grey blocks.
      map.invalidateSize();
    },
  };
}

export function createStaticMap(element, { latitude, longitude }) {
  if (!mapAvailable()) {
    showUnavailable(element, `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`);
    return;
  }
  takeOver(element);
  const map = window.L.map(element, {
    zoomControl: false,
    dragging: false,
    scrollWheelZoom: false,
    doubleClickZoom: false,
    touchZoom: false,
    keyboard: false,
  }).setView([latitude, longitude], 15);
  window.L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION }).addTo(map);
  window.L.marker([latitude, longitude]).addTo(map);
  setTimeout(() => map.invalidateSize(), 0);
}

export function initMapPicker() {
  const element = document.getElementById("settings-map");
  if (!element) return;
  let picker = null;

  onSettingsPanelOpen((settings) => {
    if (!picker) {
      picker = createPicker(element, settings, (lat, lng) => {
        setFormCoords(lat, lng);
      });
    } else {
      picker.setCoords(settings.latitude, settings.longitude);
    }
    // Built or shown inside a sheet that was just made visible.
    if (picker) setTimeout(() => picker.refresh(), 50);
  });

  onSettingsCoordsChange((lat, lng) => {
    if (picker) picker.setCoords(lat, lng);
  });
}
```

- [ ] **Step 3: Wire it into the entry point**

`app/static/js/app.js`:

```js
import { initTheme } from "./theme.js";
import { initSettings } from "./settings.js";
import { initMapPicker } from "./map.js";

initTheme();
initSettings();
initMapPicker();
```

- [ ] **Step 4: Verify by hand, including the fallback**

Run the app and open the settings sheet. Expected: a map centred on the default
coordinates with a draggable pin; dragging the pin or clicking the map updates
the latitude/longitude inputs; typing new coordinates and tabbing out moves the
pin; tiles render fully rather than as grey blocks.

Then verify the degraded path — in DevTools, block `unpkg.com` (Network →
request blocking) and reload. Expected: the map area reads "Map unavailable —
type coordinates instead.", every input still works, and Save still stores the
typed values.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/map.js app/static/js/app.js app/templates/chat.html
git commit -m "Add map picker to the settings sheet"
```

---

### Task 7: In-phone browser overlay and permission dialog

**Files:**
- Create: `app/static/js/browser.js`
- Modify: `app/static/js/app.js`
- Modify: `app/templates/chat.html`
- Modify: `app/static/css/base.css`, `app/static/css/ios.css`, `app/static/css/android.css`

**Interfaces:**
- Consumes: the `.ios-only` / `.android-only` helpers already in `base.css` —
  the dialog picks its copy through CSS, so no JavaScript reads the theme.
- Produces:
  - `openBrowser(url: string): HTMLElement` — shows the overlay with the
    hostname parsed from `url`, and returns the empty content element for the
    caller to fill
  - `closeBrowser(): void`
  - `currentHost(): string` — the host currently shown in the chrome
  - `askPermission(): Promise<boolean>` — shows the prompt for the host already
    on screen; resolves `true` for allow, `false` for deny
  - `initBrowser(): void`

- [ ] **Step 1: Add the overlay markup**

In `app/templates/chat.html`, directly after the settings sheet added in Task 5:

```html
      <div class="browser" id="browser">
        <div class="browser-chrome">
          <button type="button" class="browser-done" id="browser-done">Done</button>
          <span class="browser-url"><span aria-hidden="true">🔒</span> <span id="browser-host"></span></span>
          <span class="browser-reload" aria-hidden="true">↻</span>
        </div>
        <div class="browser-content" id="browser-content"></div>

        <div class="perm-backdrop" id="perm-backdrop">
          <div class="perm-dialog">
            <div class="ios-only">
              <p class="perm-title">“<span class="perm-host"></span>” Would Like To Use Your Current Location</p>
              <p class="perm-body">Your location is used to send a patrol to you.</p>
              <div class="perm-actions">
                <button type="button" class="perm-deny">Don't Allow</button>
                <button type="button" class="perm-allow">Allow</button>
              </div>
            </div>
            <div class="android-only">
              <p class="perm-title">Allow <span class="perm-host"></span> to access this device's location?</p>
              <div class="perm-actions">
                <button type="button" class="perm-deny">Don't allow</button>
                <button type="button" class="perm-allow">While using the app</button>
              </div>
            </div>
          </div>
        </div>
      </div>
```

Both dialog variants are always in the DOM; the existing `.ios-only` /
`.android-only` helpers in `base.css` show the right one for the current theme,
so no JavaScript needs to know which is on screen.

- [ ] **Step 2: Write `app/static/js/browser.js`**

```js
const state = { resolve: null };

function hostFromUrl(url) {
  try {
    return new URL(url).host;
  } catch (_) {
    // The URL in a demo message is fake and may not parse. Show it as typed.
    return url.replace(/^https?:\/\//, "").split("/")[0];
  }
}

export function openBrowser(url) {
  const browser = document.getElementById("browser");
  const content = document.getElementById("browser-content");
  const host = hostFromUrl(url);

  document.getElementById("browser-host").textContent = host;
  document.querySelectorAll(".perm-host").forEach((el) => {
    el.textContent = host;
  });
  content.textContent = "";
  browser.classList.add("open");
  browser.dataset.host = host;
  return content;
}

export function closeBrowser() {
  const browser = document.getElementById("browser");
  browser.classList.remove("open");
  hidePermission(false);
}

export function currentHost() {
  return document.getElementById("browser").dataset.host || "";
}

function hidePermission(answer) {
  document.getElementById("perm-backdrop").classList.remove("open");
  if (state.resolve) {
    const resolve = state.resolve;
    state.resolve = null;
    resolve(answer);
  }
}

export function askPermission() {
  document.getElementById("perm-backdrop").classList.add("open");
  return new Promise((resolve) => {
    state.resolve = resolve;
  });
}

export function initBrowser() {
  document.getElementById("browser-done").addEventListener("click", closeBrowser);

  document.querySelectorAll(".perm-allow").forEach((btn) => {
    btn.addEventListener("click", () => hidePermission(true));
  });
  document.querySelectorAll(".perm-deny").forEach((btn) => {
    btn.addEventListener("click", () => hidePermission(false));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const backdrop = document.getElementById("perm-backdrop");
    // Escape backs out of the prompt first, then out of the page.
    if (backdrop.classList.contains("open")) {
      hidePermission(false);
    } else {
      closeBrowser();
    }
  });
}
```

- [ ] **Step 3: Style the overlay and dialog**

Append to `app/static/css/base.css`:

```css
/* --- Simulated in-phone browser ----------------------------------------- */

.sms-link {
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
  word-break: break-all;
}

.browser {
  position: absolute;
  inset: 0;
  z-index: 25;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  color: #16181d;
  transform: translateY(100%);
  visibility: hidden;
  transition: transform 0.25s ease, visibility 0.25s;
}

.browser.open {
  transform: translateY(0);
  visibility: visible;
}

.browser-chrome {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 0.85rem;
  background: #f1f1f3;
  border-bottom: 1px solid #d8d8dd;
  font-size: 0.8rem;
}

.browser-done {
  border: none;
  background: none;
  color: #007aff;
  font-size: 0.85rem;
  cursor: pointer;
  padding: 0;
}

.browser-url {
  flex: 1;
  text-align: center;
  color: #4a4a4f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.browser-reload {
  color: #4a4a4f;
}

.browser-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 1.25rem;
}

/* --- Fake permission prompt --------------------------------------------- */

.perm-backdrop {
  position: absolute;
  inset: 0;
  z-index: 26;
  background: rgba(0, 0, 0, 0.4);
  display: none;
  padding: 1.25rem;
}

.perm-backdrop.open {
  display: flex;
}

.perm-dialog {
  background: #f2f2f6;
  color: #16181d;
  border-radius: 14px;
  padding: 1.1rem 1rem 0.75rem;
  width: 100%;
  max-width: 17rem;
  margin: auto;
  text-align: center;
}

.perm-title {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  font-weight: 600;
}

.perm-body {
  margin: 0 0 0.75rem;
  font-size: 0.75rem;
  opacity: 0.7;
}

.perm-actions {
  display: flex;
  gap: 0.5rem;
}

.perm-actions button {
  flex: 1;
  padding: 0.55rem 0.5rem;
  border: none;
  border-radius: 10px;
  font-size: 0.85rem;
  cursor: pointer;
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

.perm-actions .perm-allow {
  font-weight: 600;
}
```

Append to `app/static/css/ios.css`:

```css
html[data-theme="ios"] .perm-dialog {
  border-radius: 14px;
  text-align: center;
}
```

Append to `app/static/css/android.css`:

```css
html[data-theme="android"] .perm-backdrop.open {
  align-items: flex-end;
}

html[data-theme="android"] .perm-dialog {
  max-width: none;
  margin: 0;
  border-radius: 28px;
  text-align: left;
  background: #1f2126;
  color: #e8eaed;
}

html[data-theme="android"] .perm-actions {
  justify-content: flex-end;
}

html[data-theme="android"] .perm-actions button {
  flex: 0 0 auto;
  background: none;
  color: #a8c7fa;
}

html[data-theme="android"] .browser-done {
  color: #1a73e8;
}
```

- [ ] **Step 4: Wire it into the entry point**

`app/static/js/app.js`:

```js
import { initTheme } from "./theme.js";
import { initSettings } from "./settings.js";
import { initMapPicker } from "./map.js";
import { initBrowser } from "./browser.js";

initTheme();
initSettings();
initMapPicker();
initBrowser();
```

- [ ] **Step 5: Verify by hand from the console**

Run the app, open a session, and in the DevTools console:

```js
const m = await import("/static/js/browser.js");
m.openBrowser("https://aa-assist.co.uk/loc/x7k2").textContent = "hello";
await m.askPermission();
```

Expected: the overlay slides up showing `aa-assist.co.uk` in the chrome, the
prompt appears naming the same host, and the promise resolves `true` for Allow /
`false` for Don't Allow. Switch the theme to Android and repeat: the prompt is
bottom-anchored with Android copy. `Esc` dismisses the prompt first, then the
overlay. **Leave it open for 5 seconds** and confirm the 1.5s message poll does
not disturb it.

- [ ] **Step 6: Commit**

```bash
git add app/static/js/browser.js app/static/js/app.js app/templates/chat.html app/static/css/
git commit -m "Add simulated in-phone browser and permission prompt"
```

---

### Task 8: Tap a link, share the location

**Files:**
- Create: `app/static/js/location.js`
- Modify: `app/static/js/app.js`
- Modify: `app/static/css/base.css`

**Interfaces:**
- Consumes: `loadSettings()` (Task 5); `createStaticMap()` (Task 6);
  `openBrowser()`, `askPermission()` (Task 7);
  `POST /{session_id}/location` (Task 2); the `.sms-link` anchors with
  `data-url` (Task 3).
- Produces: `initLocationLinks(): void`

- [ ] **Step 1: Write `app/static/js/location.js`**

```js
import { loadSettings } from "./settings.js";
import { createStaticMap } from "./map.js";
import { openBrowser, askPermission } from "./browser.js";

function sessionId() {
  return document.body.dataset.sessionId || "";
}

async function report(payload) {
  try {
    await fetch(`/${encodeURIComponent(sessionId())}/location`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (_) {
    /* the demo page has already moved on; nothing useful to show here */
  }
}

function renderRequestPage(content, settings, onShare) {
  content.innerHTML = "";

  const brand = document.createElement("p");
  brand.className = "site-brand";
  brand.textContent = settings.company;

  const headline = document.createElement("h1");
  headline.className = "site-headline";
  headline.textContent = settings.headline;

  const blurb = document.createElement("p");
  blurb.className = "site-blurb";
  blurb.textContent =
    "We'll only use this to send the nearest patrol to you. It is not stored " +
    "after your recovery is complete.";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "site-btn";
  button.textContent = settings.buttonText;
  button.addEventListener("click", onShare);

  content.append(brand, headline, blurb, button);
}

function renderGranted(content, settings) {
  content.innerHTML = "";

  const heading = document.createElement("h1");
  heading.className = "site-headline";
  heading.textContent = "Got it — help is on the way";

  const map = document.createElement("div");
  map.className = "site-map";

  const detail = document.createElement("p");
  detail.className = "site-blurb";
  detail.textContent = settings.label
    ? `${settings.label} · ${settings.latitude.toFixed(5)}, ${settings.longitude.toFixed(5)}`
    : `${settings.latitude.toFixed(5)}, ${settings.longitude.toFixed(5)}`;

  content.append(heading, map, detail);
  createStaticMap(map, {
    latitude: settings.latitude,
    longitude: settings.longitude,
  });
}

function renderDenied(content, settings, onRetry) {
  content.innerHTML = "";

  const heading = document.createElement("h1");
  heading.className = "site-headline";
  heading.textContent = "We couldn't locate you";

  const blurb = document.createElement("p");
  blurb.className = "site-blurb";
  blurb.textContent =
    "Without your location we'll need to ask you for it over the phone.";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "site-btn";
  button.textContent = "Try again";
  button.addEventListener("click", onRetry);

  content.append(heading, blurb, button);
}

function openLocationPage(url) {
  const content = openBrowser(url);
  const settings = loadSettings();

  async function share() {
    const granted = await askPermission();
    if (granted) {
      await report({
        status: "granted",
        latitude: settings.latitude,
        longitude: settings.longitude,
        accuracy_m: settings.accuracyM,
        label: settings.label,
      });
      renderGranted(content, settings);
    } else {
      await report({ status: "denied" });
      renderDenied(content, settings, () => {
        renderRequestPage(content, settings, share);
      });
    }
  }

  renderRequestPage(content, settings, share);
}

export function initLocationLinks() {
  // Delegated from the document: HTMX replaces #messages every 1.5s, so a
  // listener bound to the links themselves would not survive a single poll.
  document.addEventListener("click", (event) => {
    const link = event.target.closest(".sms-link");
    if (!link) return;
    // The URL is fake. Never let the browser try to resolve it.
    event.preventDefault();
    openLocationPage(link.dataset.url || "");
  });
}
```

- [ ] **Step 2: Wire it into the entry point**

`app/static/js/app.js`:

```js
import { initTheme } from "./theme.js";
import { initSettings } from "./settings.js";
import { initMapPicker } from "./map.js";
import { initBrowser } from "./browser.js";
import { initLocationLinks } from "./location.js";

initTheme();
initSettings();
initMapPicker();
initBrowser();
initLocationLinks();
```

- [ ] **Step 3: Style the simulated page**

Append to `app/static/css/base.css`:

```css
/* --- The simulated breakdown-company page ------------------------------- */

.site-brand {
  margin: 0 0 1.25rem;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #c8102e;
}

.site-headline {
  margin: 0 0 0.75rem;
  font-size: 1.3rem;
  line-height: 1.3;
}

.site-blurb {
  margin: 0 0 1.5rem;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #5a5a60;
}

.site-btn {
  width: 100%;
  padding: 0.85rem 1rem;
  border: none;
  border-radius: 12px;
  background: #c8102e;
  color: #ffffff;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
}

.site-map {
  height: 160px;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 1rem;
  background: #e6e6ea;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  color: #5a5a60;
}
```

- [ ] **Step 4: Verify the whole flow by hand**

Run the app and open `http://localhost:8000/flow-check`. Then:

```bash
curl -X POST http://localhost:8000/api/sessions/flow-check/messages \
  -H 'Content-Type: application/json' \
  -d '{"body":"AA Assist: tap to share your location https://aa-assist.co.uk/loc/x7k2","from":"AA Assist"}'
```

Expected, in order:
1. The bubble arrives with the URL underlined and tappable.
2. Tapping it opens the overlay on the branded page — no navigation, the address
   bar of the real browser is unchanged.
3. The button opens the prompt; **Allow** swaps to the confirmation with a map
   pin at the configured coordinates.
4. `curl http://localhost:8000/api/sessions/flow-check/location` returns
   `"status":"granted"` with those coordinates.
5. Done, tap again, choose **Don't Allow**: the page shows the failure state and
   the endpoint returns `{"status":"denied","shared_at":…}`; "Try again" returns
   to the request page.
6. Click **Clear**, then poll the endpoint again: `{"status":"none"}`.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/location.js app/static/js/app.js app/static/css/base.css
git commit -m "Open a simulated location request page when a link is tapped"
```

---

### Task 9: Document the feature

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above. Produces no code.

- [ ] **Step 1: Document the location flow**

In `README.md`, add a section after the **Poll replies** section:

````markdown
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
 "accuracy_m": 12, "label": "M32 J2, Bristol",
 "shared_at": "2026-09-09T10:04:11+00:00"}
```
```json
{"status": "denied", "shared_at": "2026-09-09T10:04:11+00:00"}
```

Only the latest share is kept, and the **Clear** button resets it to `none`.
The `/replies` stream is unaffected — a shared location never appears there.
````

Also add a line to the **Phone UI** list:

```markdown
- **POST /{session_id}/location** — the phone reporting the customer's answer to the location prompt (used by the UI, not by integrations)
```

- [ ] **Step 2: Run the full suite one last time**

Run: `uv run pytest -v`
Expected: PASS — all tests.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document the location link flow"
```
