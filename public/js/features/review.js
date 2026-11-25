/* The review dialog: check what the AI found, change anything, then accept. Its markup is in
   templates/reviewDialog.js. Editors act on review.g, a copy, so nothing is saved before Accept. */
"use strict";

let review = {open: false};
let mendingId = null;
/* The AI's mend answers not yet saved, by garment ID. They were paid for, so closing the review keeps them, and the
   garment page's Review mend button shows them again without another call. Accepting clears them; so does a reload. */
const mendAnswers = {};

function openReview(details){
  review = {open: true, busy: false, confirming: false, error: "", ...details};
  const ov = dialogOverlay("review", ov => {
    ov.addEventListener("click", reviewClick);
    ov.addEventListener("keydown", e => {
      if (e.key !== "Escape" || review.busy || e.target.closest(".cb, .multi, .mats, textarea")) return;
      if (review.mode !== "mend") askToCancel();   // a mend review closes only through Cancel (see reviewClick)
    });
  });
  showOverlay(ov);
  renderReview();
  ov.querySelector("[data-r-accept]").focus();
}
function closeReview(){
  const mending = review.mode === "mend";
  if (review.mode === "new" || review.mode === "weigh") review.photos.forEach(url => URL.revokeObjectURL(url));
  review = {open: false};
  hideOverlay(document.getElementById("review"));
  if (mending) refresh();   // the garment page's button: Mend, or Review mend while answers are kept
}
function renderReview(){
  const ov = document.getElementById("review");
  const scroller = ov.querySelector(".bbody"), top = scroller ? scroller.scrollTop : 0;
  ov.innerHTML = reviewDialog();
  ov.querySelector(".bbody").scrollTop = top;
}
function askToCancel(){
  review.confirming = true; renderReview();
  review.open && document.querySelector("#review [data-r-keep]").focus();
}
async function acceptReview(){
  review.busy = true; review.error = ""; renderReview();
  try {
    if (review.mode === "weigh"){
      // The draft stays on the server until this succeeds, so a failed call can simply be tried again.
      const weighed = await api("/api/weighs", {method: "POST", body: {draft_id: review.draftId, garment: review.g}});
      adoptWeigh(weighed);
      closeReview();
      location.hash = "#weigh-" + weighed.candidate.id;
    } else if (review.mode === "new"){
      const added = await api(`/api/garments/drafts/${review.draftId}`, {method: "POST", body: review.g});
      G.push(added); reindex();
      closeReview();
      toast("Added to your wardrobe.");
      location.hash = "#garment-" + added.id;
    } else {
      const changes = Object.fromEntries(review.fields.filter(f => hasValue(review.g[f])).map(f => [f, review.g[f]]));
      if (Object.keys(changes).length) adoptGarment(await api(`/api/garments/${review.g.id}`, {method: "PATCH", body: changes}));
      delete mendAnswers[review.g.id];
      closeReview();
      toast("Saved.");
    }
  } catch (e) {
    review.busy = false; review.error = e.message; renderReview();
  }
}
async function discardReview(){
  if (review.mode === "mend"){   // nothing on the server to delete, and the AI's answers stay in mendAnswers
    closeReview();
    return toast("Not saved. Review mend shows the AI's answers again.");
  }
  review.busy = true; renderReview();
  try {
    await api(`/api/garments/drafts/${review.draftId}`, {method: "DELETE"});
    closeReview();
    toast("Discarded. Nothing was saved.");
  } catch (e) {
    review.busy = false; review.confirming = false; review.error = e.message; renderReview();
  }
}
/* A click on the backdrop asks before closing a new garment, and does nothing in a mend review: that closes only
   through Cancel (or ×) and then "Yes, close", so a stray click or Escape can't close it. */
function reviewClick(e){
  if (review.busy) return;
  if (e.target.id === "review"){ if (review.mode !== "mend") askToCancel(); return; }
  const ed = e.target.closest("[data-edit]");
  if (ed) return openEditor(ed.dataset.edit);
  if (e.target.closest("[data-r-accept]")) acceptReview();
  else if (e.target.closest("[data-r-cancel]")) askToCancel();
  else if (e.target.closest("[data-r-keep]")){ review.confirming = false; renderReview(); }
  else if (e.target.closest("[data-r-discard]")) discardReview();
}
/* The kept answers for blanks the garment still has, or null. Blanks filled in on the page since are left out. */
function mendAnswersFor(g){
  const kept = Object.entries(mendAnswers[g.id] || {}).filter(([field]) => g.blank_fields.includes(field));
  return kept.length ? Object.fromEntries(kept) : null;
}
function reviewMend(g, filled){
  openReview({mode: "mend", g: {...structuredClone(g), ...filled}, fields: g.blank_fields, photos: g.photos.map(p => p.thumb_url)});
}
/* The garment page's Mend button. With answers kept from an earlier mend, it shows those again and calls nothing. */
async function startMend(g){
  if (mendingId) return;
  const kept = mendAnswersFor(g);
  if (kept) return reviewMend(g, kept);
  mendingId = g.id; refresh();
  try {
    const {filled} = await api(`/api/garments/${g.id}/mend`, {method: "POST"});
    if (!Object.keys(filled).length) return toast("The AI couldn't fill in anything else from the photos.");
    mendAnswers[g.id] = filled;
    reviewMend(g, filled);
  } catch (e) {
    toast(e.message, true);
  } finally {
    mendingId = null;
    if (!review.open) refresh();
  }
}

/* The garment page's Mend button, or Review mend once answers are kept. */
function handleMendClick(e){
  if (!e.target.closest("[data-mend]")) return false;
  const g = currentGarment();
  if (g) startMend(g);
  return true;
}
