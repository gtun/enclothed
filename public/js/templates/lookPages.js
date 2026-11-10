/* TEMPLATE: mimic (recreate a photographed look): one look's page (#look-N), with each piece of the look
   beside the garment of yours standing in for it, and the list of looks (#looks). */
"use strict";

let lookConfirm = false;   // true while "Delete look" waits for its second click
const closenessLabel = c => choiceLabel(OPT.closeness || [], c);
const closenessBadge = c => `<span class="closeness closeness-${esc(c)}">${esc(closenessLabel(c))}</span>`;
const RECREATION_NAMES = ["Closest recreation", "Another way"];

function looksLink(){
  return LOOKS.length ? `<a class="btn quiet" href="#looks" style="text-decoration:none">Looks <span>${LOOKS.length}</span></a>` : "";
}
const pieceName = p => `${colorName(p.primary_color)} ${subcategoryName(p.subcategory)}`;
function lookPiece(p){
  return `<div class="lpiece"><span class="lsw" style="background:${hex(p.primary_color)}" aria-hidden="true"></span>
    <div><b>${esc(pieceName(p))}</b>${p.essential ? "" : ` <small>optional</small>`}<em>${esc(p.role)}</em></div></div>`;
}
/* One recreation: every piece of the look, the garment standing in for it, and how close it is. */
function recreationPanel(l, r, i){
  const o = outById[r.outfit_id];
  if (!o) return "";
  const standIns = new Set(r.matches.map(m => m.garment_id).filter(Boolean));
  const added = o.pieces.map(p => byId[p.id]).filter(g => g && !standIns.has(g.id));
  const rows = r.matches.map(m => {
    const p = l.pieces[m.piece - 1], g = m.garment_id ? byId[m.garment_id] : null;
    if (!p) return "";
    const stand = g
      ? `<a class="lstand" href="#garment-${g.id}"><span class="ph${fadeClass(g)}">${ph(g, thumb(g))}</span><span>${esc(title(g))}${goneMark(g)}</span></a>`
      : `<span class="lnone">Nothing of yours does this</span>`;
    return `<li class="lmatch">${lookPiece(p)}<span class="larrow" aria-hidden="true">→</span>
      <div class="lright">${stand}<div class="lhow">${closenessBadge(m.closeness)}${m.note ? `<span>${esc(m.note)}</span>` : ""}</div></div></li>`;
  }).join("");
  return `<div class="panel"><h4>${esc(RECREATION_NAMES[i] || `Recreation ${i + 1}`)} <a class="btn quiet" href="#outfit-${o.id}" style="text-decoration:none">Open outfit</a></h4>
    <ul class="lmatches">${rows}</ul>
    ${added.length ? `<p class="ladded">Added for what the photos don't show: ${added.map(g => `<a class="gref" href="#garment-${g.id}" data-gref="${g.id}">${esc(title(g))}</a>`).join(", ")}</p>` : ""}</div>`;
}
function lookPage(l){
  const outfits = l.recreations.map(r => outById[r.outfit_id]).filter(Boolean);
  const busy = mimicBusy === l.id;
  const photos = l.photos.length
    ? `<div class="wphotos">${l.photos.map((p, i) => `<img src="${esc(encodeURI(i ? p.thumb_url : p.url))}" alt="${esc(l.title)}, photo ${i + 1}" ${i ? 'loading="lazy"' : ""}>`).join("")}</div>`
    : `<div class="ph"></div>`;
  const actions = lookConfirm
    ? `<p class="dnote">Delete this look and its photos? Its outfits stay under Outfits.</p>
       <div class="hero-actions"><button type="button" class="btn primary" data-look-delete-yes ${busy ? "disabled" : ""}>Yes, delete it</button><button type="button" class="btn" data-look-delete-no>Keep it</button></div>`
    : `<div class="hero-actions">${!l.recreations.length && !busy ? `<button type="button" class="btn llm-action" data-look-match title="Uses AI (spends tokens)">Match it to my wardrobe</button>` : ""}
       <button type="button" class="btn" data-look-delete ${busy ? "disabled" : ""}>Delete look</button></div>`;
  let body;
  if (busy) body = `<div class="panel"><div class="busy" role="status"><span class="spin" aria-hidden="true"></span>Matching it to your wardrobe… this can take up to a minute.</div></div>`;
  else if (l.recreations.length) body = l.recreations.map((r, i) => recreationPanel(l, r, i)).join("");
  else body = `<div class="panel"><h4>What's in the look</h4><ul class="lmatches">${l.pieces.map(p => `<li class="lmatch solo">${lookPiece(p)}</li>`).join("")}</ul>
    <p class="gonenote">${mimicTried.has(l.id) ? "Nothing in your wardrobe could recreate this look." : "Not matched to your wardrobe yet."}</p></div>`;
  return `<button type="button" class="back" data-back="looks" style="margin-top:20px">← Looks</button>
    <div class="detail wdetail ldetail">
    <div class="gallery">${photos}</div>
    <div class="info">
      <div><span class="eyebrow">Look · ${esc(when(l.created_at))}${l.silhouette ? ` · ${esc(l.silhouette)}-line` : ""}${SHOW_IDS ? ` · #${l.id}` : ""}</span>
        <h2>${esc(l.title)}</h2>
        <p class="lsummary">${esc(l.summary)}</p>
        ${l.note ? `<p class="dnote">Your note: <q>${esc(l.note)}</q></p>` : ""}
        ${actions}</div>
      ${body}
    </div></div>
    ${outfits.length ? `<section class="rail" style="margin-top:28px"><h2>Recreations <span>${outfits.length}</span></h2><div class="ogrid">${outfits.map(oCard).join("")}</div></section>` : ""}`;
}
function looksPage(){
  const head = `<header class="hero"><div><h1>Looks</h1><p class="sub">Outfits you photographed to recreate: a lookbook shot, a store mannequin, someone's style you liked. Each one is matched, piece by piece, to what you own.</p>
    <div class="hero-actions"><button type="button" class="btn llm-action" data-mimic-look title="Uses AI (spends tokens)">Mimic a look</button></div></div></header>`;
  if (!LOOKS.length) return head + `<div class="state"><p>No looks yet. Photograph one you like with “Mimic a look”.</p></div>`;
  return head + `<main class="wlist">${LOOKS.map(l => {
    const first = l.photos[0], n = l.recreations.length;
    return `<a class="wrow" href="#look-${l.id}"><div class="ph">${first ? `<img src="${esc(encodeURI(first.thumb_url))}" alt="" loading="lazy" decoding="async">` : ""}</div>
      <div><span class="eyebrow">${esc(when(l.created_at))} · ${plural(l.pieces.length, "piece")}</span><h3>${esc(l.title)} <span class="closeness">${n ? plural(n, "recreation") : "not matched"}</span></h3>
      <p class="clamp">${esc(l.summary)}</p></div></a>`; }).join("")}</main>`;
}
