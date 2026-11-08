/* TEMPLATE: the Add garment dialog (tips, button labels, field labels and placeholders). */
"use strict";

function uploadDialog(){
  const n = upload.files.length, weighing = upload.purpose === "weigh";
  return `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="u-title">
    <div class="bhead"><h2 id="u-title">${weighing ? "Weigh a garment" : "Add a garment"}</h2><button type="button" class="iconbtn" data-u-close aria-label="Close" ${upload.busy ? "disabled" : ""}>×</button></div>
    <div class="bbody">
      ${weighing ? `<p class="dnote">Thinking of buying something? Photograph it and see how it fits with what you own: whether you already have something like it, and outfits it would make. It isn't added to your wardrobe unless you buy it.</p>` : ""}
      <ul class="tips"><li><b>Front</b> and <b>back</b> of the whole garment, on a hanger or laid flat</li><li>Every <b>label</b>: brand, size, and the care tag with the fabric content</li><li>Close-ups of any details worth noting (optional). Up to ${OPT_UPLOAD_MAX} photos.</li></ul>
      <div class="pickers">
        <label class="btn primary">Take a photo<input type="file" accept="image/*" capture="environment" data-u-input ${upload.busy ? "disabled" : ""}></label>
        <label class="btn">Choose photos<input type="file" accept="image/*" multiple data-u-input ${upload.busy ? "disabled" : ""}></label>
      </div>
      ${n ? `<div class="previews">${upload.files.map((f, i) => `<div class="ph"><img src="${f.url}" alt="Photo ${i + 1}" data-u-img="${i}"><button type="button" class="rm" data-u-rm="${i}" aria-label="Remove photo ${i + 1}" ${upload.busy ? "disabled" : ""}>×</button></div>`).join("")}</div>`
        : `<p class="bhint">No photos yet. On a phone, “Take a photo” opens the camera; take one at a time and repeat.</p>`}
      <div class="field"><label for="u-prompt">Anything the photos don't show <em>(optional, helps the tagging)</em></label>
        <textarea id="u-prompt" class="txt" rows="2" placeholder="e.g. the true color is navy, not black; vintage 1990s; runs small" ${upload.busy ? "disabled" : ""}>${esc(upload.prompt)}</textarea></div>
      <div class="field"><label for="u-notes">Your notes <em>(optional, kept private, never sent to the AI)</em></label>
        <textarea id="u-notes" class="txt" rows="2" placeholder="${weighing ? "e.g. 2nd Street Shibuya, ¥4,800" : "e.g. bought at 2nd Street Taipei; hemmed 2 cm"}" ${upload.busy ? "disabled" : ""}>${esc(upload.notes)}</textarea></div>
      <p class="formerr" id="u-err" role="alert"></p>
    </div>
    <div class="bfoot">${upload.busy ? `<div class="busy" role="status"><span class="spin" aria-hidden="true"></span>Tagging your garment… this can take up to a minute.</div>` : ""}
      <button type="button" class="btn llm-action wide" data-u-submit title="Uses AI (spends tokens)" ${!n || upload.busy ? "disabled" : ""}>${n ? `Tag and review (${plural(n, "photo")})` : "Add at least one photo"}</button></div>
  </div>`;
}
