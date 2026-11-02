/* Lookups rebuilt after every change (garments by id, outfits per garment, requests), plus outfit-level formality and warmth. */
"use strict";

function adoptOutfit(o){
  o.pieces = o.garments.map(x => ({id: x.garment.id, advice: x.styling_advice, anchor: x.is_anchor}));
  return o;
}
function reindex(){
  byId = Object.fromEntries(G.map(g => [g.id, g]));
  outById = Object.fromEntries(O.map(o => [o.id, o]));
  setById = Object.fromEntries(SETS.map(s => [s.id, s]));
  O.forEach(o => o.pieces.sort((a, b) => catRank(byId[a.id]) - catRank(byId[b.id])));
  outfitsOf = {};
  O.forEach(o => o.pieces.forEach(p => (outfitsOf[p.id] ||= []).push({o, advice: p.advice, anchor: p.anchor})));
  REQUESTS = [];
  O.forEach(o => { let r = REQUESTS.find(x => x.text === o.prompt_message); if (!r) REQUESTS.push(r = {text: o.prompt_message, items: []}); r.items.push(o); });
  REQUESTS.forEach((r, i) => r.key = "r" + i);
}
const reqOf = o => REQUESTS.find(r => r.text === o.prompt_message);
const visible = o => showDisliked || o.liked !== false;


/* An outfit can only be as formal as its least formal piece (a garment's formality is the most
   formal occasion it can serve), and it's as warm as its warmest top layer (outerwear, top, or
   one-piece; bottoms, shoes and accessories rarely decide the temperature). Pieces without a
   value are ignored. Both are computed from the garments, so they stay right after edits. */
const WARM_LAYERS = new Set(["outerwear", "top", "one-piece"]);
function outfitFormality(o){ const v = o.pieces.map(p => byId[p.id]?.formality).filter(Boolean); return v.length ? Math.min(...v) : null; }
function outfitWarmth(o){ const v = o.pieces.map(p => byId[p.id]).filter(g => g && WARM_LAYERS.has(g.category) && g.warmth).map(g => g.warmth); return v.length ? Math.max(...v) : null; }
