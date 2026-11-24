/* Share links: the Share button on garment and outfit pages makes a new link, then the dialog offers to copy
   or send it. Each click makes a new link, good for a few days, holding a copy of the page as it is then.
   The shared page itself is share.html and js/share.js. The dialog's markup is in templates/shareDialog.js. */
"use strict";

let shareBusy = false;
function closeShare(){
  const ov = document.getElementById("share"); if (!ov || ov.hidden) return;
  hideOverlay(ov, document.querySelector("[data-share]"));
}
async function openShare(kind, id){
  if (shareBusy) return;
  shareBusy = true;
  const ov = dialogOverlay("share", ov => {
    ov.addEventListener("click", shareClick);
    ov.addEventListener("keydown", e => { e.stopPropagation(); if (e.key === "Escape") closeShare(); });
  });
  ov.innerHTML = shareDialog(kind, null);
  showOverlay(ov);
  ov.querySelector("[data-share-close]").focus();
  try {
    const made = await api("/api/shares", {method: "POST", body: {kind, id}});
    if (ov.hidden) return;   // closed while the link was being made
    ov.innerHTML = shareDialog(kind, {url: location.origin + made.path, expires_at: made.expires_at});
    ov.querySelector("[data-share-copy]").focus();
  } catch (e) {
    closeShare();
    toast(e.message, true);
  } finally {
    shareBusy = false;
  }
}
async function shareClick(e){
  const ov = e.currentTarget;
  if (e.target === ov || e.target.closest("[data-share-close]")) return closeShare();
  const input = ov.querySelector("#share-url"); if (!input) return;
  if (e.target === input) input.select();
  if (e.target.closest("[data-share-copy]")){
    try { await navigator.clipboard.writeText(input.value); toast("Link copied"); }
    catch (err) { input.select(); toast("Couldn't copy: the link is selected, so copy it yourself", true); }
  }
  if (e.target.closest("[data-share-send]")){
    try { await navigator.share({title: document.title.replace(/ · enclothed$/, ""), url: input.value}); }
    catch (err) { if (err.name !== "AbortError") toast("Couldn't open sharing. Copy the link instead.", true); }
  }
}
/* The button on a garment page or an outfit page. Which one comes from the page's address. */
document.addEventListener("click", e => {
  if (!e.target.closest?.("[data-share]")) return;
  const m = location.hash.match(/^#(garment|outfit)-(\d+)$/); if (!m) return;
  openShare(m[1], +m[2]);
});
