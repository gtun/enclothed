/* The Shared links page: loads your live share links and handles its copy buttons. Its markup is in templates/sharedLinksPage.js. */
"use strict";

let sharedLinks = {rows: null, error: "", demo: false};
let sharedLinksRequest = 0;   // the latest load, so a slow answer from an earlier visit is ignored

async function loadSharedLinks(){
  const id = ++sharedLinksRequest;
  try {
    const rows = await api("/api/shares");
    if (id !== sharedLinksRequest) return;
    sharedLinks.rows = rows;
    sharedLinks.error = "";
  } catch (e) {
    if (id !== sharedLinksRequest) return;
    sharedLinks.error = e.message;
  }
  if (current === "shared") refresh();
}
function handleSharedLinksClick(e){
  const copy = e.target.closest("[data-copy-share]");
  if (!copy) return false;
  const url = location.origin + copy.dataset.copyShare;
  navigator.clipboard.writeText(url).then(() => toast("Link copied"),
    () => toast(`Couldn't copy. The link is ${url}`, true));
  return true;
}
