/* The outfit builder panel: picking pieces, generating suggestions, saving your own outfit. Its markup is in templates/builderPanel.js. */
"use strict";

/* ================= outfit builder =================
   A floating panel for putting an outfit together: pick pieces, add details, then either
   ask for suggestions (the pieces become anchors) or save it as your own outfit.
   A "session" is one run of suggestions: retrying after a change adds to the same results page. */
/* count and risk are how many suggestions to ask for and at what tier ("mix" spreads them across safe, stretch and bold).
   silhouette is the letter shape every outfit should form, or null for any. They aren't cleared with the rest of the
   builder, so they carry over to the next outfit. */
const builder = Object.assign({open: false, min: false, pieces: [], details: "", manual: false, form: {aesthetic: "", explanation: "", missing: "", advice: {}}, session: null, count: 3, risk: "mix", silhouette: null},
  store.get("enclothed-builder", {}));
let builderBusy = false, builderBusyText = "", restoringTree = false, silhouetteOpen = false;
const saveBuilder = () => store.set("enclothed-builder", {open: builder.open, min: builder.min, pieces: builder.pieces, details: builder.details,
  manual: builder.manual, form: builder.form, session: builder.session, count: builder.count, risk: builder.risk, silhouette: builder.silhouette});
const sortedPieces = () => builder.pieces.map(id => byId[id]).filter(Boolean).sort((a, b) => catRank(a) - catRank(b) || a.id - b.id);
const sameSet = (a, b) => a.length === b.length && [...a].sort().join() === [...b].sort().join();
const unchangedSinceLast = () => builder.session && sameSet(builder.pieces, builder.session.last.pieces) && builder.details.trim() === builder.session.last.details.trim()
  && builder.count === (builder.session.last.count ?? 3) && builder.risk === (builder.session.last.risk ?? "mix")
  && builder.silhouette === (builder.session.last.silhouette ?? null);

function pickButton(g){
  const on = builder.pieces.includes(g.id);
  return `<button type="button" class="addbtn" data-pick="${g.id}" aria-pressed="${on}" aria-label="${on ? "Remove from outfit" : "Add to outfit"}: ${esc(title(g))}" title="${on ? "Remove from outfit" : "Add to outfit"}">${on ? "−" : "+"}</button>`;
}
function togglePiece(id){
  id = +id;
  if (builder.pieces.includes(id)) builder.pieces = builder.pieces.filter(x => x !== id);
  else { builder.pieces = [...builder.pieces, id]; if (!builder.open){ builder.open = true; builder.min = isPhone(); } }
  saveBuilder(); renderBuilder(); refresh();
}
const isPhone = () => matchMedia("(max-width:900px)").matches;
function openBuilder(){ builder.open = true; builder.min = false; saveBuilder(); renderBuilder(); refresh(); }
function closeBuilder(){ builder.open = false; saveBuilder(); renderBuilder(); refresh(); }
function newOutfit(){
  Object.assign(builder, {open: true, min: false, pieces: [], details: "", manual: false, form: {aesthetic: "", explanation: "", missing: "", advice: {}}, session: null});
  saveBuilder(); renderBuilder();
  if (location.hash !== "#wardrobe") location.hash = "#wardrobe"; else refresh();
}
/* Start a fresh outfit from these pieces, staying on the current page (weigh's outfit links use it). */
function openPiecesInBuilder(ids){
  Object.assign(builder, {open: true, min: false, pieces: ids, details: "", manual: false, form: {aesthetic: "", explanation: "", missing: "", advice: {}}, session: null});
  saveBuilder(); renderBuilder(); refresh();
}
function scrollToCategory(c){
  const goScroll = () => document.getElementById("rail-" + c)?.scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
  if (cat !== "all" && cat !== c) cat = "all";
  scope = "any";
  if (current !== "wardrobe"){ location.hash = "#wardrobe"; setTimeout(goScroll, 60); }
  else { refresh(); goScroll(); }
}

function renderBuilder(){
  let el = document.getElementById("builder");
  if (!el){ el = document.createElement("aside"); el.id = "builder"; el.className = "builder"; el.setAttribute("aria-label", "Outfit builder"); document.body.appendChild(el); }
  document.body.classList.toggle("with-builder", builder.open);
  document.body.classList.toggle("builder-min", builder.open && builder.min);
  el.hidden = !builder.open;
  el.classList.toggle("min", builder.min);
  if (!builder.open) return;
  const keepScroll = el.querySelector(".bbody")?.scrollTop || 0;
  const openTrees = [...el.querySelectorAll("details[data-tree][open]")].map(d => d.dataset.tree);
  el.innerHTML = builderPanel();

  restoringTree = true;
  openTrees.forEach(c => { const d = el.querySelector(`details[data-tree="${CSS.escape(c)}"]`); if (d) d.open = true; });
  setTimeout(() => { restoringTree = false; }, 60);
  el.querySelector(".bbody").scrollTop = keepScroll;
  const options = OWNED.filter(g => !builder.pieces.includes(g.id)).sort((a, b) => catRank(a) - catRank(b))
    .map(g => ({value: g.id, label: `${title(g)} · ${colorName(g.primary_color)}${SHOW_IDS ? ` · #${g.id}` : ""}`, hex: hex(g.primary_color)}));
  combo(el.querySelector("#b-search"), {options, keepOpen: true, autofocus: false, collapsed: true, placeholder: "Type a garment name to add it…", onPick: id => { togglePiece(id); document.querySelector("#b-search input")?.focus(); }});
}
function updateBuilderButtons(){
  const el = document.getElementById("builder"); if (!el) return;
  const pieces = sortedPieces();
  const reasonEl = el.querySelector("#b-reason");
  if (builder.manual){
    const reason = saveBlockedReason(pieces);
    el.querySelector("[data-save-own]").disabled = !!reason || builderBusy; reasonEl.textContent = reason;
    const fill = el.querySelector("[data-describe]"), label = describeLabel(pieces);
    if (fill){ fill.disabled = !label || builderBusy; if (label) fill.textContent = label; }
  } else {
    const reason = suggestBlockedReason(pieces);
    el.querySelector("[data-suggest]").disabled = !!reason || builderBusy; reasonEl.textContent = reason;
  }
}
document.addEventListener("input", e => {
  if (!e.target.closest("#builder")) return;
  const t = e.target;
  if (t.hasAttribute("data-details")) builder.details = t.value;
  else if (t.dataset.form) builder.form[t.dataset.form] = t.value;
  else if (t.dataset.advice) builder.form.advice[t.dataset.advice] = t.value;
  else return;
  saveBuilder(); updateBuilderButtons();
});
document.addEventListener("toggle", e => {
  const d = e.target;
  if (!restoringTree && d.matches && d.matches("#builder details[data-tree]") && d.open) scrollToCategory(d.dataset.tree);
}, true);

document.addEventListener("toggle", e => { if (e.target.matches?.("#builder details[data-sil-section]")) silhouetteOpen = e.target.open; }, true);

async function suggest(){
  if (builderBusy) return;
  const fresh = !builder.session;
  const sent = {pieces: builder.pieces.slice(), details: builder.details, count: builder.count, risk: builder.risk, silhouette: builder.silhouette};
  builderBusy = true; renderBuilder();
  try {
    const created = (await api("/api/outfits/suggestions", {method: "POST", body: {anchors: sent.pieces, details: sent.details,
      count: sent.count, riskiness: sent.risk === "mix" ? null : sent.risk, silhouette: sent.silhouette}})).map(adoptOutfit);
    if (!created.length) throw new Error("No complete outfits came back this time. Try again, or adjust the pieces or details.");
    O.push(...created); reindex();
    const ids = created.map(o => o.id);
    builder.session = fresh ? {ids, last: sent} : {ids: [...builder.session.ids, ...ids], last: sent};
    builder.open = false;
    saveBuilder();
    toast(`${plural(created.length, "new outfit")}`);
    builderBusy = false; renderBuilder();
    if (location.hash === "#results") refresh(); else location.hash = "#results";
    return;
  } catch (e) { toast(e.message, true); }
  builderBusy = false; renderBuilder();
}
/* Ask the AI for whichever of the name and "why it works" are blank. Anything typed, even while waiting, is kept. */
async function describeOwn(){
  if (builderBusy) return;
  const pieces = sortedPieces();
  if (!describeLabel(pieces)) return;
  builderBusy = true; builderBusyText = "Writing a name and why it works…"; renderBuilder();
  try {
    const f = builder.form;
    const out = await api("/api/outfits/describe", {method: "POST", body: {garments: pieces.map(g => g.id), details: builder.details || null,
      aesthetic: f.aesthetic.trim() || null, explanation: f.explanation.trim() || null}});
    if (!f.aesthetic.trim()) f.aesthetic = out.aesthetic;
    if (!f.explanation.trim()) f.explanation = out.explanation;
    saveBuilder();
  } catch (e) { toast(e.message, true); }
  builderBusy = false; builderBusyText = ""; renderBuilder();
}
async function saveOwn(){
  if (builderBusy) return;
  builderBusy = true; renderBuilder();
  try {
    const body = {aesthetic: builder.form.aesthetic, explanation: builder.form.explanation, missing: builder.form.missing || null, details: builder.details || null,
      garments: sortedPieces().map(g => ({garment_id: g.id, styling_advice: builder.form.advice[g.id] || null}))};
    const created = adoptOutfit(await api("/api/outfits", {method: "POST", body}));
    O.push(created); reindex();
    Object.assign(builder, {open: false, pieces: [], details: "", manual: false, form: {aesthetic: "", explanation: "", missing: "", advice: {}}, session: null});
    saveBuilder(); builderBusy = false; renderBuilder();
    toast("Outfit saved");
    location.hash = "#outfit-" + created.id;
    return;
  } catch (e) { toast(e.message, true); }
  builderBusy = false; renderBuilder();
}
function handleBuilderClick(e){
  const t = e.target.closest("[data-pick],[data-new-outfit],[data-builder-open],[data-results-retry],[data-results-done],[data-add-garment]");
  if (!t) return false;
  if (t.dataset.pick){ e.preventDefault(); togglePiece(t.dataset.pick); }
  else if (t.hasAttribute("data-new-outfit")) newOutfit();
  else if (t.hasAttribute("data-builder-open")) openBuilder();
  else if (t.hasAttribute("data-add-garment")) openUpload();
  else if (t.hasAttribute("data-results-retry")){ builder.open = true; builder.min = false; builder.manual = false; saveBuilder(); renderBuilder(); location.hash = "#wardrobe"; }
  else if (t.hasAttribute("data-results-done")){
    Object.assign(builder, {open: false, pieces: [], details: "", manual: false, session: null}); saveBuilder(); renderBuilder(); location.hash = "#outfits"; }
  return true;
}
document.addEventListener("click", e => {
  if (!e.target.closest("#builder")) return;
  if (handleBuilderClick(e)) return;
  const t = e.target.closest("button"); if (!t) return;
  if (t.hasAttribute("data-builder-close")) closeBuilder();
  else if (t.hasAttribute("data-builder-min")){ builder.min = !builder.min; saveBuilder(); renderBuilder(); }
  else if (t.hasAttribute("data-suggest")) suggest();
  else if (t.hasAttribute("data-save-own")) saveOwn();
  else if (t.hasAttribute("data-describe")) describeOwn();
  else if (t.dataset.manual){ builder.manual = t.dataset.manual === "on"; saveBuilder(); renderBuilder(); }
  else if (t.dataset.count){ builder.count = Number(t.dataset.count); saveBuilder(); renderBuilder(); }
  else if (t.dataset.risk){ builder.risk = t.dataset.risk; saveBuilder(); renderBuilder(); }
  else if (t.dataset.sil){ builder.silhouette = builder.silhouette === t.dataset.sil ? null : t.dataset.sil; saveBuilder(); renderBuilder(); }   // picking it again goes back to any
});
