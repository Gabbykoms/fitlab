// Brief panel: field validation, location source, selection echo (FE-5 to FE-7, FE-11).
import { $, $$ } from "./dom.js";
import { getState, update, watch } from "./state.js";
import { toast } from "./toast.js";

const REQUIRED = ["#occasion", "#aesthetic", "#event-date", "#event-time"];
const GEO_TIMEOUT_MS = 10_000;
let generating = false;

export function todayISO() {
  return new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time
}

function styling() {
  return $("input[name=styling]:checked")?.value ?? "";
}

/** Returns an immutable snapshot of the form, or null fields where empty. */
export function readBrief() {
  const { location, selectedItemIds } = getState();
  const city = $("#city").value.trim();
  const useGeo = !city && location.source === "geo";
  return Object.freeze({
    occasion: $("#occasion").value.trim(),
    aesthetic: $("#aesthetic").value.trim(),
    styling_preference: styling(),
    event_date: $("#event-date").value,
    event_time: $("#event-time").value,
    city: city || null,
    lat: useGeo ? location.lat : null,
    lon: useGeo ? location.lon : null,
    selected_item_ids: [...selectedItemIds],
    notes: $("#notes").value.trim() || null,
  });
}

export function validateBrief(brief) {
  if (!brief.occasion) return "Describe the occasion.";
  if (!brief.aesthetic) return "Describe the look you want.";
  if (!brief.styling_preference) return "Choose a styling preference.";
  if (!brief.event_date) return "Choose the event date.";
  if (brief.event_date < todayISO()) return "The event date cannot be in the past.";
  if (!brief.event_time) return "Choose the event time.";
  return "";
}

function refreshValidity() {
  const brief = readBrief();
  const problem = validateBrief(brief);
  $("#generate-btn").disabled = generating || Boolean(problem);
  // Only surface the past-date problem inline; empty fields are marked on blur.
  $("#brief-error").textContent = brief.event_date && brief.event_date < todayISO()
    ? "The event date cannot be in the past." : "";
  $("#event-date").setAttribute("aria-invalid", String(Boolean(brief.event_date && brief.event_date < todayISO())));
}

function renderLocation() {
  const city = $("#city").value.trim();
  const { location } = getState();
  const status = $("#location-status");
  if (city) status.textContent = `Using ${city}`;
  else if (location.source === "geo") status.textContent = "Using your current location";
  else if (location.source === "pending") status.textContent = "Requesting your location…";
  else status.textContent = "No location chosen yet: add a city or use your location for weather.";
}

function requestLocation() {
  if (!("geolocation" in navigator)) {
    toast("This browser cannot share a location. Enter the event city instead.", "error");
    return $("#city").focus();
  }
  update(() => ({ location: { source: "pending", lat: null, lon: null } }));
  navigator.geolocation.getCurrentPosition(
    (pos) => update(() => ({
      location: { source: "geo", lat: pos.coords.latitude, lon: pos.coords.longitude },
    })),
    () => {
      update(() => ({ location: { source: "none", lat: null, lon: null } }));
      toast("Location access was not available. Enter the event city instead.", "error");
      $("#city").focus();
    },
    { timeout: GEO_TIMEOUT_MS, maximumAge: 600_000 },
  );
}

function renderSelectionEcho(ids) {
  const n = ids.length;
  $("#selection-echo").textContent = n === 0
    ? "No wardrobe pieces selected."
    : `${n} ${n === 1 ? "piece" : "pieces"} selected as the starting point`;
}

export function setGenerating(busy) {
  generating = busy;
  $("#generate-btn").textContent = busy ? "Generating…" : "Generate three outfits";
  refreshValidity();
}

export function initBrief({ onSubmit }) {
  const form = $("#brief-form");
  $("#event-date").min = todayISO();
  form.addEventListener("input", () => {
    refreshValidity();
    renderLocation();
  });
  form.addEventListener("change", refreshValidity);
  REQUIRED.forEach((selector) => $(selector).addEventListener("blur", (event) => {
    if (!event.target.value) event.target.setAttribute("aria-invalid", "true");
    else if (selector !== "#event-date") event.target.removeAttribute("aria-invalid");
  }));
  $("#use-location").addEventListener("click", requestLocation);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const brief = readBrief();
    const problem = validateBrief(brief);
    if (problem) {
      $("#brief-error").textContent = problem;
      return;
    }
    onSubmit(brief);
  });
  watch((s) => s.location, renderLocation);
  watch((s) => s.selectedItemIds, renderSelectionEcho);
  $$("input[name=styling]").forEach((radio) => radio.addEventListener("change", refreshValidity));
  renderLocation();
  refreshValidity();
}
