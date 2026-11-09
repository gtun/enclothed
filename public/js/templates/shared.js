/* TEMPLATE pieces used on several pages: a garment photo, the palette stripe. */
"use strict";

function ph(g, src, eager){
  return src ? `<img src="${esc(encodeURI(src))}" alt="" ${eager ? "" : 'loading="lazy"'} decoding="async">`
             : `<span class="sw" style="background:${hex(g.primary_color)}"></span>`;
}
/* Garments and outfits named in AI prose, as links (features/garmentPeek.js shows a photo on hover).
   The AI writes "[the camel shearling field jacket](5)" for a garment, and in a weigh verdict
   "[with the black tee and navy jeans](outfit: 52, 71)" for an outfit it built with the candidate; that link
   opens the candidate plus those pieces in the outfit builder. Verdicts from before those rules have bare IDs,
   "(5)" or "(52, 71)", which become the garments' names; with a candidate, a group of two or more becomes an
   outfit link. links=false where the text sits inside another link, such as a card. Unknown IDs keep their text. */
const GARMENT_REF = /\[([^\]\n]+)\]\(outfit:\s*(\d+(?:\s*,\s*\d+)*)\)|\[([^\]\n]+)\]\((\d+)\)|\((\d+(?:\s*,\s*\d+)*)\)/g;
const refIds = text => text.split(",").map(id => +id.trim());
function garmentRefs(text, links = true, candidate = null){
  const named = (label, g) => links ? `<a class="gref" href="#garment-${g.id}" data-gref="${g.id}">${esc(label)}</a>` : esc(label);
  const outfit = (label, ids) => links && candidate && byId[candidate]
    ? `<a class="gref oref" href="#" role="button" data-oref="${[candidate, ...ids.filter(id => id !== candidate)].join(",")}" title="Open in the outfit builder">${esc(label)}</a>` : esc(label);
  let html = "", last = 0;
  for (const m of (text || "").matchAll(GARMENT_REF)){
    let piece;
    if (m[1] !== undefined){ const ids = refIds(m[2]).filter(id => byId[id]); piece = ids.length ? outfit(m[1], ids) : esc(m[1]); }
    else if (m[3] !== undefined) piece = byId[m[4]] ? named(m[3], byId[m[4]]) : esc(m[3]);
    else {
      const gs = refIds(m[5]).map(id => byId[id]);
      if (!gs.every(Boolean)) piece = esc(m[0]);   // "(3)" that isn't a garment stays as typed
      else if (candidate && gs.length > 1) piece = `(${outfit(gs.map(title).join(" + "), gs.map(g => g.id))})`;
      else piece = `(${gs.map(g => named(title(g), g)).join(", ")})`;
    }
    html += esc(text.slice(last, m.index)) + piece;
    last = m.index + m[0].length;
  }
  return html + esc((text || "").slice(last));
}
/* Garments you no longer own, where old links still show them. Each place's choice is in settings.js. */
const showDisowned = (g, place) => !isDisowned(g) || SETTINGS.disowned[place] !== "hide";
const fadeClass = g => isDisowned(g) ? " disowned" : "";
const goneMark = g => isDisowned(g) ? `<span class="gone">no longer owned</span>` : "";
/* A small label after an outfit's name saying the risk tier it was suggested at; nothing for older or hand-built outfits. */
const TIER_TIPS = {safe: "Suggested as a safe choice", stretch: "Suggested as a stretch: one unexpected choice", bold: "Suggested as bold: breaks a styling rule on purpose"};
const tierBadge = o => o.risk_tier ? ` <span class="tier tier-${esc(o.risk_tier)}" title="${esc(TIER_TIPS[o.risk_tier] || "")}">${esc(choiceLabel(OPT.risk_tiers || [], o.risk_tier))}</span>` : "";
function palette(o){
  const seg = [];
  o.pieces.forEach(p => { const c = byId[p.id]?.primary_color; const last = seg[seg.length-1]; if (last && last.c === c) last.n++; else seg.push({c, n:1}); });
  return seg;
}
const palBar = (o, cls="") => `<div class="pal ${cls}" role="img" aria-label="Palette: ${esc(palette(o).map(s => colorName(s.c)).join(", "))}">${palette(o).map(s => `<i style="flex:${s.n};background:${hex(s.c)}" title="${esc(colorName(s.c))}"></i>`).join("")}</div>`;
const vPal = o => `<span class="vpal" aria-hidden="true">${palette(o).map(s => `<i style="flex:${s.n};background:${hex(s.c)}"></i>`).join("")}</span>`;
