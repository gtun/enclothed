/* TEMPLATE: a single outfit's page. */
"use strict";

function outfitPage(o){
  const found = reqOf(o);
  const r = found && found.items.includes(o) ? found : {items: [o]};   // a hidden outfit isn't in its request's list
  const i = r.items.indexOf(o);
  const prev = r.items[i-1], next = r.items[i+1];
  const names = palette(o).map(s => `<span><i style="background:${hex(s.c)}"></i>${esc(colorName(s.c))}</span>`).join("");
  const rateBtn = (v, icon, label) => `<button type="button" data-rate="${v}" aria-pressed="${o.liked === v}">${icon}${label}</button>`;
  return `<div class="ohead">
      <button type="button" class="back" data-back="outfits">← Outfits</button>
      <p class="req">Asked for <q>${esc(o.prompt_message)}</q> · ${esc(whenLong(o.timestamp))}</p>
      <h1>${esc(o.aesthetic)}</h1>
      ${palBar(o, "big")}<div class="palnames">${names}</div>
      <div class="rate"><div class="seg" role="group" aria-label="Rate this outfit">${rateBtn(true, THUMB_UP, "Like")}${rateBtn(false, THUMB_DOWN, "Dislike")}</div>
        <small>${o.liked === null || o.liked === undefined ? "Not rated" : "Click again to clear"}</small></div>
      <p class="lede">${esc(o.explanation)}</p>
      ${o.missing ? `<div class="missing"><b>To finish the look</b>${esc(o.missing)}</div>` : ""}
      ${r.items.length > 1 ? `<nav class="pager" aria-label="Other options for this request">
        <a href="${prev ? "#outfit-"+prev.id : "#"}" aria-disabled="${!prev}">‹ Prev</a>
        <span>Option ${i+1} of ${r.items.length} for this request</span>
        <a href="${next ? "#outfit-"+next.id : "#"}" aria-disabled="${!next}">Next ›</a></nav>` : ""}
    </div>
    <section class="pieces" aria-label="Pieces">${o.pieces.map(p => { const g = byId[p.id]; if (!g || !showDisowned(g, "outfitPage")) return ""; return `
      <a class="piece" href="#garment-${g.id}">
        <div class="ph${fadeClass(g)}">${ph(g, thumb(g))}${goneMark(g)}<span class="badge id">#${g.id}</span>${g.set_id ? `<span class="badge set" title="Part of a set">${SET_ICON}<b>${esc(setName(setById[g.set_id]))}</b></span>` : ""}</div>
        <span class="eyebrow">${esc(categoryName(g.category))}${p.anchor ? `<span class="anchor" title="You asked for the outfit to be built around this piece">anchor</span>` : ""}</span>
        <span class="nm">${esc(title(g))}</span>
        ${p.advice ? `<p>${esc(p.advice)}</p>` : `<p class="empty">No specific advice for this piece.</p>`}
      </a>`; }).join("")}</section>`;
}
