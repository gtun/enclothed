/* Page routing (#wardrobe, #outfits, #garment-N, #outfit-N, #results, #usage), click handling, Day/Evening, and start-up. Loaded last. */
"use strict";

const app = document.getElementById("app");
const scrollMem = {};
let current = null;
let pageFound = true;   // false on "not found" pages, which skip the first-visit help
const stack = [location.hash || "#wardrobe"];
function currentGarment(){ const m = location.hash.match(/^#garment-(\d+)$/); return m ? byId[m[1]] : null; }
function render(){
  const h = location.hash.slice(1);
  let m, view = "wardrobe", html;
  pageFound = true;
  if ((m = h.match(/^garment-(\d+)$/))){
    const g = byId[m[1]];
    view = "garment"; pageFound = !!g;
    html = g ? garmentPage(g) : `<div class="state"><h1>Garment not found</h1><p><a href="#wardrobe">Back to the wardrobe</a></p></div>`;
    document.title = g ? `${title(g)} · enclothed` : "enclothed";
  } else if ((m = h.match(/^outfit-(\d+)$/))){
    const o = outById[m[1]];
    view = "outfit"; pageFound = !!o;
    html = o ? outfitPage(o) : `<div class="state"><h1>Outfit not found</h1><p><a href="#outfits">Back to outfits</a></p></div>`;
    document.title = o ? `${o.aesthetic} · enclothed` : "enclothed";
  } else if (h === "outfits"){ view = "outfits"; html = outfits(); document.title = "Outfits · enclothed"; }
  else if (h === "results"){ view = "results"; pageFound = !!builder.session?.ids.length; html = resultsPage(); document.title = "New suggestions · enclothed"; }
  else if (h === "disowned-garments"){ view = "disowned-garments"; html = disownedGarments(); document.title = "Disowned garments · enclothed"; }
  else if (h === "disowned-outfits"){ view = "disowned-outfits"; html = disownedOutfits(); document.title = "Disowned outfits · enclothed"; }
  else if (h === "style"){ view = "style"; html = stylePage(); document.title = "Your style · enclothed"; }
  else if (h === "usage"){ view = "usage"; html = usagePage(); document.title = "Usage · enclothed"; }
  else { html = wardrobe(); document.title = "enclothed"; }
  app.innerHTML = html;
  const section = (view === "outfit" || view === "outfits" || view === "results" || view === "disowned-outfits") ? "outfits" : view === "style" || view === "usage" ? view : "wardrobe";
  for (const k of ["wardrobe", "outfits", "style", "usage"]){ const n = document.getElementById("nav-" + k);
    if (k === section) n.setAttribute("aria-current", "page"); else n.removeAttribute("aria-current"); }
  const prev = stack.length > 1 ? stack[stack.length - 2] : null;
  const bk = app.querySelector("[data-back]");
  if (bk && prev){ const pm = prev.match(/^#(garment|outfit)-/);
    bk.textContent = pm ? `← Back to ${pm[1]}` : prev === "#results" ? "← New suggestions" : prev === "#outfits" ? "← Outfits" : prev === "#disowned-garments" ? "← Disowned garments" : prev === "#disowned-outfits" ? "← Disowned outfits" : "← Wardrobe"; }
  return view;
}
function route(){
  closeHelp();
  if (current === "wardrobe" || current === "outfits") scrollMem[current] = scrollY;
  const view = render();
  current = view;
  if (view === "garment") wireGallery();
  if (view === "usage") loadUsage();
  scrollTo(0, (view === "wardrobe" || view === "outfits") ? (scrollMem[view] || 0) : 0);
  if (pageFound) showHelpOnce(view);
}
/* Re-draw the current page after a change, keeping scroll and photo position. */
function refresh(){
  const y = scrollY, gi = galleryIndex();
  const view = render();
  if (view === "garment") wireGallery(gi);
  scrollTo(0, y);
}
addEventListener("hashchange", () => {
  const h = location.hash || "#wardrobe";
  if (stack.length > 1 && stack[stack.length - 2] === h) stack.pop(); else if (stack[stack.length - 1] !== h) stack.push(h);
  route();
});
app.addEventListener("click", e => {
  const f = e.target.closest("[data-cat],[data-scope],[data-req],[data-toggle-disliked]");
  if (f){
    if (f.dataset.cat) cat = f.dataset.cat;
    if (f.dataset.scope) scope = f.dataset.scope;
    if (f.dataset.req) req = f.dataset.req;
    if (f.hasAttribute("data-toggle-disliked")){ showDisliked = !showDisliked; store.set("enclothed-show-disliked", showDisliked); }
    refresh(); return;
  }
  if (e.target.closest("[data-ofilt-toggle]")){ filtersOpen = !filtersOpen; refresh(); if (filtersOpen) document.getElementById("of-q")?.focus(); return; }
  const wv = e.target.closest("[data-wview]");
  if (wv){ wview = wv.dataset.wview; store.set("enclothed-wardrobe-view", wview); refresh(); return; }
  if (handleStyleClick(e)) return;
  if (handleUsageClick(e)) return;
  const of = e.target.closest("[data-ofilt-f],[data-ofilt-w],[data-ofilt-clear]");
  if (of){
    const toggle = (list, v) => list.includes(v) ? list.filter(x => x !== v) : [...list, v];
    if (of.dataset.ofiltF) ofilt.formality = toggle(ofilt.formality, +of.dataset.ofiltF);
    else if (of.dataset.ofiltW) ofilt.warmth = toggle(ofilt.warmth, +of.dataset.ofiltW);
    else ofilt = {q: "", from: "", to: "", formality: [], warmth: []};
    refresh(); return;
  }
  const ed = e.target.closest("[data-edit]");
  if (ed){
    const onText = ed.tagName !== "BUTTON";   // notes: a link is followed, and text can be selected, without opening the editor
    if (onText && (e.target.closest("a") || String(getSelection()))) return;
    openEditor(ed.dataset.edit); return;
  }
  if (e.target.closest("[data-disown]")){ const g = currentGarment(); if (g) openDisown(g); return; }
  if (e.target.closest("[data-reown]")){ const g = currentGarment(); if (g) reown(g); return; }
  if (handleNotesCheckClick(e)) return;
  if (handleBuilderClick(e)) return;
  const r = e.target.closest("[data-rate]");
  if (r){ const id = r.dataset.rateId || (location.hash.match(/^#outfit-(\d+)$/) || [])[1]; if (id && outById[id]) rate(outById[id], r.dataset.rate === "true"); return; }
  const b = e.target.closest("[data-back]");
  if (b){ if (stack.length > 1) history.back(); else location.hash = b.dataset.back; }
});
/* Typing in a filter redraws the page, so put the cursor back where it was. */
let filterTimer = null;
app.addEventListener("input", e => {
  const el = e.target.closest("[data-ofilt]"); if (!el) return;
  ofilt[el.dataset.ofilt] = el.value;
  clearTimeout(filterTimer);
  filterTimer = setTimeout(() => {
    const id = el.id, start = el.selectionStart, end = el.selectionEnd;
    refresh();
    const again = document.getElementById(id);
    if (again){ again.focus(); try { again.setSelectionRange(start, end); } catch (err) {} }
  }, el.type === "date" ? 0 : 200);
});
addEventListener("keydown", e => {
  if (e.key === "Escape" && e.target.closest(".notecheck")){ e.target.closest(".notecheck").querySelector('[data-nc="no"]').click(); return; }
  if (!galleryGo || e.target.closest("input,textarea,[role=combobox]")) return;
  if (e.key === "ArrowRight"){ e.preventDefault(); galleryGo(1); }
  if (e.key === "ArrowLeft"){ e.preventDefault(); galleryGo(-1); }
});

/* ================= Day / Evening ================= */
function paintTheme(){
  const t = document.documentElement.getAttribute("data-theme");
  document.querySelectorAll("[data-t]").forEach(b => b.setAttribute("aria-pressed", b.dataset.t === t));
}
document.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => {
  document.documentElement.setAttribute("data-theme", b.dataset.t);
  try { localStorage.setItem("enclothed-theme", b.dataset.t); } catch (e) {}
  paintTheme();
}));
paintTheme();

/* ================= start ================= */
(async function start(){
  try {
    const profile = await api("/api/profile");
    const [garments, outfitList, sets, options, preferences] = await Promise.all([
      api("/api/garments"), api("/api/outfits"), api("/api/sets"), api("/api/options"), api("/api/preferences")]);
    Object.assign(prefs, preferences);
    G = garments; O = outfitList.map(adoptOutfit); SETS = sets; OPT = options;
    SETTINGS.locale ||= profile.language;
    document.documentElement.dataset.locale = profile.language;
    renderLanguage(profile);
    HEX = Object.fromEntries(options.colors.map(c => [c.name, c.hex]));
    document.getElementById("who").textContent = profile.name;
    renderActAs(profile);
    startHelp(profile.signed_in_as || profile.name);
    usage.admin = profile.is_admin;
    reindex();
    builder.pieces = builder.pieces.filter(id => byId[id] && !isDisowned(byId[id]));
    if (builder.session) builder.session.ids = builder.session.ids.filter(id => outById[id]);
    renderBuilder();
    startInsights();
    route();
  } catch (e) {
    if (e.status === 401 || e.status === 403){ app.innerHTML = accessPage(e.status); hideSections(); return; }
    app.innerHTML = `<div class="state"><h1>Couldn't load your wardrobe</h1><p>${esc(e.message)}</p><p>Check that the server is running (<code>uv run fastapi dev src/enclothed/api.py</code>), then refresh.</p></div>`;
  }
})();
