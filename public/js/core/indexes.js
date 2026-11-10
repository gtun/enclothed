/* Lookups rebuilt after every change (garments by id, outfits per garment, requests), plus outfit-level formality and warmth. */
"use strict";

function adoptOutfit(o){
  o.pieces = o.garments.map(x => ({id: x.garment.id, advice: x.styling_advice, anchor: x.is_anchor}));
  return o;
}
const isDisowned = g => !!g?.disowned_on;
/* A garment being weighed (weigh, "should I buy this?") isn't owned, so it's in none of the wardrobe's lists.
   The outfits built around it live on its weigh page until it's bought, then they become ordinary outfits. */
const isCandidate = g => !!g?.weighed_on;
const candidateOf = o => o.pieces.map(p => byId[p.id]).find(isCandidate);
/* An outfit with a piece you no longer own lives on the Disowned outfits page, not the Outfits page. Its own link still works. */
const outfitHidden = o => o.pieces.some(p => isDisowned(byId[p.id])) || !!candidateOf(o);
function reindex(){
  byId = Object.fromEntries(G.map(g => [g.id, g]));
  OWNED = G.filter(g => !isDisowned(g) && !isCandidate(g));
  DISOWNED = G.filter(isDisowned);
  CANDIDATES = G.filter(isCandidate);
  weighById = Object.fromEntries(WEIGHS.map(w => [w.garment_id, w]));
  lookById = Object.fromEntries(LOOKS.map(l => [l.id, l]));
  lookOfOutfit = {};
  LOOKS.forEach(l => l.recreations.forEach(r => { lookOfOutfit[r.outfit_id] = l; }));
  SHOWN = O.filter(o => !outfitHidden(o));
  DISOWNED_O = O.filter(o => outfitHidden(o) && !candidateOf(o));
  weighOutfitsOf = {};
  O.forEach(o => { const c = candidateOf(o); if (c) (weighOutfitsOf[c.id] ||= []).push(o); });
  outById = Object.fromEntries(O.map(o => [o.id, o]));
  setById = Object.fromEntries(SETS.map(s => [s.id, s]));
  O.forEach(o => o.pieces.sort((a, b) => catRank(byId[a.id]) - catRank(byId[b.id])));
  outfitsOf = {};
  allOutfitsOf = {};
  O.filter(o => !candidateOf(o)).forEach(o => o.pieces.forEach(p => (allOutfitsOf[p.id] ||= []).push({o, advice: p.advice, anchor: p.anchor})));
  outfitsOf = Object.fromEntries(Object.entries(allOutfitsOf).map(([id, uses]) => [id, uses.filter(u => !outfitHidden(u.o))]).filter(([, uses]) => uses.length));
  REQUESTS = [];
  SHOWN.forEach(o => { let r = REQUESTS.find(x => x.text === o.prompt_message); if (!r) REQUESTS.push(r = {text: o.prompt_message, items: []}); r.items.push(o); });
  REQUESTS.forEach((r, i) => r.key = "r" + i);
  applyLlmColors();   // AI button color can depend on the wardrobe (settings.js)
}
/* A garment's wears are its outfits' wears added up: every outfit it's in except weigh's, since a wear of an
   outfit is a wear of each piece in it, whether or not the outfit is shown. */
const garmentWears = g => (allOutfitsOf[g.id] || []).reduce((n, u) => n + u.o.wear_count, 0);
/* "3 wears, 5 outfits" once a garment is in any outfit; "no outfits" before that. */
const wearsAndOutfits = (g, n) => n ? `${plural(garmentWears(g), "wear")}, ${plural(n, "outfit")}` : "no outfits";
const reqOf = o => REQUESTS.find(r => r.text === o.prompt_message);
const visible = o => showDisliked || o.liked !== false;


/* An outfit can only be as formal as its least formal piece (a garment's formality is the most
   formal occasion it can serve), and it's as warm as its warmest top layer (outerwear, top, or
   one-piece; bottoms, shoes and accessories rarely decide the temperature). Pieces without a
   value are ignored. Both are computed from the garments, so they stay right after edits. */
const WARM_LAYERS = new Set(["outerwear", "top", "one-piece"]);
function outfitFormality(o){ const v = o.pieces.map(p => byId[p.id]?.formality).filter(Boolean); return v.length ? Math.min(...v) : null; }
function outfitWarmth(o){ const v = o.pieces.map(p => byId[p.id]).filter(g => g && WARM_LAYERS.has(g.category) && g.warmth).map(g => g.warmth); return v.length ? Math.max(...v) : null; }
