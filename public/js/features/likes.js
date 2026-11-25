/* Liking and disliking outfits. */
"use strict";

async function rate(o, value){
  const next = o.liked === value ? null : value;
  try {
    const updated = adoptOutfit(await api(`/api/outfits/${o.id}`, {method: "PATCH", body: {liked: next}}));
    const i = O.findIndex(x => x.id === o.id);
    O[i] = updated; reindex();
    toast(next === true ? "Liked" : next === false ? (current === "outfits" && !showDisliked ? "Disliked, and hidden. “Show disliked” brings it back." : "Disliked") : "Rating cleared");
  } catch (e) { toast(e.message, true); }
  refresh();
}

/* Like and Dislike, on a card (which names its outfit) or on an outfit's page. */
function handleRateClick(e){
  const r = e.target.closest("[data-rate]");
  if (!r) return false;
  const id = r.dataset.rateId || (location.hash.match(/^#outfit-(\d+)$/) || [])[1];
  if (id && outById[id]) rate(outById[id], r.dataset.rate === "true");
  return true;
}
