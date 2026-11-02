/* TEMPLATE: a single garment's page, including the list of editable details (FIELDS: labels and order). */
"use strict";

/* Editable fields: how each one shows, and which editor it opens. */
const FIELDS = [
  {key:"category", label:"Category", kind:"category"},
  {key:"subcategory", label:"Subcategory", kind:"subcategory"},
  {key:"brand", label:"Brand", kind:"text", suggest:() => unique(G.map(g => g.brand))},
  {key:"primary_color", label:"Primary color", kind:"color"},
  {key:"secondary_colors", label:"Secondary", kind:"colors"},
  {key:"accent_colors", label:"Accent", kind:"colors"},
  {key:"formality", label:"Formality", kind:"level", list:() => OPT.formality},
  {key:"warmth", label:"Warmth", kind:"level", list:() => OPT.warmth},
  {key:"fit", label:"Fit", kind:"choice", list:() => OPT.fits},
  {key:"sheen", label:"Sheen", kind:"choice", list:() => OPT.sheens},
  {key:"pattern", label:"Pattern", kind:"text", suggest:() => unique(G.map(g => g.pattern))},
  {key:"materials", label:"Materials", kind:"materials"},
  {key:"country_of_origin", label:"Made in", kind:"text", suggest:() => unique(G.map(g => g.country_of_origin))},
];
const colorChip = c => `<span class="cchip"><span class="chip" style="background:${hex(c)}"></span>${esc(c)}</span>`;
function displayValue(g, f){
  const v = g[f.key];
  const none = `<span class="none">—</span>`;
  switch (f.kind){
    case "color": return colorChip(v);
    case "colors": return v.length ? v.map(colorChip).join("") : none;
    case "level": return v ? `${v} · ${esc(levelLabel(f.list(), v))}` : none;
    case "choice": return v ? esc(choiceLabel(f.list(), v)) : none;
    case "materials": return v.length ? v.map(m => `<span style="display:block">${m.part ? `<span class="none">${esc(m.part)}:</span> ` : ""}${m.fibers.map(x => `${esc(x.fiber)} ${x.percent}%`).join(", ")}</span>`).join("") : none;
    default: return v ? esc(v) : none;
  }
}
const evButton = (field, label, inner, cls="") => `<button type="button" class="ev ${cls}" data-edit="${field}" aria-label="Edit ${esc(label)}">${inner}${PEN}</button>`;

function garmentPage(g){
  const s = setById[g.set_id];
  let setPanel = "";
  if (s){
    const others = G.filter(x => x.set_id === s.id && x.id !== g.id);
    const ids = G.filter(x => x.set_id === s.id).map(x => x.id);
    const together = O.filter(o => ids.every(id => o.pieces.some(p => p.id === id))).length;
    setPanel = `<div class="panel"><h4><span style="display:inline-flex;gap:7px;align-items:center">${SET_ICON} Part of a set: ${esc(setName(s))}</span><small>worn together in ${plural(together,"outfit")}</small></h4>
      <div class="inset">${others.map(x => `<a class="mini" href="#garment-${x.id}"><div class="ph">${ph(x, thumb(x))}</div><span>${esc(x.subcategory)}</span><em>#${x.id}</em></a>`).join("")}</div></div>`;
  }
  const allUses = (outfitsOf[g.id] || []).slice().sort((a, b) => b.o.timestamp.localeCompare(a.o.timestamp));
  const uses = allUses.filter(u => visible(u.o));
  const hidden = allUses.length - uses.length;
  const outPanel = `<div class="panel"><h4>In outfits <small>${uses.length ? plural(uses.length,"outfit") : ""}${hidden ? ` · ${hidden} disliked hidden` : ""}</small></h4>
    ${uses.length ? `<div class="olist" tabindex="0" aria-label="Outfits with this garment">${uses.map(u => `
      <a class="orow" href="#outfit-${u.o.id}">${vPal(u.o)}<span><b>${esc(u.o.aesthetic)}</b><span>${u.advice ? esc(u.advice) : esc(u.o.prompt_message)}</span></span><time>${when(u.o.timestamp)}</time></a>`).join("")}</div>`
      : `<p class="empty">${hidden ? "Only in disliked outfits." : "Not in any outfit yet."}</p>`}</div>`;
  const co = {};
  uses.forEach(u => u.o.pieces.forEach(p => { if (p.id !== g.id && byId[p.id] && !(g.set_id && byId[p.id].set_id === g.set_id)) co[p.id] = (co[p.id]||0) + 1; }));
  const top = Object.entries(co).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const coPanel = top.length >= 2 ? `<div class="panel"><h4>Often paired with</h4><div class="inset">${top.map(([id, n]) => { const x = byId[id]; return `<a class="mini" href="#garment-${x.id}"><div class="ph">${ph(x, thumb(x))}</div><span>${esc(x.subcategory)}</span><em>together ${n}×</em></a>`; }).join("")}</div></div>` : "";
  const gallery = g.photos.length ? `<div class="track" id="track" tabindex="0" aria-label="Photos">${g.photos.map((p, i) =>
      `<figure class="slide"><img src="${esc(encodeURI(p.url))}" alt="${esc(title(g))}, ${esc(photoName(p.url))}" ${i > 1 ? 'loading="lazy"' : ""}></figure>`).join("")}</div>
      <div class="gnav"><button type="button" id="gprev" aria-label="Previous photo">‹</button><span id="gcount"></span><button type="button" id="gnext" aria-label="Next photo">›</button></div>`
    : `<div class="ph">${ph(g, null)}</div>`;
  const rows = FIELDS.map(f => `<dt>${esc(f.label)}</dt><dd data-field="${f.key}">${evButton(f.key, f.label, `<span>${displayValue(g, f)}</span>`)}</dd>`).join("");
  const tags = `<div data-field="style_tags">${evButton("style_tags", "style tags",
      g.style_tags.length ? `<span class="tags">${g.style_tags.map(t => `<span class="tg">${esc(t)}</span>`).join("")}</span>` : `<span class="addnote">+ Add style tags</span>`)}</div>`;
  const notes = `<div data-field="notes">${evButton("notes", "your notes", g.notes ? `<p class="notes mine">${esc(g.notes)}</p>` : `<span class="addnote">+ Add your own notes</span>`, "block")}</div>`;
  const label = `<div data-field="label_text">${evButton("label_text", "label text", g.label_text ? `<div class="label">${esc(g.label_text)}</div>` : `<span class="addnote">+ Add label text</span>`, "block")}</div>`;
  return `<button type="button" class="back" data-back="wardrobe" style="margin-top:20px">← Wardrobe</button>
    <div class="detail">
    <div class="gallery">${gallery}</div>
    <div class="info">
      <div><span class="eyebrow">${esc(g.brand || "unknown brand")} · ${esc(g.category)} · #${g.id}</span><h2>${esc(g.subcategory)}</h2>
        <div class="hero-actions"><button type="button" class="btn${builder.pieces.includes(g.id) ? " primary" : ""}" data-pick="${g.id}" aria-pressed="${builder.pieces.includes(g.id)}">${builder.pieces.includes(g.id) ? "− Remove from outfit" : "+ Add to outfit"}</button></div></div>
      ${setPanel}
      <p class="notes">${esc(g.styling_notes)}</p>
      ${notes}
      ${outPanel}
      ${coPanel}
      <div class="panel">
        <div class="edit-head"><h3>Details</h3><small>Click any value to correct it</small></div>
        <dl class="kv">${rows}<dt>Added</dt><dd style="padding:6px 0">${esc(whenDay(g.date_added))}</dd></dl>
        ${tags}
      </div>
      ${label}
    </div></div>`;
}
