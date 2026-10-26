// Critique rendering (spec.md §7): overall readout, per-dimension bar gauges
// with a tick at the 70 retry line, "Not assessed" for null dimensions (FE-14),
// and the attempt log (FE-25). The payload is treated as untrusted.
import { h } from "./dom.js";

export const RETRY_THRESHOLD = 70;
export const MAX_ATTEMPTS = 3;
const DIMENSIONS = [
  ["occasion", "Occasion"],
  ["aesthetic", "Aesthetic"],
  ["styling", "Styling"],
  ["weather", "Weather"],
  ["upload_fidelity", "Fidelity"],
];
const ASSESSED_FLAG = { weather: "weather_assessed", upload_fidelity: "upload_fidelity_assessed" };

export const isScore = (v) => Number.isInteger(v) && v >= 0 && v <= 100;

/** null = not assessed; undefined = malformed (the whole critique is then treated as failed). */
function dimensionValue(critique, key) {
  const value = critique.scores?.[key];
  const flag = ASSESSED_FLAG[key];
  if (flag && (critique[flag] === false || value === null)) return null;
  return isScore(value) ? value : undefined;
}

const wellFormed = (c) => DIMENSIONS.every(([key]) => dimensionValue(c, key) !== undefined);

export const critiqueFailed = (c) =>
  !c || typeof c !== "object" || c.status === "failed" || !c.scores || typeof c.scores !== "object" || !wellFormed(c);

function gauge(key, label, value) {
  const state = value === null ? "na" : value < RETRY_THRESHOLD ? "low" : "ok";
  return h("div", { class: "gauge", dataset: { dim: key, state }, role: "group", "aria-label": label },
    h("span", { class: "gauge-label" }, label),
    h("span", { class: "gauge-track", "aria-hidden": "true" },
      h("span", { class: "gauge-fill", style: { "--v": `${value ?? 0}%` } }),
      h("span", { class: "gauge-tick" })),
    h("span", { class: "gauge-value" }, value === null ? "Not assessed" : String(value)));
}

/** "pass" | "open" | "unknown", from the final critique and the unresolved list. */
export function verdictOf(option) {
  if (critiqueFailed(option.critique)) return "unknown";
  const open = (option.unresolved?.length ?? 0) > 0 || option.critique.retry_recommended === true;
  return open ? "open" : "pass";
}

const VERDICT_LABEL = { pass: "Meets brief", open: "Open issues", unknown: "Not checked" };

export function overallBlock(option) {
  const verdict = verdictOf(option);
  const badge = h("span", { class: `verdict ${verdict}` }, VERDICT_LABEL[verdict]);
  if (verdict === "unknown") return h("div", { class: "overall" }, badge);
  const overall = isScore(option.critique.overall) ? String(option.critique.overall) : "—";
  return h("div", { class: "overall", role: "img", "aria-label": `Overall score ${overall} out of 100, ${VERDICT_LABEL[verdict]}` },
    h("span", { class: "overall-readout", "aria-hidden": "true" }, overall),
    h("span", { class: "overall-scale", "aria-hidden": "true" }, "/100"),
    h("span", { "aria-hidden": "true" }, badge));
}

export function gauges(critique) {
  return h("div", { class: "gauges" },
    DIMENSIONS.map(([key, label]) => gauge(key, label, dimensionValue(critique, key))),
    h("p", { class: "gauge-legend" }, "│ = 70 retry line · scores rate fit to your brief, not fashion quality"));
}

export function failedNotice() {
  return h("p", { class: "critique-failed" },
    "We could not check this outfit against your brief. Here is the image without a score.");
}

function attemptRow(entry, index, isFinal) {
  const failed = critiqueFailed(entry);
  const score = failed ? "—" : isScore(entry.overall) ? String(entry.overall) : "—";
  let why = "critique unavailable";
  if (!failed && entry.retry_reason) why = isFinal ? `unresolved: ${entry.retry_reason}` : `regenerated: ${entry.retry_reason}`;
  else if (!failed) why = "accepted";
  return h("li", { class: isFinal ? "is-final" : "" },
    h("span", {}, `#${entry?.attempt ?? index + 1}`),
    h("span", {}, score),
    h("span", { class: "why" }, why));
}

export function attemptLog(option) {
  const history = Array.isArray(option.critique_history) && option.critique_history.length
    ? option.critique_history
    : [option.critique];
  return h("details", { class: "attempt-log" },
    h("summary", {}, `Attempt log · ${history.length} of ${MAX_ATTEMPTS}`),
    h("ol", {}, history.map((entry, i) => attemptRow(entry, i, i === history.length - 1))));
}

const SEVERITY_LABEL = { minor: "Minor", major: "Major", critical: "Critical" };

export function mismatchItem(m) {
  const severity = SEVERITY_LABEL[m?.severity] ? m.severity : "minor";
  return h("li", { class: "mismatch", dataset: { severity } },
    h("div", { class: "mismatch-head" },
      h("span", {}, SEVERITY_LABEL[severity]),
      h("span", {}, String(m?.code ?? "").replaceAll("_", " ").toLowerCase())),
    h("div", {}, String(m?.explanation ?? "")));
}
