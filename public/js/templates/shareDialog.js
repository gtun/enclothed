/* TEMPLATE: the share-link dialog on a garment or outfit page (what's shared, the link, its buttons). */
"use strict";

/* What the link's page will show, so nobody shares more than they expect. Kept in step with shares.py. */
const SHARE_WHAT = {
  garment: "its photos, category, brand, colors, fabric, materials, where it was made and style tags",
  outfit: "the outfit's name, why it works and its pieces, each with its photos and the same details as a shared garment",
};

function shareDialog(kind, link){
  const thing = kind === "garment" ? "garment" : "outfit";
  const body = !link ? `<p class="dnote">Making a link…</p>`
    : `<p class="dnote">Anyone with this link can see ${SHARE_WHAT[kind]}, until ${esc(whenLong(link.expires_at))}.</p>
       <p class="dnote">It's a copy of this ${thing} as it is now, so later changes won't show. ${kind === "garment" ? "Your name and notes aren't in it." : "Your name, request, rating and wears aren't in it."}</p>
       <div class="sharelink"><input class="txt" id="share-url" type="text" readonly value="${esc(link.url)}" aria-label="Share link"></div>`;
  return `<div class="dialog small" role="dialog" aria-modal="true" aria-labelledby="share-title">
    <div class="bhead"><h2 id="share-title">Share this ${thing}</h2></div>
    <div class="bbody">${body}</div>
    <div class="bfoot dbtns">${link ? `<button type="button" class="btn primary" data-share-copy>Copy link</button>${navigator.share ? `<button type="button" class="btn" data-share-send>Send…</button>` : ""}` : ""}<button type="button" class="btn" data-share-close>Close</button></div>
  </div>`;
}
