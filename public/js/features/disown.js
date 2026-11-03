/* "I no longer own this": asks first, then records today's date on the garment. Its markup is in templates/disownDialog.js.
   "Add this to my wardrobe again" clears the date.
   The garment stays in G because old outfits still show it. OWNED (indexes.js) is everything still in the wardrobe. */
"use strict";

let disowning = false;
function openDisown(g){
  let ov = document.getElementById("disown");
  if (!ov){ ov = document.createElement("div"); ov.id = "disown"; ov.className = "overlay"; document.body.appendChild(ov);
    ov.addEventListener("click", disownClick);
    ov.addEventListener("keydown", e => { if (e.key === "Escape") closeDisown(); }); }
  ov.dataset.id = g.id;
  ov.innerHTML = disownDialog(g);
  ov.hidden = false; document.body.style.overflow = "hidden";
  ov.querySelector("[data-d-no]").focus();
}
function closeDisown(){
  if (disowning) return;
  const ov = document.getElementById("disown"); ov.hidden = true; ov.innerHTML = ""; document.body.style.overflow = "";
  document.querySelector("[data-disown]")?.focus();
}
async function reown(g){
  if (disowning) return;
  disowning = true;
  try {
    adoptGarment(await api(`/api/garments/${g.id}`, {method: "PATCH", body: {disowned_on: null}}));
    renderBuilder();
    toast(`${title(g)} is back in your wardrobe`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    disowning = false;
    refresh();
  }
}
async function disownClick(e){
  if (e.target.id === "disown" || e.target.closest("[data-d-no]")) return closeDisown();
  if (!e.target.closest("[data-d-yes]") || disowning) return;
  const g = byId[e.currentTarget.dataset.id];
  disowning = true;
  e.currentTarget.querySelectorAll("button").forEach(b => { b.disabled = true; });
  try {
    adoptGarment(await api(`/api/garments/${g.id}`, {method: "PATCH", body: {disowned_on: localDay(Date.now())}}));
    builder.pieces = builder.pieces.filter(id => id !== g.id);
    saveBuilder(); renderBuilder();
    disowning = false; closeDisown();
    toast(`${title(g)} removed from your wardrobe`);
    if (location.hash === "#wardrobe") refresh(); else location.hash = "#wardrobe";
  } catch (err) {
    disowning = false; closeDisown();
    toast(err.message, true);
  }
}
