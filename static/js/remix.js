// Remix editor + session revisions strip (FE-16 to FE-18, FE-26).
import { api } from "./api.js";
import { optionCard, pendingCard, pieceKey } from "./cards.js";
import { $, $$, h, replace, show } from "./dom.js";
import { pollJob } from "./jobs.js";
import { getState, update, watch } from "./state.js";
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

function renderChoice(choice) {
  replace($("#remix-chosen"), choice.map((c) => h("li", {},
    h("span", { class: "mono" }, `${"ABC"[c.optionIndex] ?? "?"}`),
    String(c.piece.name ?? ""),
    h("button", {
      type: "button", class: "icon-btn", "aria-label": `Remove ${c.piece.name ?? "piece"}`,
      onclick: () => update((s) => ({ remixChoice: s.remixChoice.filter((x) => x.key !== c.key) })),
    }, "✕"))));
  const chosen = new Set(choice.map((c) => c.key));
  $$("#options .piece[data-key]").forEach((el) => el.setAttribute("aria-pressed", String(chosen.has(el.dataset.key))));
  $("#remix-btn").disabled = choice.length === 0;
}

const setRevision = (jobId, patch) => update((s) => ({
  revisions: s.revisions.map((r) => (r.jobId === jobId ? { ...r, ...patch } : r)),
}));

async function submitRemix() {
  const { job, remixChoice } = getState();
  if (!job?.id || !remixChoice.length) return;
  const button = $("#remix-btn");
  button.disabled = true;
  const result = await api.remix({
    source_job_id: job.id,
    selected_pieces: remixChoice.map((c) => c.piece),
    instructions: $("#remix-instructions").value, // sent verbatim (FE-17)
    event_date: job.brief.event_date,
    event_time: job.brief.event_time,
    city: job.brief.city,
  });
  button.disabled = getState().remixChoice.length === 0;
  if (!result.ok) return toast(result.message, "error");

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

function renderRevisions(revisions) {
  show($("#revisions-wrap"), revisions.length > 0);
  replace($("#revisions"), revisions.map(revisionCard));
}

export function cancelRemixes() {
  cancels.forEach((cancel) => cancel());
  cancels.clear();
}

export function initRemix() {
  $("#remix-btn").addEventListener("click", submitRemix);
  watch((s) => s.remixChoice, renderChoice);
  watch((s) => s.revisions, renderRevisions);
}
