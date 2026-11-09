/* TEMPLATE: the outfits page (heading, stats, filters, outfits grouped by request). */
"use strict";

let req = "all";
/* Who made the outfits shown ("all", "ai" or "own"), and whether to show only outfits you've worn. */
let osrc = "all", wornOnly = false;
const OUTFIT_SOURCES = [["all", "All"], ["ai", "Suggested by AI"], ["own", "Put together myself"]];
function outfits(){
  if (!SHOWN.length) return `<header class="hero"><div><h1>Outfits</h1><div class="hero-actions"><button type="button" class="btn primary" data-new-outfit>+ New outfit</button>${disownedLink("disowned-outfits", "Disowned", DISOWNED_O.length)}</div></div></header><div class="state"><p>No outfits yet. Start one with “New outfit”.</p></div>`;
  const kept = o => visible(o) && passesFilters(o) && (!wornOnly || o.wear_count > 0);   // everything but the source
  const groups = [...REQUESTS].reverse().map(r => ({...r, shown: r.items.filter(o => kept(o) && (osrc === "all" || o.source === osrc))})).filter(r => r.shown.length);
  const nDisliked = SHOWN.filter(o => o.liked === false).length;
  if (req !== "all" && !groups.some(r => r.key === req)) req = "all";
  const shownTotal = groups.reduce((n, r) => n + r.shown.length, 0);
  const btn = (k, label, n, full) => `<button type="button" data-req="${k}" aria-pressed="${req===k}" title="${esc(full||label)}">${esc(label)} <span>${n}</span></button>`;
  const toggle = nDisliked ? `<span class="sep" aria-hidden="true"></span><button type="button" data-toggle-disliked aria-pressed="${showDisliked}">${showDisliked ? "Showing" : "Show"} disliked <span>${nDisliked}</span></button>` : "";
  const nWorn = SHOWN.filter(o => o.wear_count > 0 && visible(o)).length;
  const sources = OUTFIT_SOURCES.map(([k, label]) => `<button type="button" data-osrc="${k}" aria-pressed="${osrc === k}">${esc(label)} <span>${SHOWN.filter(o => kept(o) && (k === "all" || o.source === k)).length}</span></button>`).join("");
  const sourceRow = `<div class="filters osrc" role="toolbar" aria-label="Who made it"><div class="seg">${sources}</div>
    ${nWorn || wornOnly ? `<button type="button" data-toggle-worn aria-pressed="${wornOnly}" title="Only outfits you've logged as worn">Worn <span>${nWorn}</span></button>` : ""}</div>`;
  const shown = groups.filter(r => req === "all" || r.key === req);
  return `<header class="hero"><div><h1>Outfits</h1><p class="sub">Every outfit suggested so far, grouped by what you asked for. The stripe is each piece's main color, outer layer down to shoes.</p>
      <div class="hero-actions"><button type="button" class="btn primary" data-new-outfit>+ New outfit</button>${builder.session ? `<a class="btn" href="#results" style="text-decoration:none">Latest suggestions</a>` : ""}${disownedLink("disowned-outfits", "Disowned", DISOWNED_O.length)}</div></div>
    <div class="stats"><div><b>${SHOWN.length}</b>outfits</div><div><b>${REQUESTS.length}</b>requests</div><div><b>${SHOWN.filter(o => o.liked).length}</b>liked</div><div><b>${SHOWN.filter(o => o.wear_count > 0).length}</b>worn</div></div></header>
    ${filterPanel()}
    ${sourceRow}
    <div class="filters" role="toolbar" aria-label="Filter by request">${btn("all","All requests",shownTotal)}${groups.map(r => btn(r.key, r.text, r.shown.length, r.text)).join("")}${toggle}</div>
    <main style="display:flex;flex-direction:column;gap:34px">${shown.length ? shown.map(r => `<section class="rail"><h2 class="req"><q>${esc(r.text)}</q> <span>${plural(r.shown.length,"option")}</span></h2>
      <div class="ogrid">${r.shown.map(oCard).join("")}</div></section>`).join("") : `<p class="empty">${filtersActive() || osrc !== "all" || wornOnly ? "No outfits match these filters." : "Every outfit here is disliked. Use “Show disliked” to see them."}</p>`}</main>`;
}
