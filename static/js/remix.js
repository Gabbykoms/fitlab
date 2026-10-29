// Remix editor + session revisions strip (FE-16 to FE-18, FE-26).
import { api } from "./api.js";
import { optionCard, pendingCard, pieceKey } from "./cards.js";
import { $, $$, h, replace, show } from "./dom.js";
import { pollJob } from "./jobs.js";
import { currentEpoch, getState, update, watch } from "./state.js";
import { toast } from "./toast.js";

const MAX_PIECES = 12;
const cancels = new Set();

export const isChosen = (key) => getState().remixChoice.some((c) => c.key === key);

export function togglePiece(jobId, option, piece) {
  const key = pieceKey(jobId, option.index ?? 0, piece);
  update((s) => {
    if (s.remixChoice.some((c) => c.key === key)) {
      return { remixChoice: s.remixChoice.filter((c) => c.key !== key) };
    }
    if (s.remixChoice.length >= MAX_PIECES) {
      toast(`A remix can combine up to ${MAX_PIECES} pieces.`);
      return {};
    }
    return { remixChoice: [...s.remixChoice, { key, optionIndex: option.index ?? 0, piece }] };
  });
}

let submitting = false;

function removeChoice(key) {
  const keys = getState().remixChoice.map((c) => c.key);
  const next = keys[keys.indexOf(key) + 1] ?? keys[keys.indexOf(key) - 1];
  update((s) => ({ remixChoice: s.remixChoice.filter((x) => x.key !== key) }));
  // Keep keyboard focus nearby after the list re-renders (the removed chip is gone).
  ($(`#remix-chosen button[data-key="${CSS.escape(next ?? "")}"]`) ?? $("#remix-instructions")).focus();
}

function renderChoice(choice) {
  replace($("#remix-chosen"), choice.map((c) => h("li", {},
    h("span", { class: "mono" }, `${"ABC"[c.optionIndex] ?? "?"}`),
    String(c.piece.name ?? ""),
    h("button", {
      type: "button", class: "icon-btn", dataset: { key: c.key }, "aria-label": `Remove ${c.piece.name ?? "piece"}`,
      onclick: () => removeChoice(c.key),
    }, "✕"))));
  const chosen = new Set(choice.map((c) => c.key));
  $$("#options .piece[data-key]").forEach((el) => el.setAttribute("aria-pressed", String(chosen.has(el.dataset.key))));
  $("#remix-btn").disabled = submitting || choice.length === 0;
}

/** Patch one revision; a no-op (no new array, no re-render) when nothing changes. */
const setRevision = (jobId, patch) => update((s) => {
  const current = s.revisions.find((r) => r.jobId === jobId);
  if (!current || Object.entries(patch).every(([k, v]) => current[k] === v)) return {};
  return { revisions: s.revisions.map((r) => (r === current ? { ...r, ...patch } : r)) };
});

async function submitRemix() {
  const { job, remixChoice } = getState();
  if (submitting || !job?.id || !remixChoice.length) return;
  const epoch = currentEpoch();
  submitting = true;
  $("#remix-btn").disabled = true;
  const result = await api.remix({
    source_job_id: job.id,
    selected_pieces: remixChoice.map((c) => c.piece),
    instructions: $("#remix-instructions").value, // sent verbatim (FE-17)
    event_date: job.brief.event_date,
    event_time: job.brief.event_time,
    city: job.brief.city,
  });
  submitting = false;
  if (epoch !== currentEpoch()) return;
  $("#remix-btn").disabled = getState().remixChoice.length === 0;
  if (!result.ok) {
    if (result.status !== 401) toast(result.message, "error");
    return;
  }

  const jobId = result.data.job_id;
  update((s) => ({
    revisions: [...s.revisions, { jobId, n: s.revisions.length + 1, status: "queued", option: null, error: null }],
  }));
  const cancel = pollJob(jobId, {
    onProgress: (data) => setRevision(jobId, { status: data.status }),
    onDone: (data) => {
      cancels.delete(cancel);
      const option = data.options?.[0] ?? null;
      setRevision(jobId, { status: option ? data.status : "failed", option, error: data.error ?? null });
      if (data.status === "failed" || !option) toast(data.error || "The remix could not be generated. Please try again.", "error");
      else toast("Remix ready.", "success");
    },
    onError: (message) => {
      cancels.delete(cancel);
      setRevision(jobId, { status: "failed", error: message });
      toast(message, "error");
    },
  });
  cancels.add(cancel);
}

function revisionCard(rev) {
  const label = `R${rev.n}`;
  if (rev.status === "failed") {
    return h("article", { class: "option-card" },
      h("div", { class: "card-strip" }, h("span", { class: "card-letter" }, label), h("span", {}, "failed")),
      h("div", { class: "card-body" }, h("p", { class: "hint" }, rev.error || "The remix could not be generated.")));
  }
  if (!rev.option) return pendingCard(label);
  return optionCard(rev.option, { jobId: rev.jobId, label, selectable: false });
}

/** Keyed reconcile: only cards whose revision object changed are rebuilt, so
 *  "Saved ✓", open attempt logs and focus survive other revisions' updates. */
function renderRevisions(revisions, _state, previous = []) {
  show($("#revisions-wrap"), revisions.length > 0);
  const strip = $("#revisions");
  if (!revisions.length) return replace(strip);
  const before = new Map(previous.map((r) => [r.jobId, r]));
  const existing = new Map([...strip.children].map((el) => [el.dataset.job, el]));
  revisions.forEach((rev, i) => {
    let el = existing.get(rev.jobId);
    if (!el || before.get(rev.jobId) !== rev) {
      const fresh = revisionCard(rev);
      fresh.dataset.job = rev.jobId;
      if (el) el.replaceWith(fresh);
      el = fresh;
    }
    if (strip.children[i] !== el) strip.insertBefore(el, strip.children[i] ?? null);
  });
  [...strip.children].slice(revisions.length).forEach((el) => el.remove());
}

export function cancelRemixes() {
  cancels.forEach((cancel) => cancel());
  cancels.clear();
  submitting = false;
}

export function initRemix() {
  $("#remix-btn").addEventListener("click", submitRemix);
  watch((s) => s.remixChoice, renderChoice);
  watch((s) => s.revisions, renderRevisions);
}
