import { loadSettings } from "./settings.js";
import { createStaticMap } from "./map.js";
import { openBrowser, askPermission } from "./browser.js";

function sessionId() {
  return document.body.dataset.sessionId || "";
}

async function report(payload) {
  try {
    const resp = await fetch(`/${encodeURIComponent(sessionId())}/location`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) console.warn("Location report rejected", resp.status);
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

// A poll swap replaces the whole message list. If one lands between mousedown
// and mouseup, the anchor the user pressed is gone by the time they release,
// so the browser fires no click at all and the tap is silently lost. Holding
// the swap while a pointer is down costs at most one 1.5s poll and closes that
// race; the list is redrawn on the following poll either way.
function holdSwapsWhilePointerIsDown() {
  let pointerDownAt = 0;

  document.addEventListener("pointerdown", () => {
    pointerDownAt = Date.now();
  });
  document.addEventListener("pointerup", () => {
    pointerDownAt = 0;
  });

  document.body.addEventListener("htmx:beforeSwap", (event) => {
    // Time-limited on purpose: if a pointerup is ever missed — released off
    // the window, or a touch gesture cancelled — the hold lapses by itself
    // rather than freezing the conversation permanently.
    if (pointerDownAt && Date.now() - pointerDownAt < 1000) {
      event.preventDefault();
    }
  });
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

  holdSwapsWhilePointerIsDown();
}
