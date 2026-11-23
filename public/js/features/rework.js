/* Rework: describe a change to a garment ("Make it bright blue") and see its front photo edited that way.
   The seam ripper on a wardrobe card opens the garment page with the panel open and the cursor in the box; the
   Rework button on the garment page opens and closes it. Kept previews show in a strip on the garment page.
   Markup is in templates/reworkPanel.js; the server side is reworks.py. */
"use strict";

const REWORK_PRIVACY_KEY = "enclothed-rework-privacy-seen";
let rework = {
  garmentId: null,   // the garment the panel and the state below belong to
  open: false, text: "", busy: false, error: "",
  focus: false,      // put the cursor in the box after the next render (opened from a card)
  list: {},          // garment id → its reworks, newest first, once loaded
  latest: null,      // the rework just made, shown beside the photo in the panel
  left: null,        // reworks left today in the demo; null where there's no limit
  confirmDelete: null,
  privacySeen: store.get(REWORK_PRIVACY_KEY, false),
};
const reworkOpenFor = g => rework.open && rework.garmentId === g.id;
const reworksOf = g => rework.list[g.id] || [];

/* Moving to another garment starts fresh, unless a card's seam ripper just opened it. */
function reworkFor(id){
  if (rework.garmentId === id) return;
  Object.assign(rework, {garmentId: id, open: false, text: "", error: "", latest: null, confirmDelete: null});
}

/* Redraw without losing the cursor in the box. */
function reworkRefresh(){
  const box = document.getElementById("rw-text");
  const typing = box && document.activeElement === box ? [box.selectionStart, box.selectionEnd] : null;
  refresh();
  const again = document.getElementById("rw-text");
  if (again){ fitReworkBox(again); if (typing){ again.focus(); again.setSelectionRange(...typing); } }
}
function fitReworkBox(box){ box.style.height = "auto"; box.style.height = box.scrollHeight + 2 + "px"; }
function focusReworkBox(){
  const box = document.getElementById("rw-text"); if (!box) return;
  fitReworkBox(box);
  box.focus(); box.setSelectionRange(box.value.length, box.value.length);
  document.getElementById("rework").scrollIntoView({block: "nearest", behavior: "smooth"});
}

/* main.js calls this each time a garment page is shown. */
async function reworkPageShown(g){
  if (!g) return;
  reworkFor(g.id);
  if (rework.focus){ rework.focus = false; setTimeout(focusReworkBox, 0); }   // after route() scrolls to the top
  try {
    const [list, allowance] = await Promise.all([api(`/api/garments/${g.id}/reworks`), api("/api/reworks/allowance")]);
    rework.list[g.id] = list;
    rework.left = allowance.left;
    if (currentGarment()?.id === g.id) reworkRefresh();
  } catch (e) {
    if (e.status !== 404) toast(`Couldn't load this garment's reworks: ${e.message}`, true);
  }
}

function toggleRework(g){
  reworkFor(g.id);
  rework.open = !rework.open;
  rework.error = "";
  refresh();
  if (rework.open) focusReworkBox(); else document.querySelector("[data-rw-toggle]")?.focus();
}

async function sendRework(g){
  if (rework.busy) return;
  const instruction = rework.text.trim();
  if (!instruction){ rework.error = "Describe the change first, such as “" + REWORK_HINT + "”."; reworkRefresh(); return; }
  Object.assign(rework, {busy: true, error: ""});
  reworkRefresh();
  try {
    const made = await api(`/api/garments/${g.id}/reworks`, {method: "POST", body: {instruction}});
    rework.list[g.id] = [made, ...(rework.list[g.id] || [])];
    if (rework.garmentId === g.id) Object.assign(rework, {latest: made, text: ""});
    if (rework.left !== null) rework.left = Math.max(0, rework.left - 1);
    if (!rework.privacySeen){ rework.privacySeen = true; store.set(REWORK_PRIVACY_KEY, true); }
  } catch (e) {
    if (rework.garmentId === g.id) rework.error = e.message;
    else toast(e.message, true);   // they've moved on to another page
  } finally {
    rework.busy = false;
    if (currentGarment()?.id === g.id) reworkRefresh();
  }
}

async function deleteRework(g, id){
  if (rework.confirmDelete !== id){ rework.confirmDelete = id; refresh(); return; }
  rework.confirmDelete = null;
  try {
    await api(`/api/reworks/${id}`, {method: "DELETE"});
    rework.list[g.id] = reworksOf(g).filter(r => r.id !== id);
    if (rework.latest?.id === id) rework.latest = null;
  } catch (e) {
    toast(e.message, true);
  }
  refresh();
}

/* Clicks inside the page (main.js). True when it was a Rework click. */
function handleReworkClick(e){
  const card = e.target.closest("[data-rework-open]");
  if (card){
    const id = +card.dataset.reworkOpen;
    reworkFor(id);
    Object.assign(rework, {open: true, focus: true, error: ""});
    location.hash = `#garment-${id}`;
    return true;
  }
  const g = currentGarment(); if (!g) return false;
  if (e.target.closest("[data-rw-toggle]")){ toggleRework(g); return true; }
  if (e.target.closest("[data-rw-go]")){ sendRework(g); return true; }
  if (e.target.closest("[data-rw-cancel]")){ Object.assign(rework, {open: false, text: "", error: "", latest: null}); refresh(); document.querySelector("[data-rw-toggle]")?.focus(); return true; }
  const del = e.target.closest("[data-rw-delete]");
  if (del){ deleteRework(g, +del.dataset.rwDelete); return true; }
  if (rework.confirmDelete !== null){ rework.confirmDelete = null; refresh(); }
  return false;
}

/* Typing in the box: keep the words across redraws, grow the box, and Enter sends (Shift+Enter for a new line). */
document.addEventListener("input", e => {
  if (!e.target.matches?.("[data-rw-text]")) return;
  rework.text = e.target.value;
  fitReworkBox(e.target);
});
document.addEventListener("keydown", e => {
  if (!e.target.matches?.("[data-rw-text]")) return;
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing){ e.preventDefault(); const g = currentGarment(); if (g) sendRework(g); }
  if (e.key === "Escape" && !rework.busy){ document.querySelector("[data-rw-cancel]")?.click(); }
});
