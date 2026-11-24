/* A hidden admin setting: hold L and click any AI button (class "llm-action") to choose which LLM this tab uses.
   The click only opens the picker; the button's own action doesn't run. The choice is kept in sessionStorage
   (core/api.js sends it as X-LLM-Provider), and choosing the default removes it, so the tab follows the server. */
"use strict";

let llmKeyHeld = false, llmAdmin = false, llmList = null, llmReturnFocus = null;

function startLLMPicker(profile){ llmAdmin = profile.is_admin; }

const typingIn = el => el && el.closest && el.closest("input,textarea,select,[contenteditable=true],[role=combobox]");
addEventListener("keydown", e => {
  if (e.key.toLowerCase() === "l" && !e.ctrlKey && !e.metaKey && !e.altKey && !typingIn(e.target)) llmKeyHeld = true;
});
addEventListener("keyup", e => { if (e.key.toLowerCase() === "l") llmKeyHeld = false; });
addEventListener("blur", () => { llmKeyHeld = false; });

/* Capturing on window runs before every other click handler, so the button's own action never starts. */
addEventListener("click", e => {
  if (!llmKeyHeld || !llmAdmin) return;
  const button = e.target.closest && e.target.closest(".llm-action");
  if (!button) return;
  e.preventDefault(); e.stopImmediatePropagation();
  llmKeyHeld = false;   // the dialog takes the keyboard, so the keyup may never come
  openLLMPicker(button);
}, true);

async function openLLMPicker(returnFocus){
  llmReturnFocus = returnFocus;
  try { llmList ||= await api("/api/llms"); }
  catch (e) { toast(e.message, true); return; }
  if (pickedLLM() && !llmList.some(l => l.provider === pickedLLM())){ try { sessionStorage.removeItem(LLM_PICK_KEY); } catch (e) {} }
  const ov = dialogOverlay("llm-picker", ov => {
    ov.addEventListener("click", e => { if (e.target === ov || e.target.closest("[data-llm-close]")) closeLLMPicker(); });
    ov.addEventListener("keydown", e => { e.stopPropagation(); if (e.key === "Escape") closeLLMPicker(); });
    ov.addEventListener("submit", e => { e.preventDefault(); chooseLLM(new FormData(e.target).get("llm")); });
  });
  ov.innerHTML = llmDialog(llmList, pickedLLM());
  showOverlay(ov);
  ov.querySelector("input[name=llm]:checked").focus();
}

function closeLLMPicker(){
  const ov = document.getElementById("llm-picker");
  if (!ov || ov.hidden) return;
  hideOverlay(ov, llmReturnFocus);
}

function chooseLLM(provider){
  const llm = llmList.find(l => l.provider === provider);
  if (!llm) return;
  try {
    if (llm.is_default) sessionStorage.removeItem(LLM_PICK_KEY);
    else sessionStorage.setItem(LLM_PICK_KEY, provider);
  } catch (e) { toast("This browser won't let the page remember a choice, so it can't switch the AI.", true); return; }
  closeLLMPicker();
  toast(`This tab now uses ${llm.name}${llm.is_default ? " (the default)" : ""}.`);
}
