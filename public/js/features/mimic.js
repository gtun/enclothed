/* mimic (recreate a photographed look): sending the photos, then matching the look to the wardrobe, and
   deleting a look. The photo picker reuses the Add garment dialog (upload.js) with purpose "mimic".
   Two requests, one after the other: the dialog shows the first ("Reading the look"), the look's page the second. */
"use strict";

let mimicBusy = null;            // the look being matched right now, if any
const mimicTried = new Set();    // looks matched in this visit that came back with nothing
const currentLook = () => { const m = location.hash.match(/^#look-(\d+)$/); return m ? lookById[m[1]] : null; };

function adoptLook(look){
  LOOKS = [look, ...LOOKS.filter(l => l.id !== look.id)];
  reindex();
}
/* After the dialog's request: the look is saved, so show it and start matching. */
async function lookCreated(look){
  adoptLook(look);
  location.hash = "#look-" + look.id;
  await matchLook(look);
}
async function matchLook(look){
  if (mimicBusy) return;
  mimicBusy = look.id; if (currentLook()?.id === look.id) refresh();
  try {
    const {look: updated, outfits} = await api(`/api/looks/${look.id}/recreations`, {method: "POST"});
    O.push(...outfits.map(adoptOutfit));
    adoptLook(updated);
    if (!outfits.length){ mimicTried.add(look.id); toast("Nothing in your wardrobe could recreate this look.", true); }
  } catch (e) {
    toast(e.message, true);
  } finally {
    mimicBusy = null;
    if (location.hash.startsWith("#look")) refresh();
  }
}
async function deleteLook(look){
  try {
    await api(`/api/looks/${look.id}`, {method: "DELETE"});
    LOOKS = LOOKS.filter(l => l.id !== look.id);
    reindex();
    toast("Look deleted. Its outfits are still under Outfits.");
    location.hash = "#looks";
  } catch (e) {
    toast(e.message, true);
  } finally {
    lookConfirm = false;
    if (location.hash.startsWith("#look")) refresh();
  }
}
function handleMimicClick(e){
  const t = e.target.closest("[data-mimic-look],[data-look-match],[data-look-delete],[data-look-delete-yes],[data-look-delete-no]");
  if (!t) return false;
  if (t.hasAttribute("data-mimic-look")){ openUpload("mimic"); return true; }
  const l = currentLook(); if (!l) return true;
  if (t.hasAttribute("data-look-match")) matchLook(l);
  else if (t.hasAttribute("data-look-delete")){ lookConfirm = true; refresh(); }
  else if (t.hasAttribute("data-look-delete-no")){ lookConfirm = false; refresh(); }
  else if (t.hasAttribute("data-look-delete-yes")) deleteLook(l);
  return true;
}
