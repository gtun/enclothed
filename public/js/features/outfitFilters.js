/* How the outfits-page filters decide what to show. */
"use strict";

let ofilt = {q: "", from: "", to: "", formality: [], warmth: []};
const filtersActive = () => !!(ofilt.q.trim() || ofilt.from || ofilt.to || ofilt.formality.length || ofilt.warmth.length);
const localDay = ts => { const d = new Date(ts); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
function passesFilters(o){
  const q = ofilt.q.trim().toLowerCase();
  if (q && !o.prompt_message.toLowerCase().includes(q)) return false;
  const day = localDay(o.timestamp);
  if (ofilt.from && day < ofilt.from) return false;
  if (ofilt.to && day > ofilt.to) return false;
  if (ofilt.formality.length && !ofilt.formality.includes(outfitFormality(o))) return false;
  if (ofilt.warmth.length && !ofilt.warmth.includes(outfitWarmth(o))) return false;
  return true;
}
