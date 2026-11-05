/* TEMPLATE pieces used on several pages: a garment photo, the palette stripe. */
"use strict";

function ph(g, src, eager){
  return src ? `<img src="${esc(encodeURI(src))}" alt="" ${eager ? "" : 'loading="lazy"'} decoding="async">`
             : `<span class="sw" style="background:${hex(g.primary_color)}"></span>`;
}
/* Garments you no longer own, where old links still show them. Each place's choice is in settings.js. */
const showDisowned = (g, place) => !isDisowned(g) || SETTINGS.disowned[place] !== "hide";
const fadeClass = g => isDisowned(g) ? " disowned" : "";
const goneMark = g => isDisowned(g) ? `<span class="gone">no longer owned</span>` : "";
function palette(o){
  const seg = [];
  o.pieces.forEach(p => { const c = byId[p.id]?.primary_color; const last = seg[seg.length-1]; if (last && last.c === c) last.n++; else seg.push({c, n:1}); });
  return seg;
}
const palBar = (o, cls="") => `<div class="pal ${cls}" role="img" aria-label="Palette: ${esc(palette(o).map(s => colorName(s.c)).join(", "))}">${palette(o).map(s => `<i style="flex:${s.n};background:${hex(s.c)}" title="${esc(colorName(s.c))}"></i>`).join("")}</div>`;
const vPal = o => `<span class="vpal" aria-hidden="true">${palette(o).map(s => `<i style="flex:${s.n};background:${hex(s.c)}"></i>`).join("")}</span>`;
