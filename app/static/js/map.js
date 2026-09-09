import { onSettingsPanelOpen, onSettingsCoordsChange, setFormCoords } from "./settings.js";

const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION = "© OpenStreetMap";
const UNAVAILABLE = "Map unavailable — type coordinates instead.";

function mapAvailable() {
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

function createPicker(element, { latitude, longitude }, onPick) {
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
