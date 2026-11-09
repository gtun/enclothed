/* weigh ("should I buy this?"): starting one, and the Get / Pass actions. The photos and
   review reuse the Add garment dialogs (upload.js, review.js) with purpose "weigh". Markup: templates/weighPages.js. */
"use strict";

let weighBusy = false;
const currentCandidate = () => { const m = location.hash.match(/^#weigh-(\d+)$/); return m ? byId[m[1]] : null; };

/* After the review dialog's "Weigh it": the server saves the candidate, its verdict and outfits together. */
function adoptWeigh({weigh, candidate, outfits}){
  G.push(candidate);
  O.push(...outfits.map(adoptOutfit));
  WEIGHS.unshift(weigh);
  reindex();
}
async function buyWeighed(g){
  weighBusy = true; refresh();
  try {
    const owned = await api(`/api/weighs/${g.id}/buy`, {method: "POST"});
    WEIGHS = WEIGHS.filter(w => w.garment_id !== g.id);
    adoptGarment(owned);   // its outfits become ordinary outfits now that it's owned
    toast("Added to your wardrobe, with its outfits.");
    location.hash = "#garment-" + g.id;
  } catch (e) {
    toast(e.message, true);
  } finally {
    weighBusy = false; weighConfirm = false;
    if (location.hash.startsWith("#weigh")) refresh();
  }
}
async function passWeighed(g){
  weighBusy = true; refresh();
  try {
    await api(`/api/weighs/${g.id}`, {method: "DELETE"});
    const gone = new Set((weighOutfitsOf[g.id] || []).map(o => o.id));
    G = G.filter(x => x.id !== g.id);
    O = O.filter(o => !gone.has(o.id));
    WEIGHS = WEIGHS.filter(w => w.garment_id !== g.id);
    reindex();
    toast("Deleted. Nothing was added to your wardrobe.");
    location.hash = "#weighed";
  } catch (e) {
    toast(e.message, true);
  } finally {
    weighBusy = false; weighConfirm = false;
    if (location.hash.startsWith("#weigh")) refresh();
  }
}
function handleWeighClick(e){
  const t = e.target.closest("[data-weigh-garment],[data-weigh-buy],[data-weigh-pass],[data-weigh-pass-yes],[data-weigh-pass-no]");
  if (!t) return false;
  if (t.hasAttribute("data-weigh-garment")){ openUpload("weigh"); return true; }
  const g = currentCandidate(); if (!g || weighBusy) return true;
  if (t.hasAttribute("data-weigh-buy")) buyWeighed(g);
  else if (t.hasAttribute("data-weigh-pass")){ weighConfirm = true; refresh(); }
  else if (t.hasAttribute("data-weigh-pass-no")){ weighConfirm = false; refresh(); }
  else if (t.hasAttribute("data-weigh-pass-yes")) passWeighed(g);
  return true;
}
