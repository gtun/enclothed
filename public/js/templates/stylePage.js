/* TEMPLATE: the "Your style" page: describe your tastes, let the AI tidy it up, save. */
"use strict";

function stylePage(){
  const draft = styleDraft.text ?? prefs.text ?? "";
  const busy = styleDraft.busy;
  const compare = styleDraft.improved === null ? "" : `
    <div class="compare">
      <div class="panel"><h4>Your words</h4><pre>${esc(styleDraft.text)}</pre>
        <div class="btns"><button type="button" class="btn" data-style="keep-mine" ${busy ? "disabled" : ""}>Keep mine</button></div></div>
      <div class="panel"><h4>AI version <small>edit it if anything's off</small></h4>
        <textarea id="style-ai" class="txt" rows="10" ${busy ? "disabled" : ""}>${esc(styleDraft.improved)}</textarea>
        <div class="btns"><button type="button" class="btn primary" data-style="save-ai" ${busy ? "disabled" : ""}>Save AI version</button></div></div>
    </div>`;
  return `<div class="style-page">
    <header><h1>Your style</h1>
      <p class="sub">Describe your tastes and needs once, and every outfit request includes them. For example: you prefer covering arms and legs, you like loose fits, you never wear shorts, or you need glasses with every outfit. Anything you call a need (always, never, must) is followed every time; the rest are defaults a specific request can override.</p></header>
    <div class="field"><label for="style-own">In your own words</label>
      <textarea id="style-own" class="txt" rows="8" maxlength="4000" placeholder="e.g. I like relaxed, layered outfits in earth tones. I always wear my glasses, so suggest frames that go with each outfit. I don't like logos." ${busy ? "disabled" : ""}>${esc(draft)}</textarea></div>
    <div class="btns">
      <button type="button" class="btn llm-action" data-style="improve" title="Uses AI (spends tokens)" ${busy ? "disabled" : ""}>Improve with AI</button>
      <button type="button" class="btn primary" data-style="save-own" ${busy ? "disabled" : ""}>Save as written</button>
      ${prefs.text ? `<button type="button" class="btn quiet" data-style="clear" ${busy ? "disabled" : ""}>Clear</button>` : ""}
      <span class="llm-legend"><i></i>This color means the button uses AI and spends tokens</span>
    </div>
    ${busy ? `<div class="busy" role="status"><span class="spin" aria-hidden="true"></span>Working…</div>` : ""}
    ${compare}
    <div class="panel"><h4>Currently saved <small>${prefs.updated_at ? "updated " + esc(whenLong(prefs.updated_at)) : "nothing yet"}</small></h4>
      ${prefs.text ? `<p class="saved-box">${esc(prefs.text)}</p>` : `<p class="empty">Nothing saved, so outfit requests use only the request itself.</p>`}</div>
  </div>`;
}
