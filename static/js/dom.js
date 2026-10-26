// Tiny DOM builder. Text is always set via text nodes, never innerHTML,
// so server-supplied strings cannot inject markup.

/**
 * h("div", { class: "x", dataset: { k: "v" }, onclick: fn, "aria-label": "y" }, child, ...)
 * Children may be strings, numbers, nodes, arrays, or null/false (skipped).
 */
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props ?? {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key === "style") Object.entries(value).forEach(([k, v]) => el.style.setProperty(k, v));
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key in el && typeof value !== "string") el[key] = value;
    else el.setAttribute(key, value === true ? "" : String(value));
  }
  appendAll(el, children);
  return el;
}

function appendAll(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function replace(el, ...children) {
  el.replaceChildren();
  appendAll(el, children);
}

export function show(el, visible = true) {
  el.hidden = !visible;
}

/** Only allow image sources the app itself produced: same-origin paths, data: or blob: URLs. */
export function safeImageSrc(src) {
  if (typeof src !== "string") return "";
  if (/^data:image\/(png|jpeg|webp|gif|svg\+xml);base64,/i.test(src)) return src;
  if (src.startsWith("blob:") || (src.startsWith("/") && !src.startsWith("//"))) return src;
  return "";
}

export function pad2(n) {
  return String(n).padStart(2, "0");
}

export function formatElapsed(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${pad2(Math.floor(s / 60))}:${pad2(s % 60)}`;
}
