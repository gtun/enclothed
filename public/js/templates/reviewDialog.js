/* TEMPLATE: the review dialog, shown after tagging a new garment or mending one. The rows use the
   garment page's blocks (garmentPage.js), so clicking a value opens the same editor. */
"use strict";

function reviewDialog(){
  const {g, mode, fields, photos, busy, confirming, error} = review;
  const isNew = mode === "new";
  const shows = key => isNew || fields.includes(key);
  const rows = FIELDS.filter(f => shows(f.key)).map(f => fieldRow(g, f)).join("");
  const blocks = [shows("styling_notes") && stylingNotesBlock(g), shows("style_tags") && tagsBlock(g),
    shows("label_text") && labelBlock(g), isNew && notesBlock(g)].filter(Boolean).join("");
  const foot = confirming
    ? `<p class="dnote">Discard this garment? Its photos and tags will be deleted.</p>
       <div class="dbtns"><button type="button" class="btn primary" data-r-discard ${busy ? "disabled" : ""}>Yes, discard</button><button type="button" class="btn" data-r-keep ${busy ? "disabled" : ""}>Keep reviewing</button></div>`
    : `<div class="dbtns"><button type="button" class="btn primary" data-r-accept ${busy ? "disabled" : ""}>${busy ? "Saving…" : "Accept all"}</button><button type="button" class="btn" data-r-cancel ${busy ? "disabled" : ""}>Cancel</button></div>`;
  return `<div class="dialog review-dialog" role="dialog" aria-modal="true" aria-labelledby="r-title">
    <div class="bhead"><h2 id="r-title">${isNew ? "Review this garment" : "Review the blank details"}</h2><button type="button" class="iconbtn" data-r-cancel aria-label="Close" ${busy ? "disabled" : ""}>×</button></div>
    <div class="bbody">
      <p class="dnote">${isNew ? "Here's what the AI found." : "Here's what the AI filled in. A dash means it couldn't tell."} Click any value to change it, or accept it as is. You can always edit later.</p>
      ${photos.length ? `<div class="review-photos">${photos.map((url, i) => `<img src="${esc(url)}" alt="Photo ${i + 1}">`).join("")}</div>` : ""}
      ${rows ? `<dl class="kv">${rows}</dl>` : ""}
      ${blocks}
      <p class="formerr" role="alert">${esc(error || "")}</p>
    </div>
    <div class="bfoot">${foot}</div>
  </div>`;
}
