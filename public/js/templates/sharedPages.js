/* TEMPLATE: the pages a share link shows (share.html): a garment, an outfit, and the expired-link page.
   They show only what the server put in the share (shares.py), and nothing that would edit, rate or ask the AI.
   Garment rows reuse FIELDS and displayValue from garmentPage.js, so they read the same as in the app. */
"use strict";

/* The garment details a share shows, in the garment page's order. Empty ones are left out. */
const SHARED_FIELDS = ["category", "subcategory", "brand", "primary_color", "secondary_colors", "accent_colors", "fabric_type", "materials", "country_of_origin"];
const hasValue = v => Array.isArray(v) ? v.length > 0 : v !== null && v !== undefined && v !== "";

function sharedGarmentPage(g, backToOutfit){
  const rows = FIELDS.filter(f => SHARED_FIELDS.includes(f.key) && hasValue(g[f.key]))
    .map(f => `<dt>${esc(f.label)}</dt><dd class="ro" data-field="${f.key}">${displayValue(g, f)}</dd>`).join("");
  const tags = g.style_tags.length ? `<div class="tags" data-field="style_tags">${g.style_tags.map(t => `<span class="tg">${esc(t)}</span>`).join("")}</div>` : "";
  const gallery = g.photos.length ? `<div class="track" id="track" tabindex="0" aria-label="Photos">${g.photos.map((p, i) =>
      `<figure class="slide"><img src="${esc(encodeURI(p.url))}" alt="${esc(title(g))}, ${esc(photoName(p.url))}" ${i > 1 ? 'loading="lazy"' : ""}></figure>`).join("")}</div>
      <div class="gnav"><button type="button" id="gprev" aria-label="Previous photo">‹</button><span id="gcount"></span><button type="button" id="gnext" aria-label="Next photo">›</button></div>`
    : `<div class="ph">${ph(g, null)}</div>`;
  return `${backToOutfit ? `<a class="back" href="#" style="margin-top:20px">← Back to outfit</a>` : ""}
    <div class="detail"${backToOutfit ? "" : ` style="margin-top:22px"`}>
    <div class="gallery">${gallery}</div>
    <div class="info">
      <div><span class="eyebrow">${esc(g.brand || "unknown brand")} · ${esc(categoryName(g.category))}</span><h2>${esc(subcategoryName(g.subcategory))}</h2></div>
      <div class="panel">
        <div class="edit-head"><h3>Details</h3></div>
        <dl class="kv">${rows}</dl>
        ${tags}
      </div>
    </div></div>`;
}

function sharedOutfitPage(o){
  const names = palette(o).map(s => `<span><i style="background:${hex(s.c)}"></i>${esc(colorName(s.c))}</span>`).join("");
  return `<div class="ohead">
      <p class="req">${esc(whenLong(o.timestamp))}</p>
      <h1>${esc(o.aesthetic)}${tierBadge(o)}</h1>
      ${palBar(o, "big")}<div class="palnames">${names}</div>
      <p class="lede">${esc(o.explanation)}</p>
      ${o.missing ? `<div class="missing"><b>To finish the look</b>${esc(o.missing)}</div>` : ""}
    </div>
    <section class="pieces" aria-label="Pieces">${o.pieces.map(p => { const g = byId[p.id]; return `
      <a class="piece" href="#garment-${g.id}">
        <div class="ph">${ph(g, thumb(g))}${p.in_set ? `<span class="badge set" title="Part of a set">${SET_ICON}<b>${esc(p.set_name || "Set")}</b></span>` : ""}</div>
        <span class="eyebrow">${esc(categoryName(g.category))}</span>
        <span class="nm">${esc(title(g))}</span>
        ${p.advice ? `<p>${esc(p.advice)}</p>` : `<p class="empty">No specific advice for this piece.</p>`}
      </a>`; }).join("")}</section>`;
}

const sharedFooter = expiresAt => `<p class="sharefoot">Shared from enclothed · this link stops working ${esc(whenLong(expiresAt))}</p>`;

const sharedGone = () => `<div class="state"><h1>This link has expired</h1><p>Shared links work for a few days. Ask whoever sent it for a new one.</p></div>`;
