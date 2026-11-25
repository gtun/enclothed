/* TEMPLATE: a garment's details: which there are, their labels and order (FIELDS), and how each value shows.
   Both the garment page (garmentPage.js) and a share link's page (sharedPages.js) use these, so share.html loads
   this file and not garmentPage.js, whose buttons call code only the app has. */
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
