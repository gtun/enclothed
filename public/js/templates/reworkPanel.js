/* TEMPLATE: Rework on the garment page: the button, the panel where you describe a change, and the strip of
   reworks you've kept. Each image is an edited copy of the front photo, never one of the garment's photos.
   Behavior is in features/rework.js, and the seam ripper (REWORK_ICON) in core/format.js. */
"use strict";

const REWORK_HINT = "Make it bright blue";

/* On a wardrobe card, beside the + button: opens the garment page with the panel ready to type in. */
const reworkCardButton = g => `<button type="button" class="addbtn rwcard" data-rework-open="${g.id}" aria-label="Rework: ${esc(title(g))}" title="Rework: see a change">${REWORK_ICON}</button>`;

const reworkButton = g => g.photos.length ? `<button type="button" class="btn rwbtn" data-rw-toggle aria-expanded="${reworkOpenFor(g)}" aria-controls="rework" title="See this garment with a change you describe. Uses AI">${REWORK_ICON}Rework</button>` : "";

function reworkPanel(g){
  if (!reworkOpenFor(g)) return "";
  const r = rework, busy = r.busy;
  const left = r.left === null ? "" : `<p class="bhint">${r.left === 1 ? "1 rework" : `${r.left} reworks`} left today in the demo.</p>`;
  const latest = r.latest && r.latest.garment_id === g.id ? `<div class="rwcompare">
      <figure><img src="${esc(encodeURI(g.photos[0].thumb_url))}" alt="${esc(title(g))} as it is"><figcaption>As it is</figcaption></figure>
      <figure><img src="${esc(r.latest.url)}" alt="Preview: ${esc(r.latest.instruction)}"><figcaption><b>Preview</b> · ${esc(r.latest.instruction)}</figcaption></figure></div>` : "";
  return `<div class="panel rwpanel" id="rework">
    <label for="rw-text"><b>What would you change?</b></label>
    <textarea id="rw-text" class="txt" rows="1" maxlength="300" placeholder="${esc(REWORK_HINT)}" data-rw-text ${busy ? "readonly" : ""}>${esc(r.text)}</textarea>
    ${r.privacySeen ? "" : `<p class="bhint">Your garment's front photo and these words go to OpenAI to make the preview. Your notes and details don't.</p>`}
    ${left}
    ${r.error ? `<p class="rwerror" role="alert">${esc(r.error)}</p>` : ""}
    <div class="hero-actions"><button type="button" class="btn rwgo" data-rw-go ${busy ? "disabled" : ""}>${busy ? "Reworking…" : "Rework"}</button>
      <button type="button" class="btn quiet" data-rw-cancel ${busy ? "disabled" : ""}>${latest ? "Done" : "Cancel"}</button>
      ${busy ? `<span class="bhint" role="status">This takes about half a minute.</span>` : ""}</div>
    ${latest}
  </div>`;
}

function reworkStrip(g){
  const list = reworksOf(g);
  if (!list.length) return "";
  return `<div class="panel"><h4>Reworks <small>previews, not photos</small></h4>
    <div class="rwstrip">${list.map(r => `<figure>
      <a href="${esc(r.url)}" target="_blank" rel="noopener"><img src="${esc(r.url)}" alt="Preview: ${esc(r.instruction)}" loading="lazy"></a>
      <figcaption><span>${esc(r.instruction)}</span><time>${esc(when(r.created_at))}</time>
        <button type="button" class="btn quiet rwdel" data-rw-delete="${r.id}">${rework.confirmDelete === r.id ? "Delete it?" : "Delete"}</button></figcaption>
    </figure>`).join("")}</div></div>`;
}
