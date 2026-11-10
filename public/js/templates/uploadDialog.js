/* TEMPLATE: the Add garment dialog (tips, button labels, field labels and placeholders), also used to weigh a garment
   and to mimic a look. */
"use strict";

function uploadDialog(){
  if (upload.purpose === "mimic") return mimicDialog();
  const n = upload.files.length, weighing = upload.purpose === "weigh";
  return `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="u-title">
    <div class="bhead"><h2 id="u-title">${weighing ? "Weigh a garment" : "Add a garment"}</h2><button type="button" class="iconbtn" data-u-close aria-label="Close" ${upload.busy ? "disabled" : ""}>×</button></div>
    <div class="bbody">
      ${weighing ? `<p class="dnote">Thinking of buying something? Photograph it and see how it fits with what you own: whether you already have something like it, and outfits it would make. It isn't added to your wardrobe unless you choose Get.</p>` : ""}
      <ul class="tips"><li><b>Front</b> and <b>back</b> of the whole garment, on a hanger or laid flat</li><li>Every <b>label</b>: brand, size, and the care tag with the fabric content</li><li>Close-ups of any details worth noting (optional). Up to ${OPT_UPLOAD_MAX} photos.</li></ul>
      <div class="pickers">
        <label class="btn primary">Take a photo<input type="file" accept="image/*" capture="environment" data-u-input ${upload.busy ? "disabled" : ""}></label>
        <label class="btn">Choose photos<input type="file" accept="image/*" multiple data-u-input ${upload.busy ? "disabled" : ""}></label>
      </div>
      ${n ? `<div class="previews">${upload.files.map((f, i) => `<div class="ph"><img src="${f.url}" alt="Photo ${i + 1}" data-u-img="${i}"><button type="button" class="rm" data-u-rm="${i}" aria-label="Remove photo ${i + 1}" ${upload.busy ? "disabled" : ""}>×</button></div>`).join("")}</div>`
        : `<p class="bhint">No photos yet. On a phone, “Take a photo” opens the camera; take one at a time and repeat.</p>`}
      <p class="bhint paste-hint">You can also paste photos here (Ctrl+V or ⌘V) or drag them in.</p>
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

/* The same dialog for mimic: photos of one whole look rather than one garment, and a note instead of private notes. */
function mimicDialog(){
  const n = upload.files.length, off = upload.busy ? "disabled" : "";
  return `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="u-title">
    <div class="bhead"><h2 id="u-title">Mimic a look</h2><button type="button" class="iconbtn" data-u-close aria-label="Close" ${off}>×</button></div>
    <div class="bbody">
      <p class="dnote">Like how an outfit is put together? Photograph it and see how close you can get with what you own: each piece of the look, matched to a garment of yours.</p>
      <ul class="tips"><li>The <b>whole outfit</b>, head to toe if you can: a lookbook or catalog shot, a store mannequin, a person</li><li>More photos of the <b>same look</b> from other angles help. A screenshot works too. Up to ${OPT_UPLOAD_MAX} photos.</li><li>One look at a time: everything in the photos is read as a single outfit</li></ul>
      <div class="pickers">
        <label class="btn primary">Take a photo<input type="file" accept="image/*" capture="environment" data-u-input ${off}></label>
        <label class="btn">Choose photos<input type="file" accept="image/*" multiple data-u-input ${off}></label>
      </div>
      ${n ? `<div class="previews">${upload.files.map((f, i) => `<div class="ph"><img src="${f.url}" alt="Photo ${i + 1}" data-u-img="${i}"><button type="button" class="rm" data-u-rm="${i}" aria-label="Remove photo ${i + 1}" ${off}>×</button></div>`).join("")}</div>`
        : `<p class="bhint">No photos yet.</p>`}
      <p class="bhint paste-hint">You can also paste photos here (Ctrl+V or ⌘V) or drag them in.</p>
      <div class="field"><label for="u-prompt">Anything about the look <em>(optional, sent to the AI)</em></label>
        <textarea id="u-prompt" class="txt" rows="2" placeholder="e.g. the jacket is the point; ignore the bag; the trousers are wool, not cotton" ${off}>${esc(upload.prompt)}</textarea></div>
      <p class="formerr" id="u-err" role="alert"></p>
    </div>
    <div class="bfoot">${upload.busy ? `<div class="busy" role="status"><span class="spin" aria-hidden="true"></span>Reading the look… this can take up to a minute.</div>` : ""}
      <button type="button" class="btn llm-action wide" data-u-submit title="Uses AI (spends tokens)" ${!n || upload.busy ? "disabled" : ""}>${n ? `Read the look and match it (${plural(n, "photo")})` : "Add at least one photo"}</button></div>
  </div>`;
}
