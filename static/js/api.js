// Same-origin API client. Every call goes to /api/* on this origin; the client
// never holds credentials (the session is an HttpOnly cookie) and never shows
// a status code or raw JSON to the user (FE-21).

const MESSAGES = {
  network: "Could not reach FitLab. Check your connection and try again.",
  401: "Please sign in again.",
  404: "That request is no longer available.",
  413: "That file is larger than 10 MB.",
  429: "The service is busy right now. Please try again in a minute.",
  503: "The styling service is not configured right now. Please try again later.",
  server: "Something went wrong on our side. Please try again.",
  invalid: "Please check the highlighted fields and try again.",
};

let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

/** A readable sentence from a FastAPI error body, or null if it isn't one. */
function sentenceFrom(detail) {
  if (typeof detail === "string" && detail.length < 300 && !/[{}<>]/.test(detail)) return detail;
  if (Array.isArray(detail) && detail[0]?.loc) {
    const field = String(detail[0].loc.at(-1) ?? "").replaceAll("_", " ");
    return field ? `Please check the ${field} field.` : null;
  }
  return null;
}

function messageFor(status, body) {
  const fromServer = sentenceFrom(body?.detail);
  if (status === 401) return fromServer ?? MESSAGES[401];
  if (status === 422 || status === 400 || status === 409) return fromServer ?? MESSAGES.invalid;
  if (MESSAGES[status]) return MESSAGES[status];
  return status >= 500 ? MESSAGES.server : fromServer ?? MESSAGES.server;
}

/**
 * request("GET", "/api/x") -> { ok, status, data, message }
 * Never throws. `message` is a user-safe sentence when ok is false.
 */
export async function request(method, path, { json, form, query, quiet401 = false } = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(query ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const init = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
  if (json !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(json);
  } else if (form) {
    init.body = form;
  }

  let response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    console.warn("FitLab request failed", method, path, err);
    return { ok: false, status: 0, data: null, message: MESSAGES.network, network: true };
  }

  const data = await response.json().catch(() => null);
  if (response.ok) return { ok: true, status: response.status, data, message: "" };

  if (response.status === 401 && !quiet401) onUnauthorized();
  return { ok: false, status: response.status, data: null, message: messageFor(response.status, data) };
}

export const api = {
  me: () => request("GET", "/api/auth/me", { quiet401: true }),
  login: (body) => request("POST", "/api/auth/login", { json: body, quiet401: true }),
  register: (body) => request("POST", "/api/auth/register", { json: body, quiet401: true }),
  logout: () => request("POST", "/api/auth/logout", { quiet401: true }),
  wardrobe: () => request("GET", "/api/wardrobe"),
  upload: (form) => request("POST", "/api/wardrobe/upload", { form }),
  deleteItem: (id) => request("DELETE", `/api/wardrobe/${encodeURIComponent(id)}`),
  generate: (brief) => request("POST", "/api/outfits/generate", { json: brief }),
  remix: (body) => request("POST", "/api/outfits/remix", { json: body }),
  job: (id) => request("GET", `/api/outfits/${encodeURIComponent(id)}`),
  saveLook: (jobId, optionIndex) => request("POST", "/api/looks", { json: { job_id: jobId, option_index: optionIndex } }),
  looks: (filters) => request("GET", "/api/looks", { query: filters }),
  deleteLook: (id) => request("DELETE", `/api/looks/${encodeURIComponent(id)}`),
};
