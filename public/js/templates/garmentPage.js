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
  {key:"statement", label:"Statement", kind:"choice", list:() => OPT.statements},
  {key:"fit", label:"Fit", kind:"choice", list:() => OPT.fits},
  {key:"shape", label:"Shape", kind:"choice", list:() => OPT.shapes},
  {key:"hem", label:"Hem", kind:"choice", list:() => OPT.hems},
  {key:"sleeve", label:"Sleeve", kind:"choice", list:() => OPT.sleeves},
  {key:"fabric_type", label:"Fabric", kind:"choice", list:() => OPT.fabric_types},
  {key:"fabric_weight", label:"Fabric weight", kind:"choice", list:() => OPT.fabric_weights},
  {key:"sheen", label:"Sheen", kind:"choice", list:() => OPT.sheens},
  {key:"pattern", label:"Pattern", kind:"text", suggest:() => unique(G.map(g => g.pattern))},
  {key:"materials", label:"Materials", kind:"materials"},
  {key:"country_of_origin", label:"Made in", kind:"text", suggest:() => unique(G.map(g => g.country_of_origin))},
];
const colorChip = c => `<span class="cchip"><span class="chip" style="background:${hex(c)}"></span>${esc(colorName(c))}</span>`;
function displayValue(g, f){
  const v = g[f.key];
  const none = `<span class="none">—</span>`;
  switch (f.kind){
    case "category": return esc(categoryName(v));
    case "subcategory": return esc(subcategoryName(v));
    case "color": return colorChip(v);
    case "colors": return v.length ? v.map(colorChip).join("") : none;
    case "level": return v ? `${v} · ${esc(levelLabel(f.list(), v))}` : none;
    case "choice": return v ? esc(choiceLabel(f.list(), v)) : none;
    case "materials": return v.length ? v.map(m => `<span style="display:block">${m.part ? `<span class="none">${esc(m.part)}:</span> ` : ""}${m.fibers.map(x => `${esc(x.fiber)} ${x.percent}%`).join(", ")}</span>`).join("") : none;
    default: return v ? esc(v) : none;
  }
}
const evButton = (field, label, inner, cls="") => `<button type="button" class="ev ${cls}" data-edit="${field}" aria-label="Edit ${esc(label)}">${inner}${PEN}</button>`;
/* For text that can hold links, which can't sit inside a button: click the text to edit, or Tab to the pen. */
const evText = (field, label, inner) => `<div class="ev block" data-edit="${field}">${inner}<button type="button" class="penbtn" data-edit="${field}" aria-label="Edit ${esc(label)}">${PEN}</button></div>`;

/* The prompt after a color edit, when the styling notes still mention the old color. */
function notesCheckDock(g){
  const c = currentCheck(g); if (!c) return "";
  const n = colorMentions(g.styling_notes, c.from).length;
  const message = c.to
    ? `The styling notes mention <b>${esc(c.from)}</b>${n > 1 ? ` ${n} times` : ""}, and you changed that color to <b>${esc(c.to)}</b>. Update the notes?`
    : `You removed <b>${esc(c.from)}</b>, but the styling notes still mention it. Add a replacement color to swap it in, or:`;
  return `<aside class="notecheck" role="group" aria-label="Check the styling notes">
    <p class="ncmsg">${message}</p>
    <p class="nctext">${highlightMentions(g.styling_notes, c.from)}</p>
    <div class="btns">${c.to ? `<button type="button" class="btn primary" data-nc="yes">Yes, change to ${esc(c.to)}</button><button type="button" class="btn" data-nc="no">No, leave it</button>` : `<button type="button" class="btn" data-nc="no">Leave it</button>`}<button type="button" class="btn" data-nc="manual">Do it manually</button></div>
  </aside>`;
}

/* Hides what doesn't fit the category, like a sleeve on shoes. A value still shows, so it can be seen and cleared. */
function fieldApplies(g, key){
  const categories = OPT.field_categories[key];
  return !categories || categories.includes(g.category) || g[key] !== null;
}
/* The blocks of editable details. The review dialog shows these too. */
const fieldRow = (g, f) => `<dt>${esc(f.label)}</dt><dd data-field="${f.key}">${evButton(f.key, f.label, `<span>${displayValue(g, f)}</span>`)}</dd>`;
const tagsBlock = g => `<div data-field="style_tags">${evButton("style_tags", "style tags",
  g.style_tags.length ? `<span class="tags">${g.style_tags.map(t => `<span class="tg">${esc(t)}</span>`).join("")}</span>` : `<span class="addnote">+ Add style tags</span>`)}</div>`;
const notesBlock = g => `<div data-field="notes">${g.notes ? evText("notes", "your notes", `<p class="notes mine">${linkify(g.notes)}</p>`) : evButton("notes", "your notes", `<span class="addnote">+ Add your own notes</span>`, "block")}</div>`;
const stylingNotesBlock = g => `<div data-field="styling_notes">${g.styling_notes ? evText("styling_notes", "styling notes", `<p class="notes">${linkify(g.styling_notes)}</p>`) : evButton("styling_notes", "styling notes", `<span class="addnote">+ Add styling notes</span>`, "block")}</div>`;
const labelBlock = g => `<div data-field="label_text">${evButton("label_text", "label text", g.label_text ? `<div class="label">${esc(g.label_text)}</div>` : `<span class="addnote">+ Add label text</span>`, "block")}</div>`;
const mendButton = g => g.blank_fields.length ? `<button type="button" class="btn llm-action" data-mend title="Fills blank details only. Uses AI (spends tokens)" ${mendingId === g.id ? "disabled" : ""}>${mendingId === g.id ? "Mending…" : "Mend blank details"}</button>` : "";

function garmentPage(g){
  const s = setById[g.set_id];
  let setPanel = "";
  if (s){
    const others = G.filter(x => x.set_id === s.id && x.id !== g.id && showDisowned(x, "sets"));
    const ids = G.filter(x => x.set_id === s.id).map(x => x.id);
    const together = (isDisowned(g) ? O : SHOWN).filter(o => ids.every(id => o.pieces.some(p => p.id === id))).length;
    setPanel = `<div class="panel"><h4><span style="display:inline-flex;gap:7px;align-items:center">${SET_ICON} Part of a set: ${esc(setName(s))}</span><small>worn together in ${plural(together,"outfit")}</small></h4>
      <div class="inset">${others.map(x => `<a class="mini" href="#garment-${x.id}"><div class="ph${fadeClass(x)}">${ph(x, thumb(x))}${goneMark(x)}</div><span>${esc(subcategoryName(x.subcategory))}</span>${SHOW_IDS ? `<em>#${x.id}</em>` : ""}</a>`).join("")}</div></div>`;
  }
  const allUses = ((isDisowned(g) ? allOutfitsOf : outfitsOf)[g.id] || []).slice().sort((a, b) => b.o.timestamp.localeCompare(a.o.timestamp));
  const uses = allUses.filter(u => visible(u.o));
  const hidden = allUses.length - uses.length;
  const outPanel = `<div class="panel"><h4>In outfits <small>${uses.length ? plural(uses.length,"outfit") : ""}${hidden ? ` · ${hidden} disliked hidden` : ""}</small></h4>
    ${uses.length ? `<div class="olist" tabindex="0" aria-label="Outfits with this garment">${uses.map(u => `
      <a class="orow" href="#outfit-${u.o.id}">${vPal(u.o)}<span><b>${esc(u.o.aesthetic)}</b><span>${u.advice ? esc(u.advice) : esc(u.o.prompt_message)}</span></span><time>${when(u.o.timestamp)}</time></a>`).join("")}</div>`
      : `<p class="empty">${hidden ? "Only in disliked outfits." : allOutfitsOf[g.id] ? `Only in <a href="#disowned-outfits">disowned outfits</a>.` : "Not in any outfit yet."}</p>`}</div>`;
  const co = {};
  uses.forEach(u => u.o.pieces.forEach(p => { if (p.id !== g.id && byId[p.id] && showDisowned(byId[p.id], "pairedWith") && !(g.set_id && byId[p.id].set_id === g.set_id)) co[p.id] = (co[p.id]||0) + 1; }));
  const top = Object.entries(co).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const coPanel = top.length >= 2 ? `<div class="panel"><h4>Often paired with</h4><div class="inset">${top.map(([id, n]) => { const x = byId[id]; return `<a class="mini" href="#garment-${x.id}"><div class="ph${fadeClass(x)}">${ph(x, thumb(x))}${goneMark(x)}</div><span>${esc(subcategoryName(x.subcategory))}</span><em>together ${n}×</em></a>`; }).join("")}</div></div>` : "";
  const gallery = g.photos.length ? `<div class="track" id="track" tabindex="0" aria-label="Photos">${g.photos.map((p, i) =>
      `<figure class="slide"><img src="${esc(encodeURI(p.url))}" alt="${esc(title(g))}, ${esc(photoName(p.url))}" ${i > 1 ? 'loading="lazy"' : ""}></figure>`).join("")}</div>
      <div class="gnav"><button type="button" id="gprev" aria-label="Previous photo">‹</button><span id="gcount"></span><button type="button" id="gnext" aria-label="Next photo">›</button></div>`
    : `<div class="ph">${ph(g, null)}</div>`;
  const rows = FIELDS.filter(f => fieldApplies(g, f.key)).map(f => fieldRow(g, f)).join("");
  const tags = tagsBlock(g), notes = notesBlock(g), stylingNotes = stylingNotesBlock(g), label = labelBlock(g);
  return `<button type="button" class="back" data-back="wardrobe" style="margin-top:20px">← Wardrobe</button>
    <div class="detail">
    <div class="gallery">${gallery}</div>
    <div class="info">
      <div><span class="eyebrow">${esc(g.brand || "unknown brand")} · ${esc(categoryName(g.category))}${SHOW_IDS ? ` · #${g.id}` : ""}</span><h2>${esc(subcategoryName(g.subcategory))}</h2>
        ${isCandidate(g) ? `<p class="gonenote">Not in your wardrobe · you're weighing whether to buy it</p><div class="hero-actions"><a class="btn primary" href="#weigh-${g.id}" style="text-decoration:none">See the verdict</a></div>`
          : isDisowned(g) ? `<p class="gonenote">No longer owned · since ${esc(whenDay(g.disowned_on))}</p><div class="hero-actions"><button type="button" class="btn primary" data-reown>Add this to my wardrobe again</button></div>`
          : `<div class="hero-actions"><button type="button" class="btn${builder.pieces.includes(g.id) ? " primary" : ""}" data-pick="${g.id}" aria-pressed="${builder.pieces.includes(g.id)}">${builder.pieces.includes(g.id) ? "− Remove from outfit" : "+ Add to outfit"}</button>${mendButton(g)}<button type="button" class="btn quiet" data-disown>I no longer own this</button></div>`}</div>
      ${setPanel}
      ${stylingNotes}
      ${notes}
      ${outPanel}
      ${coPanel}
      <div class="panel">
        <div class="edit-head"><h3>Details</h3><small>Click any value to correct it</small></div>
        <dl class="kv">${rows}<dt>Added</dt><dd style="padding:6px 0">${esc(whenDay(g.date_added))}</dd></dl>
        ${tags}
      </div>
      ${label}
    </div></div>
    ${notesCheckDock(g)}`;
}
