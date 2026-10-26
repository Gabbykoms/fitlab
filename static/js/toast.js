// Toast region (FE-21). Messages are plain sentences; never JSON or status codes.
import { $, h } from "./dom.js";

const MAX_TOASTS = 4;
const DURATION_MS = { info: 5000, success: 3500, error: 8000 };

export function toast(message, kind = "info") {
  const region = $("#toasts");
  const el = h("div", { class: "toast", dataset: { kind } }, message);
  region.append(el);
  while (region.children.length > MAX_TOASTS) region.firstElementChild.remove();
  setTimeout(() => el.remove(), DURATION_MS[kind] ?? DURATION_MS.info);
}
