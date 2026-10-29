// Option card + weather readout builders (FE-13 to FE-15, FE-18).
import { api } from "./api.js";
import { h, safeImageSrc } from "./dom.js";
import {
  MAX_ATTEMPTS, attemptLog, critiqueFailed, failedNotice, gauges, mismatchItem, overallBlock,
} from "./scores.js";
import { toast } from "./toast.js";

const LETTERS = ["A", "B", "C"];
const REASON_TEXT = {
  OUT_OF_FORECAST_RANGE: "the date is beyond the forecast window",
  PROVIDER_ERROR: "the weather service returned an error",
  NETWORK_ERROR: "the weather service could not be reached",
  LOCATION_NOT_FOUND: "that location could not be found",
  INVALID_EVENT_TIME: "no forecast exists for that time",
};

/** Display the model name without its vendor prefix; the full slug is in the tooltip. */
const shortModel = (slug) => (typeof slug === "string" && slug ? slug.split("/").pop() : "critique n/a");

export const letterFor = (index) => LETTERS[index] ?? String(index + 1);
export const pieceKey = (jobId, optionIndex, piece) => `${jobId}:${optionIndex}:${piece.id}`;

function swatch(color) {
  const valid = typeof color === "string" && CSS.supports("color", color);
  return h("span", { class: "swatch", "aria-hidden": "true", style: valid ? { background: color } : undefined });
}

function pieceChip(piece, { key, selectable, pressed, onToggle }) {
  const label = [h("span", { class: "cat" }, String(piece.category ?? "").slice(0, 10)), String(piece.name ?? "")];
  if (!selectable) return h("span", { class: "piece" }, swatch(piece.color), label);
  return h("button", {
    type: "button", class: "piece", dataset: { key }, "aria-pressed": String(pressed),
    title: "Add to remix", onclick: () => onToggle(piece),
  }, swatch(piece.color), label);
}

function figure(option, letter) {
  const fallback = h("span", { class: "img-fallback", hidden: true }, "Image unavailable");
  const img = h("img", {
    src: safeImageSrc(option.image_data_url),
    alt: `Outfit ${letter} on a fictional mannequin`,
    onerror: () => { img.hidden = true; fallback.hidden = false; },
  });
  return h("div", { class: "card-figure" }, img, fallback);
}

function section(label, ...content) {
  return h("div", {}, h("p", { class: "card-section-label" }, label), ...content);
}

function critiqueSections(option) {
  const c = option.critique;
  if (critiqueFailed(c)) return [failedNotice()];
  const list = (items) => (Array.isArray(items) ? items : []).map((t) => h("li", {}, String(t)));
  return [
    gauges(c),
    h("p", { class: "summary" }, String(c.summary ?? "")),
    c.matches?.length ? section("Matches", h("ul", { class: "notes-list matches" }, list(c.matches))) : null,
    c.mismatches?.length ? section("Mismatches", h("ul", { class: "notes-list" }, c.mismatches.map(mismatchItem))) : null,
    c.uncertainty?.length ? section("Uncertain", h("ul", { class: "notes-list uncertain" }, list(c.uncertainty))) : null,
  ];
}

function unresolvedBanner(option) {
  const open = Array.isArray(option.unresolved) ? option.unresolved : [];
  if (!open.length) return null;
  return h("div", { class: "unresolved-banner", role: "note" },
    h("strong", {}, `Unresolved after ${option.attempts ?? MAX_ATTEMPTS} attempts`),
    open.map((m) => h("div", {}, String(m.explanation ?? ""))));
}

async function save(jobId, optionIndex, button) {
  button.disabled = true;
  button.textContent = "Saving…";
  const result = await api.saveLook(jobId, optionIndex);
  if (!result.ok) {
    button.disabled = false;
    button.textContent = "Save look";
    return toast(`${result.message} The look was not saved.`, "error");
  }
  button.textContent = "Saved ✓";
  toast("Saved to your looks.", "success");
  document.dispatchEvent(new CustomEvent("fitlab:look-saved"));
}

/**
 * optionCard(option, { jobId, label, selectable, isPressed(key), onTogglePiece(piece, option) })
 */
export function optionCard(option, { jobId, label, selectable = false, isPressed = () => false, onTogglePiece }) {
  const pieces = Array.isArray(option.pieces) ? option.pieces : [];
  const saveBtn = h("button", { type: "button", class: "btn btn-ghost btn-small save-look" }, "Save look");
  saveBtn.addEventListener("click", () => save(jobId, option.index ?? 0, saveBtn));
  return h("article", { class: "option-card", dataset: { option: label } },
    h("div", { class: "card-strip" },
      h("span", { class: "card-letter" }, label),
      h("span", { title: `Critique model: ${option.critique_model ?? "unknown"}` },
        `Attempt ${option.attempts ?? 1}/${MAX_ATTEMPTS} · ${shortModel(option.critique_model)}`)),
    figure(option, label),
    h("div", { class: "card-body" },
      overallBlock(option),
      unresolvedBanner(option),
      ...critiqueSections(option),
      section("Pieces", pieces.length
        ? h("div", { class: "pieces" }, pieces.map((p) => {
          const key = pieceKey(jobId, option.index ?? 0, p);
          return pieceChip(p, { key, selectable, pressed: isPressed(key), onToggle: (piece) => onTogglePiece(piece, option) });
        }))
        : h("p", { class: "hint" }, "Pieces could not be identified for this image.")),
      attemptLog(option)),
    h("div", { class: "card-actions" }, saveBtn));
}

export function pendingCard(label) {
  return h("article", { class: "option-card is-pending", "aria-busy": "true" },
    h("div", { class: "card-strip" }, h("span", { class: "card-letter" }, label), h("span", {}, "generating")),
    h("div", { class: "card-figure" }),
    h("div", { class: "card-body" },
      h("div", { class: "skeleton-line" }), h("div", { class: "skeleton-line short" }), h("div", { class: "skeleton-line" })));
}

function readout(k, v) {
  return h("div", { class: "readout-item" }, h("span", { class: "k" }, k), h("span", { class: "v" }, v));
}

function eventTime(w) {
  return String(w?.event_local_datetime ?? "").replace("T", " · ") || "—";
}

/** FE-7 + weather intent: always show the location and time used. */
export function weatherReadout(w) {
  if (!w || typeof w !== "object") return [];
  if (!w.available) {
    const why = REASON_TEXT[w.unavailable_reason] ?? "no forecast was available";
    return [
      readout("Location", String(w.location_name ?? "Not set")),
      readout("Event time", eventTime(w)),
      h("p", {}, `Weather is unavailable for that date, so these outfits were made without weather guidance (${why}).`),
    ];
  }
  const num = (v, unit) => (typeof v === "number" ? `${Math.round(v)}${unit}` : "—");
  return [
    readout("Location", String(w.location_name ?? "—")),
    readout("Event time", eventTime(w)),
    readout("Conditions", String(w.condition_label ?? "—")),
    readout("Temp", `${num(w.temperature_f, "°F")} (feels ${num(w.feels_like_f, "°F")})`),
    readout("Precip", num(w.precipitation_probability, "%")),
    readout("Wind", num(w.wind_speed_mph, " mph")),
    readout("Advice", String(w.layering_advice ?? "—")),
  ];
}
