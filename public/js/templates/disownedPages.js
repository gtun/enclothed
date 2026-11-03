/* TEMPLATE: the two pages for what you no longer own: Disowned garments and Disowned outfits. */
"use strict";

const DISOWNED_EMPTY = `<div class="state"><p>Nothing here yet.</p></div>`;
const byNewestDay = (a, b) => b.disowned_on.localeCompare(a.disowned_on) || b.id - a.id;

/* The link to these pages, from the wardrobe and outfits pages. Shows only when there's something to see. */
function disownedLink(hash, label, n){
  return n ? `<a class="btn quiet" href="#${hash}" style="text-decoration:none">${esc(label)} <span class="cnt">${n}</span></a>` : "";
}
function disownedHead(heading, sub, here){
  const tab = (hash, label, n) => `<a href="#${hash}"${hash === here ? ` aria-current="page"` : ""}>${esc(label)} <span>${n}</span></a>`;
  return `<header class="hero"><div><h1>${esc(heading)}</h1><p class="sub">${esc(sub)}</p></div></header>
    <nav class="filters disowned-tabs" aria-label="Disowned">${tab("disowned-garments", "Garments", DISOWNED.length)}${tab("disowned-outfits", "Outfits", DISOWNED_O.length)}</nav>`;
}
function disownedGarments(){
  const items = [...DISOWNED].sort(byNewestDay);
  return disownedHead("Disowned garments", "Pieces you no longer own, most recent first. Open one to add it to your wardrobe again.", "disowned-garments")
    + (items.length ? `<main><div class="grid">${items.map(gCard).join("")}</div></main>` : DISOWNED_EMPTY);
}
function disownedOutfits(){
  const items = [...DISOWNED_O].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  return disownedHead("Disowned outfits", "Outfits with a piece you no longer own. Those pieces are faded.", "disowned-outfits")
    + (items.length ? `<main><div class="ogrid">${items.map(oCard).join("")}</div></main>` : DISOWNED_EMPTY);
}
