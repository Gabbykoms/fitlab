// Single immutable store. update() never edits the current state; it builds a
// new frozen object and notifies subscribers with (next, previous).

const initialState = Object.freeze({
  user: null,
  wardrobe: [],
  selectedItemIds: [],
  location: { source: "none", lat: null, lon: null },
  job: null,          // { id, status, startedAt, brief, options, weather, error }
  remixChoice: [],    // [{ key, optionIndex, piece }]
  revisions: [],      // [{ jobId, status, startedAt, option, error }]
  saved: [],
});

let state = initialState;
const listeners = new Set();

export function getState() {
  return state;
}

/** fn receives the current state and returns the keys to change. */
export function update(fn) {
  const previous = state;
  state = Object.freeze({ ...previous, ...fn(previous) });
  listeners.forEach((listener) => listener(state, previous));
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let sessionEpoch = 0;

/** Async work captures this before awaiting and bails if it changed (sign-out happened). */
export const currentEpoch = () => sessionEpoch;

export function resetForSignOut() {
  sessionEpoch += 1;
  update(() => ({ ...initialState }));
}

/**
 * Subscribe to one slice; callback(slice, state, previousSlice) fires only when
 * that slice's reference changes.
 */
export function watch(selector, callback) {
  return subscribe((next, previous) => {
    if (selector(next) !== selector(previous)) callback(selector(next), next, selector(previous));
  });
}
