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

function formatCoords(latitude, longitude) {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

// Shared by createPicker and createStaticMap. A single tile 404 (common at
// high zoom, or over water) must never tear down an otherwise working map —
// only degrade if no tile has ever loaded successfully. Once degraded, the
// Leaflet map instance is destroyed and the holder shows the same fallback
// the library-absent branch uses, via the same showUnavailable helper.
function addTileLayer(map, element, fallbackMessage) {
  let loaded = false;
  let degraded = false;
  const layer = window.L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION });
  layer.on("tileload", () => {
    loaded = true;
  });
  layer.on("tileerror", () => {
    if (loaded || degraded) return;
    degraded = true;
    map.remove();
    showUnavailable(element, fallbackMessage);
  });
  layer.addTo(map);
  return { isDegraded: () => degraded };
}

function createPicker(element, { latitude, longitude }, onPick) {
  if (!mapAvailable()) {
    showUnavailable(element, UNAVAILABLE);
    return null;
  }
  takeOver(element);
  const map = window.L.map(element).setView([latitude, longitude], 14);
  const tileLayer = addTileLayer(map, element, UNAVAILABLE);
  // Real tile requests always resolve asynchronously, so this never actually
  // fires in a browser — kept because addTileLayer can in principle degrade
  // synchronously (e.g. under test doubles), and createPicker must not hand
  // back a picker built on a map it just destroyed.
  if (tileLayer.isDegraded()) return null;
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
      // A tileerror can degrade the map after this picker was already
      // handed back to initMapPicker; once degraded, the map is destroyed
      // and the holder shows plain text, so there is nothing left to move.
      if (tileLayer.isDegraded()) return;
      marker.setLatLng([lat, lng]);
      map.setView([lat, lng], map.getZoom());
    },
    refresh() {
      // The sheet is hidden when the map is built, so Leaflet needs a nudge
      // once it becomes visible or the tiles render as grey blocks.
      if (tileLayer.isDegraded()) return;
      map.invalidateSize();
    },
  };
}

export function createStaticMap(element, { latitude, longitude }) {
  if (!mapAvailable()) {
    showUnavailable(element, formatCoords(latitude, longitude));
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
  const tileLayer = addTileLayer(map, element, formatCoords(latitude, longitude));
  if (tileLayer.isDegraded()) return;
  window.L.marker([latitude, longitude]).addTo(map);
  setTimeout(() => {
    if (!tileLayer.isDegraded()) map.invalidateSize();
  }, 0);
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
