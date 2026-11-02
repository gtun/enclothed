/* "Your style": the user's own description of their tastes and needs, an optional AI rewrite,
   and saving. The saved text is sent with every outfit request. Markup: templates/stylePage.js. */
"use strict";

const prefs = {text: null, updated_at: null};          // what's saved on the server
const styleDraft = {text: null, improved: null, busy: false};   // what's on screen

async function improveStyle(){
  const text = document.getElementById("style-own").value.trim();
  if (!text) return toast("Write something first.", true);
  styleDraft.text = text; styleDraft.busy = true; refresh();
  try {
    styleDraft.improved = (await api("/api/preferences/improve", {method: "POST", body: {text}})).text;
  } catch (e) { toast(e.message, true); }
  styleDraft.busy = false; refresh();
}
async function saveStyle(text){
  styleDraft.busy = true; refresh();
  try {
    Object.assign(prefs, await api("/api/preferences", {method: "PUT", body: {text}}));
    styleDraft.text = null; styleDraft.improved = null;
    toast(prefs.text ? "Saved. It's included with every outfit request." : "Cleared.");
  } catch (e) { toast(e.message, true); }
  styleDraft.busy = false; refresh();
}
function handleStyleClick(e){
  const t = e.target.closest("[data-style]"); if (!t) return false;
  const action = t.dataset.style;
  if (action === "improve") improveStyle();
  else if (action === "save-own") saveStyle(document.getElementById("style-own").value);
  else if (action === "save-ai") saveStyle(document.getElementById("style-ai").value);
  else if (action === "keep-mine"){ styleDraft.improved = null; refresh(); }
  else if (action === "clear"){ if (confirm("Clear your saved style notes?")) saveStyle(""); }
  return true;
}
document.addEventListener("input", e => { if (e.target.id === "style-own") styleDraft.text = e.target.value; });
