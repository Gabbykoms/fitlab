// Sign-in / registration dialog and session lifecycle (FE-2 to FE-4).
// The client only hides panels; the server enforces auth (APP-3).
import { api } from "./api.js";
import { $ } from "./dom.js";
import { update } from "./state.js";
import { toast } from "./toast.js";

const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,40}$/;
const MIN_PASSWORD = 8;

let handlers = { onSignedIn: () => {}, onSignedOut: () => {} };

function setError(message) {
  $("#auth-error").textContent = message;
}

function validate(username, password, mode) {
  if (!USERNAME_PATTERN.test(username)) {
    return "Usernames are 3–40 characters: letters, numbers, dots, dashes or underscores.";
  }
  if (mode === "register" && password.length < MIN_PASSWORD) {
    return `Passwords need at least ${MIN_PASSWORD} characters.`;
  }
  if (!password) return "Please enter your password.";
  return "";
}

function setBusy(busy) {
  $("#login-btn").disabled = busy;
  $("#register-btn").disabled = busy;
}

async function submit(mode) {
  const username = $("#auth-username").value.trim();
  const password = $("#auth-password").value;
  const problem = validate(username, password, mode);
  if (problem) return setError(problem);

  setError("");
  setBusy(true);
  try {
    if (mode === "register") {
      const created = await api.register({ username, password });
      if (!created.ok) return setError(created.message);
    }
    const result = await api.login({ username, password });
    if (!result.ok) return setError(result.message);
    signedIn(result.data);
  } finally {
    setBusy(false);
  }
}

function signedIn(user) {
  $("#auth-password").value = "";
  setError("");
  const dialog = $("#auth-dialog");
  if (dialog.open) dialog.close();
  update(() => ({ user: { id: user.user_id, username: user.username } }));
  handlers.onSignedIn(user);
}

export function openAuthDialog() {
  const dialog = $("#auth-dialog");
  if (!dialog.open) dialog.showModal();
  $("#auth-username").focus();
}

export function signOutLocally() {
  handlers.onSignedOut();
  openAuthDialog();
}

export async function checkSession() {
  const result = await api.me();
  if (result.ok) signedIn(result.data);
  else openAuthDialog();
}

export function initAuth(callbacks) {
  handlers = { ...handlers, ...callbacks };
  const dialog = $("#auth-dialog");
  // Signing in is the only way in, so the dialog cannot be dismissed with Escape.
  dialog.addEventListener("cancel", (event) => event.preventDefault());
  $("#auth-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submit(event.submitter?.value === "register" ? "register" : "login");
  });
  $("#register-btn").addEventListener("click", () => {
    $("#auth-password").setAttribute("autocomplete", "new-password");
  });
  $("#logout-btn").addEventListener("click", async () => {
    const result = await api.logout();
    if (!result.ok && result.status !== 401) {
      // The server session may still be valid, so don't pretend the user is signed out.
      toast("Could not sign out. Please try again.", "error");
      return;
    }
    signOutLocally();
  });
}
