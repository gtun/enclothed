/* TEMPLATE: one outfit card (outfits page and new-suggestions page), with its worn and like/dislike buttons. */
"use strict";

/* The round button left of Like: a hanger until the outfit is worn, then the number of wears. Either way it opens
   the "wore it" date picker (features/wears.js). Its tooltip says what the number is and when it was last worn. */
function wearTip(o){
  return o.wear_count ? `Worn ${plural(o.wear_count, "time")}, last on ${when(o.last_worn)}. Click to log another wear.` : "Mark as worn";
}
function wearButton(o){
  const tip = wearTip(o);
  return `<button type="button" class="ratebtn wearbtn${o.wear_count ? " worn" : ""}" data-wear="${o.id}" aria-label="${esc(tip)}" title="${esc(tip)}">${o.wear_count ? `<b>${o.wear_count}</b>` : WEAR_ICON}</button>`;
}

function rateButtons(o){
  const b = (v, icon, verb) => `<button type="button" class="ratebtn" data-rate="${v}" data-rate-id="${o.id}" aria-pressed="${o.liked === v}" aria-label="${verb} ${esc(o.aesthetic)}" title="${o.liked === v ? "Clear rating" : verb}">${icon}</button>`;
  return `<div class="ocard-rate" role="group" aria-label="Wear and rate this outfit">${wearButton(o)}${b(true, THUMB_UP, "Like")}${b(false, THUMB_DOWN, "Dislike")}</div>`;
}
function oCard(o){
  const pcs = o.pieces.map(p => byId[p.id]).filter(g => g && showDisowned(g, "outfitCard"));
  const f = outfitFormality(o), w = outfitWarmth(o);
  return `<div class="ocardwrap${o.liked === false ? " disliked" : ""}"><a class="ocard" href="#outfit-${o.id}">
    <div class="flat" aria-hidden="true">${pcs.map(g => `<span class="${fadeClass(g).trim()}">${ph(g, thumb(g))}${goneMark(g)}</span>`).join("")}</div>
    ${palBar(o)}
    <div class="obody"><h3>${esc(o.aesthetic)}${tierBadge(o)}</h3><p class="clamp">${esc(o.explanation)}</p>
      <div class="ofoot"><span>${when(o.timestamp)}</span><span>${plural(pcs.length,"piece")}</span>
        <span title="Formality: ${f ? esc(levelLabel(OPT.formality, f)) : "unknown"} (least formal piece)">F${pips(f || 0, 4)}</span>
        <span title="Warmth: ${w ? esc(levelLabel(OPT.warmth, w)) : "unknown"} (warmest top layer)">W${pips(w || 0, 5)}</span>
        ${o.missing ? "<span>needs extras</span>" : ""}</div></div></a>${rateButtons(o)}</div>`;
}
