/* Logging wears: the "wore it" date picker that the wear buttons open, and removing a wear logged by mistake.
   The buttons are in templates/outfitCard.js (wearButton) and the outfit page lists each wear. */
"use strict";

let wearPop = null;
function closeWearPop(){ wearPop?.remove(); wearPop = null; }
function openWearPop(button, outfitId){
  closeWearPop();
  const today = todayLocal();
  wearPop = Object.assign(document.createElement("div"), {className: "wearpop"});
  wearPop.setAttribute("role", "dialog");
  wearPop.setAttribute("aria-label", "Log a wear");
  wearPop.dataset.outfit = outfitId;
  wearPop.innerHTML = `<label for="wear-day">Wore it on</label><input id="wear-day" class="txt" type="date" value="${today}" max="${today}" required>
    <div class="row"><button type="button" class="btn primary" data-wear-save>Log wear</button><button type="button" class="btn quiet" data-wear-cancel>Cancel</button></div>`;
  document.body.append(wearPop);
  // Under the button, or above it when there's no room; kept inside the window.
  const r = button.getBoundingClientRect(), w = wearPop.offsetWidth, h = wearPop.offsetHeight;
  wearPop.style.top = `${Math.max(8, r.bottom + 8 + h > innerHeight ? r.top - h - 8 : r.bottom + 8)}px`;
  wearPop.style.left = `${Math.min(Math.max(8, r.right - w), innerWidth - w - 8)}px`;
  wearPop.querySelector("input").focus();
}
function replaceOutfit(updated){
  const i = O.findIndex(x => x.id === updated.id);
  O[i] = adoptOutfit(updated); reindex(); refresh();
}
async function saveWear(){
  const input = wearPop.querySelector("input"), id = wearPop.dataset.outfit, day = input.value;
  if (!day) { input.focus(); return; }
  wearPop.querySelectorAll("button, input").forEach(el => el.disabled = true);
  try {
    replaceOutfit(await api(`/api/outfits/${id}/wears`, {method: "POST", body: {worn_on: day}}));
    toast(day === todayLocal() ? "Logged as worn today" : `Logged as worn on ${whenDay(day)}`);
    closeWearPop();
  } catch (e) { toast(e.message, true); wearPop?.querySelectorAll("button, input").forEach(el => el.disabled = false); }
}
async function removeWear(outfitId, wearId){
  try { replaceOutfit(await api(`/api/outfits/${outfitId}/wears/${wearId}`, {method: "DELETE"})); toast("Wear removed"); }
  catch (e) { toast(e.message, true); }
}
document.addEventListener("click", e => {
  const open = e.target.closest?.("[data-wear]");
  if (open){ wearPop?.dataset.outfit === open.dataset.wear ? closeWearPop() : openWearPop(open, open.dataset.wear); return; }
  const unwear = e.target.closest?.("[data-unwear]");
  if (unwear){ removeWear(unwear.dataset.outfit, unwear.dataset.unwear); return; }
  if (!wearPop) return;
  if (e.target.closest("[data-wear-save]")) saveWear();
  else if (e.target.closest("[data-wear-cancel]") || !wearPop.contains(e.target)) closeWearPop();
});
document.addEventListener("keydown", e => {
  if (!wearPop) return;
  if (e.key === "Escape"){ closeWearPop(); e.stopPropagation(); }
  else if (e.key === "Enter" && e.target.id === "wear-day"){ e.preventDefault(); saveWear(); }
}, true);
addEventListener("hashchange", closeWearPop);
