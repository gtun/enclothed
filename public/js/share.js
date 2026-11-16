/* A share link's page (share.html): loads the frozen copy from /s/<token>/data, then shows it. Loaded last.
   An outfit share is the outfit at #, and each of its garments at #garment-N (N is its place in the share,
   not a wardrobe id). Day/Evening is the app's own setting; the language is this browser's choice for shared
   pages, starting from the language the link was made in. Changing it changes the fixed terms (colors,
   categories...), not text the AI wrote, which stays in the language it was written in. */
"use strict";

const app = document.getElementById("app");
const languagePicker = document.getElementById("language");
const SHARE = location.pathname.replace(/\/+$/, "");   // "/s/<token>"
const LOCALE_SETTING = SETTINGS.locale;   // settings.js can pin a locale for dates; otherwise it follows the language
const LANGUAGE_KEY = "enclothed-share-language";
let share = null;

/* The share's garments, shaped like the app's, so the app's templates can show them. */
function adoptShare(data){
  G = data.kind === "garment" ? [data.garment] : data.garments;
  G = G.map((g, i) => ({...g, id: i, photos: g.photos.map(p => ({
    role: p.role, url: `${SHARE}/photos/${i}/${p.file}`, thumb_url: `${SHARE}/thumbs/${i}/${p.file}`}))}));
  byId = Object.fromEntries(G.map(g => [g.id, g]));
  if (data.outfit){
    const o = data.outfit;
    o.pieces = o.pieces.map(p => ({id: p.garment, advice: p.styling_advice, in_set: p.in_set, set_name: p.set_name}))
      .sort((a, b) => catRank(byId[a.id]) - catRank(byId[b.id]));
  }
  return data;
}

function render(){
  const m = location.hash.match(/^#garment-(\d+)$/);
  let html, name;
  if (share.kind === "garment"){ const g = G[0]; html = sharedGarmentPage(g, false); name = title(g); }
  else if (m && byId[m[1]]){ const g = byId[m[1]]; html = sharedGarmentPage(g, true); name = title(g); }
  else { html = sharedOutfitPage(share.outfit); name = share.outfit.aesthetic; }
  app.innerHTML = html + sharedFooter(share.expires_at);
  document.title = `${name} · enclothed`;
  wireGallery();
}

async function useLanguage(language){
  OPT = await api(`/s/options/${encodeURIComponent(language)}`);
  HEX = Object.fromEntries(OPT.colors.map(c => [c.name, c.hex]));
  SETTINGS.locale = LOCALE_SETTING || language;
  document.documentElement.dataset.locale = language;
  document.documentElement.lang = language;
  languagePicker.innerHTML = OPT.languages.map(l => `<option value="${esc(l.value)}">${esc(l.label)}</option>`).join("");
  languagePicker.value = language;
  languagePicker.hidden = false;
}
languagePicker.addEventListener("change", async () => {
  const before = document.documentElement.dataset.locale, language = languagePicker.value;
  languagePicker.disabled = true;
  try { await useLanguage(language); store.set(LANGUAGE_KEY, language); render(); }
  catch (e) { languagePicker.value = before; }
  finally { languagePicker.disabled = false; }
});

addEventListener("hashchange", () => { if (share){ render(); scrollTo(0, 0); } });
addEventListener("keydown", e => {
  if (!galleryGo) return;
  if (e.key === "ArrowRight"){ e.preventDefault(); galleryGo(1); }
  if (e.key === "ArrowLeft"){ e.preventDefault(); galleryGo(-1); }
});

/* ================= Day / Evening (as in main.js) ================= */
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
    const data = await api(`${SHARE}/data`);
    const chosen = store.get(LANGUAGE_KEY, null);
    try { await useLanguage(chosen || data.language); }
    catch (e) { if (!chosen) throw e; await useLanguage(data.language); }   // a saved choice the server no longer offers
    share = adoptShare(data);
    render();
  } catch (e) {
    app.innerHTML = e.status === 404 ? sharedGone()
      : `<div class="state"><h1>Couldn't load this page</h1><p>${esc(e.message)}</p><p>Try refreshing in a moment.</p></div>`;
    document.title = "enclothed";
  }
})();
