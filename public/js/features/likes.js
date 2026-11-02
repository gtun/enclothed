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
