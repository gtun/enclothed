/* TEMPLATE: one garment in the wardrobe's List view: photo on the left, details on the right. */
"use strict";

function garmentRow(g){
  const s = setById[g.set_id];
  const colors = [["", g.primary_color], ...g.secondary_colors.map(c => ["", c]), ...g.accent_colors.map(c => ["accent ", c])]
    .map(([kind, c]) => `<span><span class="chip" style="background:${hex(c)}"></span>${esc(kind)}${esc(colorName(c))}</span>`).join("");
  const materials = g.materials.map(m => `${m.part ? esc(m.part) + ": " : ""}${m.fibers.map(f => `${esc(f.fiber)} ${f.percent}%`).join(", ")}`).join(" · ");
  const n = (outfitsOf[g.id] || []).length;
  const picked = builder.pieces.includes(g.id);
  return `<article class="grow${picked ? " picked" : ""}">
    <a class="ph" href="#garment-${g.id}" aria-label="${esc(title(g))}">${ph(g, thumb(g))}${SHOW_IDS ? `<span class="badge id">#${g.id}</span>` : ""}</a>
    ${pickButton(g)}
    <div class="gbody">
      <span class="eyebrow">${esc(categoryName(g.category))} · ${esc(subcategoryName(g.subcategory))}${s ? ` · ${esc(setName(s))}` : ""}</span>
      <h3><a href="#garment-${g.id}">${esc(title(g))}</a></h3>
      <div class="colors">${colors}</div>
      <div class="facts">
        ${materials ? `<span><b>Materials</b> ${materials}</span>` : ""}
        <span><b>Formality</b> ${g.formality ? esc(levelLabel(OPT.formality, g.formality)) : "—"}</span>
        <span><b>Warmth</b> ${g.warmth ? esc(warmthShort(levelLabel(OPT.warmth, g.warmth))) : "—"}</span>
        <span>${wearsAndOutfits(g, n)}</span>
      </div>
      <p class="gnotes">${linkify(g.styling_notes)}</p>
    </div>
  </article>`;
}
