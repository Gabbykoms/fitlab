// FitLab front-end entry (spec.md §3.6). Talks only to same-origin /api/*;
// holds no credentials, provider names or provider URLs.
import { setUnauthorizedHandler } from "./js/api.js";
import { checkSession, initAuth, signOutLocally } from "./js/auth.js";
import { initBrief } from "./js/brief.js";
import { $, show } from "./js/dom.js";
import { cancelRemixes, initRemix } from "./js/remix.js";
import { cancelGeneration, initResults, startGenerate } from "./js/results.js";
import { closeDrawer, initSaved, loadSaved } from "./js/saved.js";
import { getState, resetForSignOut } from "./js/state.js";
import { toast } from "./js/toast.js";
import { clearUploadQueue, initWardrobe, loadWardrobe } from "./js/wardrobe.js";

function onSignedIn(user) {
  $("#user-badge").textContent = user.username;
  show($("#session-actions"), true);
  show($("#wardrobe-panel"), true);
  loadWardrobe();
  loadSaved();
}

function onSignedOut() {
  cancelGeneration();
  cancelRemixes();
  closeDrawer();
  clearUploadQueue();
  resetForSignOut();
  show($("#session-actions"), false);
  show($("#wardrobe-panel"), false);
  $("#user-badge").textContent = "";
}

let sessionExpiredShown = false;
setUnauthorizedHandler(() => {
  // A late 401 from a request sent before an explicit sign-out is expected, not an expiry.
  if (sessionExpiredShown || !getState().user) return;
  sessionExpiredShown = true;
  toast("Please sign in again.", "error");
  signOutLocally();
  setTimeout(() => { sessionExpiredShown = false; }, 1000);
});

initAuth({ onSignedIn, onSignedOut });
initBrief({ onSubmit: startGenerate });
initWardrobe();
initResults();
initRemix();
initSaved();
checkSession();
