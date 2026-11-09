/* The review dialog: check what the AI found, change anything, then accept. Its markup is in
   templates/reviewDialog.js. Editors act on review.g, a copy, so nothing is saved before Accept. */
"use strict";

let review = {open: false};
let mendingId = null;

function openReview(details){
  review = {open: true, busy: false, confirming: false, error: "", ...details};
  let ov = document.getElementById("review");
  if (!ov){ ov = document.createElement("div"); ov.id = "review"; ov.className = "overlay"; document.body.appendChild(ov);
    ov.addEventListener("click", reviewClick);
    ov.addEventListener("keydown", e => {
      if (e.key !== "Escape" || review.busy || e.target.closest(".cb, .multi, .mats, textarea")) return;
      askToCancel();
    }); }
  ov.hidden = false; document.body.style.overflow = "hidden";
  renderReview();
  ov.querySelector("[data-r-accept]").focus();
}
function closeReview(){
  if (review.mode === "new" || review.mode === "weigh") review.photos.forEach(url => URL.revokeObjectURL(url));
  review = {open: false};
  const ov = document.getElementById("review"); ov.hidden = true; ov.innerHTML = ""; document.body.style.overflow = "";
}
function renderReview(){
  const ov = document.getElementById("review");
  const scroller = ov.querySelector(".bbody"), top = scroller ? scroller.scrollTop : 0;
  ov.innerHTML = reviewDialog();
  ov.querySelector(".bbody").scrollTop = top;
}
function askToCancel(){
  if (review.mode === "mend") return closeReview();
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
      closeReview();
      toast("Saved.");
      refresh();
    }
  } catch (e) {
    review.busy = false; review.error = e.message; renderReview();
  }
}
const hasValue = v => Array.isArray(v) ? v.length > 0 : v !== null && v !== undefined && v !== "";
async function discardReview(){
  review.busy = true; renderReview();
  try {
    await api(`/api/garments/drafts/${review.draftId}`, {method: "DELETE"});
    closeReview();
    toast("Discarded. Nothing was saved.");
  } catch (e) {
    review.busy = false; review.confirming = false; review.error = e.message; renderReview();
  }
}
function reviewClick(e){
  if (review.busy) return;
  if (e.target.id === "review") return askToCancel();
  const ed = e.target.closest("[data-edit]");
  if (ed) return openEditor(ed.dataset.edit);
  if (e.target.closest("[data-r-accept]")) acceptReview();
  else if (e.target.closest("[data-r-cancel]")) askToCancel();
  else if (e.target.closest("[data-r-keep]")){ review.confirming = false; renderReview(); }
  else if (e.target.closest("[data-r-discard]")) discardReview();
}
async function startMend(g){
  if (mendingId) return;
  mendingId = g.id; refresh();
  try {
    const {filled} = await api(`/api/garments/${g.id}/mend`, {method: "POST"});
    if (!Object.keys(filled).length) return toast("The AI couldn't fill in anything else from the photos.");
    openReview({mode: "mend", g: {...structuredClone(g), ...filled}, fields: g.blank_fields, photos: g.photos.map(p => p.thumb_url)});
  } catch (e) {
    toast(e.message, true);
  } finally {
    mendingId = null;
    if (!review.open) refresh();
  }
}
