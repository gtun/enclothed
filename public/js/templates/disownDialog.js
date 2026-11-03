/* TEMPLATE: the "I no longer own this" confirmation (question, what it affects, button labels). */
"use strict";

function disownDialog(g){
  const s = setById[g.set_id];
  const others = s ? OWNED.filter(x => x.set_id === s.id && x.id !== g.id) : [];
  const uses = O.filter(o => o.pieces.some(p => p.id === g.id));
  const willMove = uses.filter(o => !outfitHidden(o)).length;
  const lines = [];
  if (uses.length) lines.push(`Used in ${plural(uses.length, "outfit")}.${willMove ? ` ${willMove === uses.length ? (uses.length === 1 ? "It" : "They") : willMove} will move to Disowned outfits.` : ""}`);
  if (s) lines.push(`Part of the set ${esc(setName(s))}${others.length ? ` with ${others.map(x => esc(title(x))).join(", ")}` : ""}.`);
  return `<div class="dialog small" role="dialog" aria-modal="true" aria-labelledby="d-title">
    <div class="bhead"><h2 id="d-title">Remove ${esc(title(g))} from your wardrobe?</h2></div>
    <div class="bbody">
      <p class="dnote">It moves to Disowned garments and won't be suggested again. You can add it back from there.</p>
      ${lines.length ? `<ul class="tips">${lines.map(l => `<li>${l}</li>`).join("")}</ul>` : ""}
    </div>
    <div class="bfoot dbtns"><button type="button" class="btn primary" data-d-yes>Yes, remove it</button><button type="button" class="btn" data-d-no>No, keep it</button></div>
  </div>`;
}
