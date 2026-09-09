const STORAGE_KEY = "smartbubble-settings";

// Ship a working demo with zero configuration.
const DEFAULTS = {
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

function saveSettings(values) {
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
