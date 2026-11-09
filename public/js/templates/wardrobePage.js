/* TEMPLATE: the wardrobe page (heading, stats, filters, one rail per category). */
"use strict";

let cat = "all", scope = "any";
let wview = store.get("enclothed-wardrobe-view", "grid");   // "grid", "large" or "list"
function wardrobe(){
  if (!OWNED.length) return `<div class="state"><h1>Your wardrobe is empty</h1><p>Photograph a garment to add it.</p><p><button type="button" class="btn primary" data-add-garment>+ Add garment</button> ${disownedLink("disowned-garments", "Disowned", DISOWNED.length)}</p></div>`;
  const inScope = g => scope === "any" || (scope === "sets" && g.set_id) || (scope === "unstyled" && !outfitsOf[g.id]);
  const pool = OWNED.filter(inScope);
  const cats = RAIL_ORDER.filter(c => OWNED.some(g => g.category === c));
  const brands = new Set(OWNED.map(g => g.brand).filter(Boolean)).size;
  const nUnstyled = OWNED.filter(g => !outfitsOf[g.id]).length, nSet = OWNED.filter(g => g.set_id).length;
  const btn = (k, v, label, n) => `<button type="button" data-${k}="${esc(v)}" aria-pressed="${(k==='cat'?cat:scope)===v}">${esc(label)} <span>${n}</span></button>`;
  const rails = cats.filter(c => cat === "all" || c === cat).map(c => {
    const items = pool.filter(g => g.category === c);
    const body = wview === "list" ? `<div class="glist">${items.map(garmentRow).join("")}</div>`
               : `<div class="grid${wview === "large" ? " large" : ""}">${items.map(gCard).join("")}</div>`;
    return items.length ? `<section class="rail" id="rail-${esc(c)}"><h2>${esc(categoryName(c))} <span>${items.length}</span></h2>${body}</section>` : "";
  }).join("") || `<p class="empty">Nothing matches these filters.</p>`;
  return `<header class="hero"><div><h1>The wardrobe</h1><p class="sub">Every garment, as tagged from its photos. Open one to see its set, every outfit it has been styled into, and to correct any tag.</p>
      <div class="hero-actions"><button type="button" class="btn primary" data-add-garment>+ Add garment</button><button type="button" class="btn" data-weigh-garment title="Uses AI (spends tokens)">Should I get this?</button><button type="button" class="btn" data-builder-open>${builder.open ? "Outfit builder is open" : "Put together an outfit"}</button>${weighLink()}${disownedLink("disowned-garments", "Disowned", DISOWNED.length)}</div></div>
    <div class="stats"><div><b>${OWNED.length}</b>garments</div><div><b>${brands}</b>brands</div><div><b>${SETS.length}</b>sets</div><div><b>${SHOWN.length}</b>outfits</div></div></header>
    <div class="filters" role="toolbar" aria-label="Filter garments">
      ${btn("cat","all","All",pool.length)}${cats.map(c => btn("cat", c, categoryName(c), pool.filter(g => g.category === c).length)).join("")}
      <span class="sep" aria-hidden="true"></span>
      ${btn("scope","any","Any",OWNED.length)}${btn("scope","sets","In a set",nSet)}${btn("scope","unstyled","Not in any outfit",nUnstyled)}
      <div class="seg viewseg" role="group" aria-label="View">${[["grid", "Grid"], ["large", "Large"], ["list", "List"]].map(([v, label]) =>
        `<button type="button" data-wview="${v}" aria-pressed="${wview === v}">${label}</button>`).join("")}</div>
    </div>
    <main style="display:flex;flex-direction:column;gap:30px">${rails}</main>`;
}
