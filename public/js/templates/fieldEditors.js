/* TEMPLATE: the inline editors on the garment page and in the review dialog. features/editing.js opens them,
   handles their clicks and keys, and saves. */
"use strict";

/* Where the category was, after a new category is picked: the subcategory still has to be chosen. */
const categoryPicked = category =>
  `<div class="ontrack"><span class="cchip">${esc(categoryName(category))}</span><span class="hintline">pick a subcategory to save</span></div>`;

/* Colors or style tags: what's there now, each with a remove button, and a box (.adder) for adding more. */
function multiEditorBox(values, isColor, inReview){
  const name = v => isColor ? colorName(v) : v;
  const pills = values.map((v, i) => `<span class="pill">${isColor ? `<span class="chip" style="background:${hex(v)}"></span>` : ""}${esc(name(v))}<button type="button" data-rm="${i}" aria-label="Remove ${esc(name(v))}">×</button></span>`).join("");
  return `<div class="multi float"><div class="have">${pills || `<span class="empty">None yet</span>`}</div>
    <div class="btns"><button type="button" class="btn done-btn">Done</button><span class="hintline">${inReview ? "" : "Changes save as you go"}</span></div>
    <div class="adder"></div></div>`;
}

function textEditorBox(text, rows, spellcheck){
  return `<textarea class="txt" rows="${rows}" spellcheck="${spellcheck}">${esc(text)}</textarea>
    <div class="btns" style="margin-top:8px"><button type="button" class="btn primary" data-act="save">Save</button><button type="button" class="btn quiet" data-act="cancel">Cancel</button><span class="hintline">Ctrl+Enter to save · Esc to cancel</span></div>`;
}

const materialsSum = m => m.fibers.reduce((n, f) => n + (+f.percent || 0), 0);
const materialsSumText = sum => `total ${sum}%`;

/* parts is the materials being edited; fibers and partNames are suggestions from the rest of the wardrobe.
   Each input's data-p, data-f and data-k say which part, fiber and key it changes. */
function materialsEditorBox(parts, fibers, partNames, listId, partId){
  return `<div class="mats">
      <datalist id="${listId}">${fibers.map(f => `<option value="${esc(f)}">`).join("")}</datalist>
      <datalist id="${partId}">${partNames.map(f => `<option value="${esc(f)}">`).join("")}</datalist>
      ${parts.map((m, pi) => { const sum = materialsSum(m); return `<div class="mpart">
        <div class="top"><input class="txt" list="${partId}" data-p="${pi}" data-k="part" value="${esc(m.part || "")}" placeholder="Part (optional, e.g. shell, lining)" aria-label="Part name">
          ${parts.length > 1 ? `<button type="button" class="x" data-rmpart="${pi}" aria-label="Remove this part">×</button>` : ""}</div>
        ${m.fibers.map((f, fi) => `<div class="frow"><input class="txt" list="${listId}" data-p="${pi}" data-f="${fi}" data-k="fiber" value="${esc(f.fiber)}" placeholder="Fiber" aria-label="Fiber">
          <span class="pct"><input class="num" type="number" min="1" max="100" step="1" data-p="${pi}" data-f="${fi}" data-k="percent" value="${f.percent}" aria-label="Percent"></span>
          <button type="button" class="x" data-rmfiber="${pi}:${fi}" aria-label="Remove this fiber">×</button></div>`).join("")}
        <div class="btns"><button type="button" class="btn quiet" data-addfiber="${pi}">+ Fiber</button><span class="msum${sum === 100 ? "" : " off"}">${materialsSumText(sum)}</span></div>
      </div>`; }).join("")}
      <div class="btns"><button type="button" class="btn quiet" data-addpart>+ Part</button></div>
      <div class="btns"><button type="button" class="btn primary" data-act="save">Save materials</button><button type="button" class="btn quiet" data-act="cancel">Cancel</button><span class="hintline" id="materr"></span></div>
    </div>`;
}
const MATERIALS_ERROR = "Each fiber needs a name and a whole-number percent from 1 to 100.";
