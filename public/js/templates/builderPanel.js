/* TEMPLATE: the outfit builder panel (headings, labels, placeholders, button text) and why its buttons are greyed out. */
"use strict";

/* Why "Generate" or "Save" is greyed out, shown under the button. */
function suggestBlockedReason(pieces){
  if (!pieces.length && !builder.details.trim()) return "Pick at least one piece or describe the occasion.";
  if (builder.session && unchangedSinceLast()) return "Change the pieces or details to get new suggestions.";
  return "";
}
function saveBlockedReason(pieces){
  if (!pieces.length) return "Add at least one piece.";
  if (!builder.form.aesthetic.trim() || !builder.form.explanation.trim()) return "Fill in the name and why it works.";
  return "";
}

function builderPanel(){
  const pieces = sortedPieces();
  const retry = !!builder.session;
  const reason = suggestBlockedReason(pieces);
  const cats = RAIL_ORDER.filter(c => OWNED.some(g => g.category === c));
  const tree = cats.map(c => { const items = OWNED.filter(g => g.category === c); return `<details data-tree="${esc(c)}"><summary><span>${esc(c)}</span><em>${items.length}</em></summary><ul>${items.map(g => {
      const on = builder.pieces.includes(g.id);
      return `<li><span class="chip" style="background:${hex(g.primary_color)}"></span><span>${esc(title(g))}</span><button type="button" class="small-add" data-pick="${g.id}" aria-pressed="${on}" aria-label="${on ? "Remove" : "Add"} ${esc(title(g))}">${on ? "−" : "+"}</button></li>`; }).join("")}</ul></details>`; }).join("");
  const pieceRows = pieces.length ? pieces.map(g => `<div class="bpiece">
      <div class="ph">${ph(g, thumb(g))}<button type="button" class="rm" data-pick="${g.id}" aria-label="Remove ${esc(title(g))} from outfit">×</button></div>
      <div><span class="eyebrow">${esc(g.category)}</span><br><a class="nm" href="#garment-${g.id}">${esc(title(g))}</a>
        ${builder.manual ? `<input class="txt" data-advice="${g.id}" value="${esc(builder.form.advice[g.id] || "")}" placeholder="How to wear it (optional)" aria-label="How to wear ${esc(title(g))}">` : ""}</div>
    </div>`).join("") : `<p class="bhint">No pieces yet. Use the + on any garment, the list below, or type a name.</p>`;

  const manualForm = `<div class="bsec">
      <div class="field"><label for="b-aes">Name <span class="req-star" aria-hidden="true">*</span></label><input id="b-aes" class="txt" data-form="aesthetic" value="${esc(builder.form.aesthetic)}" placeholder="e.g. Sunday errands" required></div>
      <div class="field"><label for="b-exp">Why it works <span class="req-star" aria-hidden="true">*</span></label><textarea id="b-exp" class="txt" rows="3" data-form="explanation" placeholder="A sentence or two for future you" required>${esc(builder.form.explanation)}</textarea></div>
      <div class="field"><label for="b-mis">Still missing <em>(optional)</em></label><input id="b-mis" class="txt" data-form="missing" value="${esc(builder.form.missing)}" placeholder="e.g. a darker belt"></div>
    </div>`;
  const busy = builderBusy ? `<div class="busy" role="status"><span class="spin" aria-hidden="true"></span>${builder.manual ? "Saving…" : "Asking for outfit suggestions… this can take up to a minute."}</div>` : "";
  const manualReason = saveBlockedReason(pieces);
  const foot = builder.manual
    ? `${busy}<button type="button" class="btn primary wide" data-save-own ${manualReason || builderBusy ? "disabled" : ""}>Save outfit</button>
       <p class="bhint" id="b-reason">${esc(manualReason)}</p>
       <button type="button" class="btn quiet wide" data-manual="off" ${builderBusy ? "disabled" : ""}>Back to suggestions</button>`
    : `${busy}<button type="button" class="btn llm-action wide" data-suggest title="Uses AI (spends tokens)" ${reason || builderBusy ? "disabled" : ""}>${retry ? "Suggest again" : "Generate outfit suggestions"}</button>
       <p class="bhint" id="b-reason">${esc(reason)}</p>
       <button type="button" class="btn quiet wide" data-manual="on" ${builderBusy ? "disabled" : ""}>Save as my own outfit instead</button>`;

  return `<div class="bhead"><h2>${retry ? "Refine outfit" : "New outfit"}</h2><small>${plural(pieces.length, "piece")}</small>
      <button type="button" class="iconbtn" data-builder-min aria-label="${builder.min ? "Expand" : "Minimize"} outfit builder" aria-expanded="${!builder.min}">${builder.min ? "▴" : "▾"}</button>
      <button type="button" class="iconbtn" data-builder-close aria-label="Close outfit builder">×</button></div>
    <div class="bbody">
      <div class="bsec"><h3>${builder.manual ? "Pieces" : "Pieces to build around"}</h3><div class="bpieces">${pieceRows}</div></div>
      <div class="bsec"><h3>Add pieces</h3><div id="b-search"></div><div class="tree">${tree}</div></div>
      <div class="bsec"><div class="field"><label for="b-details">${builder.manual ? "Occasion" : "Occasion and details"} <em>(optional${pieces.length || builder.manual ? "" : " if you pick pieces"})</em></label>
        ${builder.manual ? "" : `<p class="style-hint">${prefs.text ? `Your <a href="#style">style notes</a> are included.` : `Tip: describe your <a href="#style">style</a> once and it's included every time.`}</p>`}
        <textarea id="b-details" class="txt" rows="3" data-details placeholder="${builder.manual ? "e.g. rainy Sunday" : "e.g. dinner downtown, about 10°C, want to wear the new boots"}">${esc(builder.details)}</textarea></div></div>
      ${builder.manual ? manualForm : ""}
    </div>
    <div class="bfoot">${foot}</div>`;
}
