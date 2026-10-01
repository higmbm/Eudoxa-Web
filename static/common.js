// Reload the page when Firefox (or any browser) restores it from bfcache,
// so that the displayed data is always fresh after back/forward navigation.
window.addEventListener("pageshow", function (event) {
  if (event.persisted) {
    window.location.reload();
  }
});

// Explain why an Apply request failed when the failure is NOT a collision
// (collisions are reported by the caller from json.colls). `res` is the
// fetch Response, or null if fetch itself threw (no response at all); `json`
// is the parsed body, or {} when the body wasn't JSON — e.g. the HTML page a
// hosting proxy returns on a timeout.
function applyFailureMessage(res, json) {
  const notColl = "This is not a collision in your relations.";
  if (!res) {
    return "No response from the server (network problem or lost connection). "
         + "Your changes were most likely not saved. " + notColl;
  }
  if (json && json.error) {
    return `The server rejected the changes (HTTP ${res.status}): ${json.error}`;
  }
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    return `The server did not respond in time (HTTP ${res.status}). `
         + "Your changes were most likely not saved. " + notColl + " "
         + "The server may be busy; try again in a little while.";
  }
  return `Unexpected server error (HTTP ${res.status}). `
       + "Your changes were most likely not saved. " + notColl;
}