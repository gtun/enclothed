/* TEMPLATE: one garment card in the wardrobe grid. */
"use strict";

function gCard(g){
  const s = setById[g.set_id];
  const chips = [g.primary_color, ...g.secondary_colors, ...g.accent_colors].filter(Boolean)
    .map(c => `<span class="chip" title="${esc(colorName(c))}" style="background:${hex(c)}"></span>`).join("");
  const gone = isDisowned(g);
  const n = ((gone ? allOutfitsOf : outfitsOf)[g.id] || []).length;
  const picked = builder.pieces.includes(g.id);
  return `<div class="cardwrap${picked ? " picked" : ""}"><a class="card" href="#garment-${g.id}" aria-label="${esc(title(g))}, ${esc(colorName(g.primary_color))}">
    <div class="ph">${ph(g, thumb(g))}${SHOW_IDS ? `<span class="badge id">#${g.id}</span>` : ""}
      ${s ? `<span class="badge set" title="Part of a set: ${esc(setName(s))}">${SET_ICON}<b>${esc(setName(s))}</b></span>` : ""}</div>
    <div class="meta">
      <span class="brand">${esc(g.brand || "unknown brand")}</span>
      <span class="sc">${esc(subcategoryName(g.subcategory))}</span>
      <span class="chips">${chips}</span>
      <span class="row">${gone ? `<span>Disowned ${esc(whenDay(g.disowned_on))}</span>` : `<span class="scales"><span>F${pips(g.formality||0,4)}</span><span>W${pips(g.warmth||0,5)}</span></span><span>${n ? plural(n,"outfit") : "no outfits"}</span>`}</span>
    </div></a>${gone ? "" : `<span class="addlayer">${pickButton(g)}</span>`}</div>`;
}
