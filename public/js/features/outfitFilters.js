/* The outfits page's filters: what they're set to, how they decide what to show, and their clicks and typing. */
"use strict";

let ofilt = {q: "", from: "", to: "", formality: [], warmth: []};
let filtersOpen = false;   // the filter box starts collapsed on every visit
let req = "all";   // the request whose outfits are shown, by its key, or "all"
/* Who made the outfits shown ("all", "ai" or "own"), and whether to show only outfits you've worn. */
let osrc = "all", wornOnly = false;
/* Back to all requests when the one picked has nothing left to show, after a filter change or a delete. */
function settleRequest(groups){
  if (req !== "all" && !groups.some(r => r.key === req)) req = "all";
}
const activeFilterCount = () => [ofilt.q.trim(), ofilt.from, ofilt.to].filter(Boolean).length + (ofilt.formality.length ? 1 : 0) + (ofilt.warmth.length ? 1 : 0);
const filtersActive = () => !!(ofilt.q.trim() || ofilt.from || ofilt.to || ofilt.formality.length || ofilt.warmth.length);
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

/* The request, source, Worn and disliked buttons, and the filter box's toggle, chips and Clear. */
function handleOutfitFilterClick(e){
  const f = e.target.closest("[data-req],[data-toggle-disliked],[data-osrc],[data-toggle-worn]");
  if (f){
    if (f.dataset.req) req = f.dataset.req;
    if (f.hasAttribute("data-toggle-disliked")){ showDisliked = !showDisliked; store.set("enclothed-show-disliked", showDisliked); }
    if (f.dataset.osrc){ osrc = f.dataset.osrc; req = "all"; }
    if (f.hasAttribute("data-toggle-worn")) wornOnly = !wornOnly;
    refresh(); return true;
  }
  if (e.target.closest("[data-ofilt-toggle]")){ filtersOpen = !filtersOpen; refresh(); if (filtersOpen) document.getElementById("of-q")?.focus(); return true; }
  const of = e.target.closest("[data-ofilt-f],[data-ofilt-w],[data-ofilt-clear]");
  if (!of) return false;
  const toggle = (list, v) => list.includes(v) ? list.filter(x => x !== v) : [...list, v];
  if (of.dataset.ofiltF) ofilt.formality = toggle(ofilt.formality, +of.dataset.ofiltF);
  else if (of.dataset.ofiltW) ofilt.warmth = toggle(ofilt.warmth, +of.dataset.ofiltW);
  else ofilt = {q: "", from: "", to: "", formality: [], warmth: []};
  refresh(); return true;
}
/* Typing in a filter redraws the page, so put the cursor back where it was. */
let filterTimer = null;
document.getElementById("app").addEventListener("input", e => {
  const el = e.target.closest("[data-ofilt]"); if (!el) return;
  ofilt[el.dataset.ofilt] = el.value;
  clearTimeout(filterTimer);
  filterTimer = setTimeout(() => {
    const id = el.id, start = el.selectionStart, end = el.selectionEnd;
    refresh();
    const again = document.getElementById(id);
    if (again){ again.focus(); try { again.setSelectionRange(start, end); } catch (err) {} }
  }, el.type === "date" ? 0 : 200);
});
