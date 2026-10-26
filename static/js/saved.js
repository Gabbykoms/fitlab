// Saved-looks drawer: list, filter (query params), detail view, delete with
// confirmation (FE-19, FE-20, FE-27). Weather is shown as it was at generation.
import { api } from "./api.js";
import { $, h, replace, safeImageSrc, show } from "./dom.js";
import { MAX_ATTEMPTS, critiqueFailed, failedNotice, gauges, overallBlock } from "./scores.js";
import { currentEpoch, update, watch } from "./state.js";
import { toast } from "./toast.js";

function filters() {
  return {
    occasion: $("#filter-occasion").value.trim(),
    from_date: $("#filter-from").value,
    to_date: $("#filter-to").value,
  };
}

export async function loadSaved() {
  const f = filters();
  if (f.from_date && f.to_date && f.from_date > f.to_date) {
    return toast("The “from” date must be on or before the “to” date.", "error");
  }
  const epoch = currentEpoch();
  const result = await api.looks(f);
  if (epoch !== currentEpoch()) return;
  if (!result.ok) return toast(result.message, "error");
  update(() => ({ saved: result.data?.looks ?? [] }));
}

function weatherLine(w) {
  if (!w || w.available === false) return "Generated without weather guidance";
  const temp = typeof w.temperature_f === "number" ? `${Math.round(w.temperature_f)}°F` : "";
  return `Generated for ${[temp, w.condition_label].filter(Boolean).join(", ")} · ${w.location_name ?? ""}`;
}

function detail(look) {
  return h("div", { class: "saved-detail" },
    critiqueFailed(look.critique) ? failedNotice() : gauges(look.critique),
    critiqueFailed(look.critique) ? null : h("p", { class: "summary" }, String(look.critique.summary ?? "")),
    look.unresolved?.length
      ? h("div", { class: "unresolved-banner" }, h("strong", {}, "Unresolved when saved"),
        look.unresolved.map((m) => h("div", {}, String(m.explanation ?? ""))))
      : null,
    h("div", { class: "pieces" }, (look.pieces ?? []).map((p) => h("span", { class: "piece" }, String(p.name ?? "")))),
    h("p", { class: "hint" }, `Brief: ${look.brief?.aesthetic ?? ""} · ${look.brief?.styling_preference ?? ""}`),
    h("p", { class: "hint mono" }, `Final critique from attempt ${look.critique?.attempt ?? "?"} of ${MAX_ATTEMPTS}`));
}

async function remove(look) {
  const result = await api.deleteLook(look.id);
  if (!result.ok) return toast(result.message, "error");
  update((s) => ({ saved: s.saved.filter((x) => x.id !== look.id) }));
  toast("Look deleted.", "success");
  $("#filter-occasion").focus();
}

function deleteControls(look) {
  const wrap = h("span", { class: "saved-actions" });
  const ask = () => {
    const confirm = h("button", { type: "button", class: "btn btn-danger btn-small confirm-delete", onclick: () => remove(look) }, "Confirm delete");
    replace(wrap, confirm, h("button", { type: "button", class: "btn btn-ghost btn-small", onclick: () => reset(true) }, "Cancel"));
    confirm.focus();
  };
  function reset(focus = false) {
    const del = h("button", { type: "button", class: "btn btn-ghost btn-small delete-look", onclick: ask }, "Delete");
    replace(wrap, del);
    if (focus) del.focus();
  }
  reset();
  return wrap;
}

function savedItem(look) {
  const holder = h("div", { class: "saved-detail-holder", hidden: true });
  const toggle = h("button", { type: "button", class: "btn btn-ghost btn-small", "aria-expanded": "false" }, "Details");
  toggle.addEventListener("click", () => {
    const open = holder.hidden;
    if (open && !holder.firstChild) holder.append(detail(look));
    holder.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  });
  return h("li", { class: "saved-item" },
    h("img", { src: safeImageSrc(look.image_data_url), alt: `Saved look for ${look.occasion}`, loading: "lazy" }),
    h("div", { class: "saved-info" },
      h("span", { class: "saved-title" }, String(look.occasion ?? "Saved look")),
      h("span", { class: "saved-meta" }, `${look.event_date ?? ""} ${look.event_time ?? ""}`.trim()),
      h("span", { class: "saved-meta" }, weatherLine(look.weather)),
      overallBlock({ critique: look.critique, unresolved: look.unresolved }),
      h("div", { class: "saved-actions" }, toggle, deleteControls(look))),
    holder);
}

// The drawer is modal: the page behind it is made inert so Tab stays inside it.
const BACKGROUND = [".topbar", ".workbench"];
let opener = null;

function setBackgroundInert(inert) {
  BACKGROUND.forEach((selector) => { $(selector).inert = inert; });
}

function openDrawer() {
  opener = document.activeElement;
  show($("#saved-drawer"), true);
  show($("#scrim"), true);
  setBackgroundInert(true);
  loadSaved();
  $("#close-saved").focus();
}

export function closeDrawer() {
  if ($("#saved-drawer").hidden) return;
  show($("#saved-drawer"), false);
  show($("#scrim"), false);
  setBackgroundInert(false);
  if (opener?.isConnected && !opener.closest("[hidden]")) opener.focus();
  opener = null;
}

export function initSaved() {
  $("#open-saved").addEventListener("click", openDrawer);
  $("#close-saved").addEventListener("click", closeDrawer);
  $("#scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#saved-drawer").hidden) closeDrawer();
  });
  $("#filter-form").addEventListener("submit", (event) => {
    event.preventDefault();
    loadSaved();
  });
  document.addEventListener("fitlab:look-saved", () => {
    if (!$("#saved-drawer").hidden) loadSaved();
  });
  watch((s) => s.saved, (looks) => replace($("#saved-list"), looks.map(savedItem)));
}
