// Job polling (FE-12): poll every 2 s until complete/failed. Stop on 404, after
// 5 consecutive network failures, or while the page has been hidden > 60 s
// (polling resumes when the page becomes visible again).
import { api } from "./api.js";

const POLL_MS = 2000;
const MAX_NETWORK_FAILURES = 5;
const HIDDEN_LIMIT_MS = 60_000;
const TERMINAL = new Set(["complete", "failed"]);

/**
 * pollJob(jobId, { onProgress, onDone, onError }) -> cancel()
 * onProgress(data) for queued/running, onDone(data) for complete/failed,
 * onError(message) when polling gives up.
 */
export function pollJob(jobId, { onProgress = () => {}, onDone, onError }) {
  let timer = null;
  let cancelled = false;
  let failures = 0;
  let hiddenSince = null;
  let paused = false;

  const onVisibility = () => {
    if (document.visibilityState === "hidden") {
      hiddenSince = Date.now();
    } else {
      hiddenSince = null;
      if (paused) {
        paused = false;
        schedule(0);
      }
    }
  };
  document.addEventListener("visibilitychange", onVisibility);

  const stop = () => {
    cancelled = true;
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", onVisibility);
  };

  const schedule = (delay = POLL_MS) => {
    if (!cancelled) timer = setTimeout(tick, delay);
  };

  async function tick() {
    if (cancelled) return;
    if (hiddenSince && Date.now() - hiddenSince > HIDDEN_LIMIT_MS) {
      paused = true;
      return;
    }
    const result = await api.job(jobId);
    if (cancelled) return;
    if (result.ok) {
      failures = 0;
      if (TERMINAL.has(result.data?.status)) {
        stop();
        onDone(result.data);
      } else {
        onProgress(result.data);
        schedule();
      }
      return;
    }
    if (result.network && ++failures < MAX_NETWORK_FAILURES) return schedule();
    stop();
    onError(result.status === 404 ? "That request is no longer available." : result.message);
  }

  schedule();
  return stop;
}
