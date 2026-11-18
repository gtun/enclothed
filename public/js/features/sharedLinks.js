/* The Shared links page: loads your live share links and handles copying and revoking. Its markup is in templates/sharedLinksPage.js.
   Revoke asks first, in the row itself (like deleting a look): sharedLinks.confirm is the token waiting for "Yes". */
"use strict";

let sharedLinks = {rows: null, error: "", demo: false, confirm: null, busy: null};
let sharedLinksRequest = 0;   // the latest load, so a slow answer from an earlier visit is ignored

async function loadSharedLinks(){
  const id = ++sharedLinksRequest;
  sharedLinks.confirm = null;
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
async function revokeLink(token){
  if (sharedLinks.busy) return;
  sharedLinks.busy = token; refresh();
  try {
    await api(`/api/shares/${encodeURIComponent(token)}`, {method: "DELETE"});
    sharedLinks.rows = sharedLinks.rows.filter(row => row.token !== token);
    toast("Link revoked. It no longer works.");
  } catch (e) {
    toast(e.message, true);
    loadSharedLinks();   // it may have expired meanwhile: show the list as it is now
  } finally {
    sharedLinks.busy = null; sharedLinks.confirm = null;
    if (current === "shared") refresh();
  }
}
function handleSharedLinksClick(e){
  const t = e.target.closest("[data-copy-share],[data-revoke],[data-revoke-yes],[data-revoke-no]");
  if (!t) return false;
  if (t.hasAttribute("data-copy-share")){
    const url = location.origin + t.dataset.copyShare;
    navigator.clipboard.writeText(url).then(() => toast("Link copied"),
      () => toast(`Couldn't copy. The link is ${url}`, true));
  }
  else if (t.hasAttribute("data-revoke")){ sharedLinks.confirm = t.dataset.revoke; refresh(); }
  else if (t.hasAttribute("data-revoke-no")){ sharedLinks.confirm = null; refresh(); }
  else if (t.hasAttribute("data-revoke-yes")) revokeLink(t.dataset.revokeYes);
  return true;
}
