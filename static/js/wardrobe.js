// Wardrobe tray: drag-drop / picker, local preview, category tagging, upload,
// rejection reasons, selection, delete (FE-8 to FE-11).
import { api } from "./api.js";
import { $, h, replace, safeImageSrc } from "./dom.js";
import { update, watch } from "./state.js";
import { toast } from "./toast.js";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED = ["image/png", "image/jpeg", "image/webp", "image/gif"];
const CATEGORIES = [
  ["", "Category…"], ["top", "Top"], ["bottom", "Bottom"], ["outerwear", "Outerwear"],
  ["shoes", "Shoes"], ["accessory", "Accessory"], ["full_outfit", "Full outfit"],
];

function precheck(file) {
  if (!ACCEPTED.includes(file.type)) return "That file is not a supported image. Please upload a PNG, JPEG, WebP or GIF.";
  if (file.size > MAX_BYTES) return "That file is larger than 10 MB.";
  return "";
}

function uploadRow(file) {
  const preview = URL.createObjectURL(file);
  const category = h("select", { "aria-label": "Category" },
    CATEGORIES.map(([value, label]) => h("option", { value }, label)));
  const label = h("input", { type: "text", maxlength: "80", placeholder: "Label (optional)", "aria-label": "Label" });
  const error = h("p", { class: "upload-error", "aria-live": "polite" }, precheck(file));
  const send = h("button", { type: "button", class: "btn btn-primary btn-small upload-send" }, "Upload");
  const cancel = h("button", { type: "button", class: "btn btn-ghost btn-small" }, "Remove");
  const row = h("li", { class: "upload-row" },
    h("img", { src: preview, alt: `Preview of ${file.name}` }),
    h("div", { class: "upload-fields" }, category, label),
    h("div", { class: "upload-actions" }, send, cancel),
    error);

  const dispose = () => {
    URL.revokeObjectURL(preview);
    row.remove();
  };
  send.disabled = Boolean(error.textContent);
  cancel.addEventListener("click", dispose);
  send.addEventListener("click", async () => {
    if (!category.value) {
      error.textContent = "Choose a category before uploading.";
      category.focus();
      return;
    }
    send.disabled = true;
    send.textContent = "Uploading…";
    const ok = await sendUpload(file, category.value, label.value.trim(), error);
    if (ok) dispose();
    else {
      send.disabled = false;
      send.textContent = "Upload";
    }
  });
  return row;
}

async function sendUpload(file, category, label, errorEl) {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  if (label) form.append("label", label);
  const result = await api.upload(form);
  if (!result.ok) {
    errorEl.textContent = result.message;
    return false;
  }
  if (result.data?.rejected) {
    errorEl.textContent = result.data.reason || "That upload could not be accepted.";
    return false;
  }
  update((s) => ({ wardrobe: [...s.wardrobe, result.data.item] }));
  toast("Added to your wardrobe.", "success");
  return true;
}

function addFiles(files) {
  const queue = $("#upload-queue");
  [...files].forEach((file) => queue.append(uploadRow(file)));
}

function toggleSelected(id) {
  update((s) => ({
    selectedItemIds: s.selectedItemIds.includes(id)
      ? s.selectedItemIds.filter((x) => x !== id)
      : [...s.selectedItemIds, id],
  }));
}

async function removeItem(item) {
  const result = await api.deleteItem(item.id);
  if (!result.ok) return toast(result.message, "error");
  update((s) => ({
    wardrobe: s.wardrobe.filter((x) => x.id !== item.id),
    selectedItemIds: s.selectedItemIds.filter((x) => x !== item.id),
  }));
}

function itemTile(item, selected) {
  const name = item.label || item.category.replace("_", " ");
  return h("li", { class: `wardrobe-item${selected ? " is-selected" : ""}`, dataset: { id: item.id } },
    h("button", {
      type: "button", class: "select-toggle", "aria-pressed": String(selected),
      "aria-label": `${selected ? "Deselect" : "Select"} ${name}`, onclick: () => toggleSelected(item.id),
    }, h("img", { src: safeImageSrc(item.image_data_url), alt: name, loading: "lazy" })),
    h("span", { class: "wardrobe-check", "aria-hidden": "true" }, "✓"),
    h("div", { class: "wardrobe-meta" },
      h("span", { class: "mono", title: name }, name),
      h("button", { type: "button", class: "icon-btn", "aria-label": `Delete ${name}`, onclick: () => removeItem(item) }, "✕")));
}

function render(state) {
  replace($("#wardrobe-grid"), state.wardrobe.map((item) => itemTile(item, state.selectedItemIds.includes(item.id))));
}

export async function loadWardrobe() {
  const result = await api.wardrobe();
  if (!result.ok) return toast(result.message, "error");
  update(() => ({ wardrobe: result.data?.items ?? [], selectedItemIds: [] }));
}

export function initWardrobe() {
  const zone = $("#dropzone");
  const input = $("#file-input");
  input.addEventListener("change", () => {
    addFiles(input.files);
    input.value = "";
  });
  ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (event) => {
    event.preventDefault();
    zone.classList.add("is-over");
  }));
  ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, () => zone.classList.remove("is-over")));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    addFiles(event.dataTransfer?.files ?? []);
  });
  watch((s) => s.wardrobe, (_, s) => render(s));
  watch((s) => s.selectedItemIds, (_, s) => render(s));
}

export function clearUploadQueue() {
  $("#upload-queue").querySelectorAll("img").forEach((img) => URL.revokeObjectURL(img.src));
  replace($("#upload-queue"));
}
