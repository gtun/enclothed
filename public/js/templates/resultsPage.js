/* TEMPLATE: the "New suggestions" page shown after generating outfits. */
"use strict";

function resultsPage(){
  const s = builder.session;
  if (!s || !s.ids.length) return `<div class="state"><h1>No new suggestions</h1><p>Start one from <a href="#outfits">Outfits</a> with “New outfit”.</p></div>`;
  const list = s.ids.map(id => outById[id]).filter(Boolean).reverse();
  const requests = [...new Set(list.map(o => o.prompt_message))];
  const anchors = s.last.pieces.map(id => byId[id]).filter(Boolean);
  return `<header class="hero"><div><h1>New suggestions</h1>
      <p class="sub">${plural(list.length, "outfit")} for ${requests.map(r => `<q>${esc(r)}</q>`).join(", ")}${anchors.length ? `, built around ${anchors.map(g => esc(title(g))).join(", ")}` : ""}. Newest first; open one to like or dislike it.</p>
      <div class="hero-actions results-actions"><button type="button" class="btn primary" data-results-retry>Change pieces or details and try again</button><button type="button" class="btn" data-results-done>Done</button></div></div></header>
    <main><div class="ogrid">${list.map(oCard).join("")}</div></main>`;
}
