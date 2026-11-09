/* TEMPLATE: weigh ("should I buy this?"): one garment's verdict page (#weigh-N) and the list of everything being weighed (#weighed). */
"use strict";

let weighConfirm = false;   // true while "Pass" waits for its second click
const recommendationLabel = r => choiceLabel(OPT.recommendations || [], r);
const verdictBadge = r => `<span class="verdict verdict-${esc(r)}">${esc(recommendationLabel(r))}</span>`;
/* The four checks, in the order the AI answered them. For already_own, "yes" is the bad answer. */
const WEIGH_CHECKS = [["already_own", "Already own something like it?"], ["makes_outfits", "Makes good outfits?"],
  ["fills_gap", "Fills a gap?"], ["fits_style", "Fits your style?"]];
const SIMILARITY = {same: "Same job", close: "Close", different: "Different"};

function weighLink(){
  return CANDIDATES.length ? `<a class="btn quiet" href="#weighed" style="text-decoration:none">Weighing <span>${CANDIDATES.length}</span></a>` : "";
}
function weighCheck(key, label, check){
  const good = key === "already_own" ? !check.answer : check.answer;
  return `<li class="wcheck ${good ? "good" : "bad"}"><span class="wmark" aria-hidden="true">${good ? "✓" : "✕"}</span>
    <div><b>${esc(label)}</b> <span class="wans">${check.answer ? "Yes" : "No"}</span><p>${esc(check.reason)}</p></div></li>`;
}
function weighPage(g){
  const w = weighById[g.id];
  const outfits = (weighOutfitsOf[g.id] || []).slice().sort((a, b) => a.id - b.id);
  const photos = g.photos.length
    ? `<div class="wphotos">${g.photos.map((p, i) => `<img src="${esc(encodeURI(i ? p.thumb_url : p.url))}" alt="${esc(title(g))}, ${esc(photoName(p.url))}" ${i ? 'loading="lazy"' : ""}>`).join("")}</div>`
    : `<div class="ph">${ph(g, null)}</div>`;
  const similar = w ? w.verdict.similar.map(m => byId[m.garment_id] && `<a class="mini" href="#garment-${m.garment_id}"><div class="ph">${ph(byId[m.garment_id], thumb(byId[m.garment_id]))}</div>
      <span>${esc(subcategoryName(byId[m.garment_id].subcategory))}</span><em class="sim-${esc(m.similarity)}">${esc(SIMILARITY[m.similarity])}</em><em>${esc(m.differences)}</em></a>`).filter(Boolean).join("") : "";
  const busy = weighBusy ? "disabled" : "";
  const actions = weighConfirm
    ? `<p class="dnote">Delete this garment, its photos and the outfits built around it?</p>
       <div class="hero-actions"><button type="button" class="btn primary" data-weigh-pass-yes ${busy}>Yes, delete it</button><button type="button" class="btn" data-weigh-pass-no ${busy}>Keep it</button></div>`
    : `<div class="hero-actions"><button type="button" class="btn primary" data-weigh-buy ${busy}>Get</button><button type="button" class="btn" data-weigh-pass ${busy}>Pass</button>
       <a class="btn quiet" href="#garment-${g.id}" style="text-decoration:none">All details</a></div>`;
  return `<button type="button" class="back" data-back="weighed" style="margin-top:20px">← Weighing</button>
    <div class="detail wdetail">
    <div class="gallery">${photos}</div>
    <div class="info">
      <div><span class="eyebrow">Weighing · ${esc(g.brand || "unknown brand")} · ${esc(categoryName(g.category))}${SHOW_IDS ? ` · #${g.id}` : ""}</span>
        <h2>${esc(subcategoryName(g.subcategory))}</h2>
        ${w ? `<div class="wverdict">${verdictBadge(w.verdict.recommendation)}<p>${esc(w.verdict.summary)}</p></div>` : `<p class="gonenote">No verdict was saved for this garment.</p>`}
        ${actions}</div>
      ${w ? `<div class="panel"><h4>The checks <small>Weighed ${esc(when(w.weighed_at))}</small></h4><ul class="wchecks">${WEIGH_CHECKS.map(([k, label]) => weighCheck(k, label, w.verdict[k])).join("")}</ul></div>` : ""}
      ${similar ? `<div class="panel"><h4>Closest in your wardrobe</h4><div class="inset">${similar}</div></div>` : ""}
    </div></div>
    ${outfits.length ? `<section class="rail" style="margin-top:28px"><h2>Outfits with it <span>${outfits.length}</span></h2><div class="ogrid">${outfits.map(oCard).join("")}</div></section>` : ""}`;
}
function weighedPage(){
  const list = WEIGHS.map(w => byId[w.garment_id]).filter(isCandidate);
  const head = `<header class="hero"><div><h1>Weighing</h1><p class="sub">Garments you photographed while shopping, judged against your wardrobe. They aren't part of it unless you choose <b>Get</b>.</p>
    <div class="hero-actions"><button type="button" class="btn llm-action" data-weigh-garment title="Uses AI (spends tokens)">Weigh a garment</button></div></div></header>`;
  if (!list.length) return head + `<div class="state"><p>Nothing being weighed. Photograph something you're thinking of getting with “Weigh a garment”.</p></div>`;
  return head + `<main class="wlist">${list.map(g => { const w = weighById[g.id];
    return `<a class="wrow" href="#weigh-${g.id}"><div class="ph">${ph(g, thumb(g))}</div>
      <div><span class="eyebrow">${esc(g.brand || "unknown brand")} · ${esc(when(w.weighed_at))}</span><h3>${esc(subcategoryName(g.subcategory))} ${verdictBadge(w.verdict.recommendation)}</h3>
      <p class="clamp">${esc(w.verdict.summary)}</p></div></a>`; }).join("")}</main>`;
}
