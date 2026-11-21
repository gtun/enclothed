/* TEMPLATE: the admin's LLM picker, opened by holding L and clicking an AI button (features/llmPicker.js). */
"use strict";

const LLM_FEATURES = {
  tag: "tagging", mend: "mending", outfits: "outfits, weigh and mimic", look: "reading looks",
  describe: "naming outfits", preferences: "style notes", insights: "Ask your wardrobe",
};

function llmDialog(llms, picked){
  const current = picked || (llms.find(l => l.is_default) || llms[0]).provider;
  const option = l => `<label class="llm-choice">
      <input type="radio" name="llm" value="${esc(l.provider)}" ${l.provider === current ? "checked" : ""}>
      <span><b>${esc(l.name)}</b>${l.is_default ? ` <span class="tier">default</span>` : ""}
        ${l.models.map(m => `<span class="llm-model">${esc(m.name)}: ${esc(m.features.map(f => LLM_FEATURES[f] || f).join(", "))}</span>`).join("")}</span>
    </label>`;
  return `<form class="dialog small" role="dialog" aria-modal="true" aria-labelledby="llm-title" data-llm-form>
    <div class="bhead"><h2 id="llm-title">Choose the AI for this tab</h2></div>
    <div class="bbody"><fieldset class="llm-choices" aria-label="AI provider">${llms.map(option).join("")}</fieldset>
      <p class="bhint">Only this tab uses it. It lasts through refreshes, and closing the tab goes back to the default. Other tabs keep their own.</p></div>
    <div class="bfoot"><button type="submit" class="btn primary wide">Use for this tab</button>
      <button type="button" class="btn wide" data-llm-close>Cancel</button></div>
  </form>`;
}
