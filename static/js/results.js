// Generation controller and the three-option showcase (FE-12, FE-13).
import { api } from "./api.js";
import { setGenerating } from "./brief.js";
import { letterFor, optionCard, pendingCard, weatherReadout } from "./cards.js";
import { $, formatElapsed, h, replace, show } from "./dom.js";
import { pollJob } from "./jobs.js";
import { isChosen, togglePiece } from "./remix.js";
import { getState, update, watch } from "./state.js";
import { toast } from "./toast.js";

const OPTION_COUNT = 3;
const PARTIAL_MESSAGE = "One of the three outfit ideas could not be drawn. The other two are ready.";
let cancelPoll = () => {};
let ticker = null;

const setJob = (patch) => update((s) => ({ job: { ...s.job, ...patch } }));

export async function startGenerate(brief) {
  cancelPoll();
  update(() => ({
    job: { id: null, status: "submitting", startedAt: Date.now(), brief, options: [], weather: null, error: null },
    remixChoice: [],
  }));
  setGenerating(true);
  const result = await api.generate(brief);
  if (!result.ok) {
    setGenerating(false);
    setJob({ status: "failed", error: result.message });
    return toast(result.message, "error");
  }
  setJob({ id: result.data.job_id, status: result.data.status ?? "queued" });
  cancelPoll = pollJob(result.data.job_id, {
    onProgress: (data) => setJob({ status: data.status, weather: data.weather ?? null }),
    onDone: (data) => {
      setGenerating(false);
      setJob({ status: data.status, options: Array.isArray(data.options) ? data.options : [],
        weather: data.weather ?? null, error: data.error ?? null });
      if (data.status === "failed") toast(data.error || "The outfits could not be generated. Please try again.", "error");
      else if (data.options?.length && data.options.length < OPTION_COUNT) toast(PARTIAL_MESSAGE);
    },
    onError: (message) => {
      setGenerating(false);
      setJob({ status: "failed", error: message });
      toast(message, "error");
    },
  });
}

export function cancelGeneration() {
  cancelPoll();
  clearInterval(ticker);
  setGenerating(false);
}

function statusText(job) {
  const elapsed = formatElapsed(Date.now() - job.startedAt);
  switch (job.status) {
    case "submitting": return `submitting · ${elapsed}`;
    case "queued": return `queued · ${elapsed}`;
    case "running": return `running · generate → critique → retry · ${elapsed}`;
    case "complete": return `complete · ${job.options.length} options · ${elapsed}`;
    case "failed": return "failed";
    default: return "";
  }
}

function renderStatus(job) {
  const line = $("#job-status");
  const running = !["complete", "failed"].includes(job.status);
  line.dataset.state = running ? "running" : job.status;
  line.textContent = statusText(job);
  clearInterval(ticker);
  if (running) ticker = setInterval(() => { line.textContent = statusText(getState().job); }, 1000);
}

function renderOptions(job) {
  const grid = $("#options");
  if (job.status === "failed") {
    return replace(grid, h("p", { class: "hint" }, job.error || "The outfits could not be generated. Adjust the brief or try again."));
  }
  if (job.status !== "complete") {
    return replace(grid, Array.from({ length: OPTION_COUNT }, (_, i) => pendingCard(letterFor(i))));
  }
  if (!job.options.length) return replace(grid, h("p", { class: "hint" }, "No outfits came back. Please try again."));
  replace(grid, job.options.map((option) => optionCard(option, {
    jobId: job.id,
    label: letterFor(option.index ?? 0),
    selectable: true,
    isPressed: isChosen,
    onTogglePiece: (piece, opt) => togglePiece(job.id, opt, piece),
  })));
}

function render(job, previous) {
  if (!job) {
    show($("#results-panel"), false);
    show($("#remix-panel"), false);
    show($("#empty-state"), true);
    return;
  }
  show($("#empty-state"), false);
  show($("#results-panel"), true);
  renderStatus(job);
  const weather = $("#weather-readout");
  weather.classList.toggle("is-unavailable", job.weather?.available === false);
  replace(weather, weatherReadout(job.weather));
  const optionsChanged = !previous || previous.status !== job.status || previous.options !== job.options;
  if (optionsChanged) renderOptions(job);
  show($("#remix-panel"), job.status === "complete" && job.options.length > 0);
}

export function initResults() {
  // Option cards are rebuilt only when the job's status or options change.
  watch((s) => s.job, (job, _state, previous) => render(job, previous));
}
