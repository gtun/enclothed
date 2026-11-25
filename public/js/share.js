/* A share link's page (share.html): loads the frozen copy from /s/<token>/data, then shows it. Loaded last.
   An outfit share is the outfit at #, and each of its garments at #garment-N (N is its place in the share,
   not a wardrobe id). Day/Evening is the app's own setting; the language is this browser's choice for shared
   pages, starting from the language the link was made in. Changing it changes the fixed terms (colors,
   categories...), not text the AI wrote, which stays in the language it was written in.
   Its names start with "share" so none looks like main.js's (app, render) or language.js's: the templates both pages
   load must not call either. */
"use strict";

const shareRoot = document.getElementById("app");
const shareLanguage = document.getElementById("language");
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

function renderShare(){
  const m = location.hash.match(/^#garment-(\d+)$/);
  let html, name;
  if (share.kind === "garment"){ const g = G[0]; html = sharedGarmentPage(g, false); name = title(g); }
  else if (m && byId[m[1]]){ const g = byId[m[1]]; html = sharedGarmentPage(g, true); name = title(g); }
  else { html = sharedOutfitPage(share.outfit); name = share.outfit.aesthetic; }
  shareRoot.innerHTML = html + sharedFooter(share.expires_at);
  document.title = `${name} · enclothed`;
  wireGallery();
}

async function useLanguage(language){
  OPT = await api(`/s/options/${encodeURIComponent(language)}`);
  HEX = Object.fromEntries(OPT.colors.map(c => [c.name, c.hex]));
  SETTINGS.locale = LOCALE_SETTING || language;
  document.documentElement.dataset.locale = language;
  document.documentElement.lang = language;
  shareLanguage.innerHTML = languageOptions(OPT.languages);
  shareLanguage.value = language;
  shareLanguage.hidden = false;
}
shareLanguage.addEventListener("change", async () => {
  const before = document.documentElement.dataset.locale, language = shareLanguage.value;
  shareLanguage.disabled = true;
  try { await useLanguage(language); store.set(LANGUAGE_KEY, language); renderShare(); }
  catch (e) { shareLanguage.value = before; }
  finally { shareLanguage.disabled = false; }
});

addEventListener("hashchange", () => { if (share){ renderShare(); scrollTo(0, 0); } });

/* ================= start ================= */
(async function start(){
  try {
    const data = await api(`${SHARE}/data`);
    const chosen = store.get(LANGUAGE_KEY, null);
    try { await useLanguage(chosen || data.language); }
    catch (e) { if (!chosen) throw e; await useLanguage(data.language); }   // a saved choice the server no longer offers
    share = adoptShare(data);
    renderShare();
  } catch (e) {
    shareRoot.innerHTML = e.status === 404 ? sharedGone()
      : sharedLoadError(e.message);
    document.title = "enclothed";
  }
})();
