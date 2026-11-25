/* Page routing, the app's clicks, and start-up. Loaded last. Each page is one row of ROUTES; its text is in
   templates/navigation.js. Each feature handles its own clicks (CLICK_HANDLERS). */
"use strict";

const app = document.getElementById("app");
const scrollMem = {};
let current = null;
let pageFound = true;   // false on "not found" pages, which skip the first-visit help
const stack = [location.hash || "#wardrobe"];
function currentGarment(){ const m = location.hash.match(/^#garment-(\d+)$/); return m ? byId[m[1]] : null; }

/* A page about one garment, outfit or look, or the page for one that isn't there. */
const itemPage = (view, item, draw) => item ? {html: draw(item), title: pageTitle(view, item), found: true}
                                            : {html: NOT_FOUND_PAGES[view](), title: pageTitle(), found: false};
const listPage = (view, draw) => ({html: draw(), title: pageTitle(view), found: true});

/* Every page, by its address (the hash, without #). view names it for help topics and the "← Back" wording, section
   is the top-bar item it lights up, and page(match) draws it: {html, title, found}, plus view when it shows a
   different page than the address names. gallery wires the photo carousel; enter runs when the page is opened;
   keepScroll comes back to where you were. The last row catches every other address. */
const ROUTES = [
  {path: /^garment-(\d+)$/, view: "garment", section: "wardrobe", gallery: true, enter: () => reworkPageShown(currentGarment()),
   page: m => itemPage("garment", byId[m[1]], garmentPage)},
  {path: /^outfit-(\d+)$/, view: "outfit", section: "outfits", page: m => itemPage("outfit", outById[m[1]], outfitPage)},
  {path: /^weigh-(\d+)$/, view: "weigh", section: "wardrobe", page: m => {
    const g = byId[m[1]];
    if (g && !isCandidate(g)) return {html: garmentPage(g), title: pageTitle(), found: false, view: "garment"};   // bought since: an old link shows it in the wardrobe
    return itemPage("weigh", g, weighPage);
  }},
  {path: /^look-(\d+)$/, view: "look", section: "outfits", page: m => itemPage("look", lookById[m[1]], lookPage)},
  {path: /^looks$/, view: "looks", section: "outfits", page: () => listPage("looks", looksPage)},
  {path: /^weighed$/, view: "weighed", section: "wardrobe", page: () => listPage("weighed", weighedPage)},
  {path: /^outfits$/, view: "outfits", section: "outfits", keepScroll: true, page: () => listPage("outfits", outfits)},
  {path: /^results$/, view: "results", section: "outfits", page: () => {
    const found = !!builder.session?.ids.length;   // before drawing, as the page may change the session
    return {...listPage("results", resultsPage), found};
  }},
  {path: /^disowned-garments$/, view: "disowned-garments", section: "wardrobe", page: () => listPage("disowned-garments", disownedGarments)},
  {path: /^disowned-outfits$/, view: "disowned-outfits", section: "outfits", page: () => listPage("disowned-outfits", disownedOutfits)},
  {path: /^style$/, view: "style", section: "style", page: () => listPage("style", stylePage)},
  {path: /^usage$/, view: "usage", section: "usage", enter: loadUsage, page: () => listPage("usage", usagePage)},
  {path: /^shared$/, view: "shared", section: "shared", enter: loadSharedLinks, page: () => listPage("shared", sharedLinksPage)},
  {path: /^/, view: "wardrobe", section: "wardrobe", keepScroll: true, page: () => listPage("wardrobe", wardrobe)},
];
const routeFor = hash => ROUTES.find(r => r.path.test(hash.replace(/^#/, "")));
const routeByView = view => ROUTES.find(r => r.view === view);
const SECTIONS = ["wardrobe", "outfits", "style", "usage", "shared"];   // the top bar: #nav-wardrobe and so on

function render(){
  const asked = routeFor(location.hash);
  const page = asked.page(location.hash.slice(1).match(asked.path));
  const view = page.view || asked.view;
  pageFound = page.found;
  document.title = page.title;
  app.innerHTML = page.html;
  const section = routeByView(view).section;
  for (const k of SECTIONS){
    const n = document.getElementById("nav-" + k);
    if (k === section) n.setAttribute("aria-current", "page"); else n.removeAttribute("aria-current");
  }
  const prev = stack.length > 1 ? stack[stack.length - 2] : null;
  const bk = app.querySelector("[data-back]");
  if (bk && prev) bk.textContent = backLabel(routeFor(prev).view);
  return view;
}
function route(){
  closeHelp();
  if (routeByView(current)?.keepScroll) scrollMem[current] = scrollY;
  weighConfirm = false; lookConfirm = false;
  const view = render();
  current = view;
  const page = routeByView(view);
  if (page.gallery) wireGallery();
  page.enter?.();
  scrollTo(0, page.keepScroll ? (scrollMem[view] || 0) : 0);
  if (pageFound) showHelpOnce(view);
}
/* Re-draw the current page after a change, keeping scroll and photo position. */
function refresh(){
  const y = scrollY, gi = galleryIndex();
  const view = render();
  if (routeByView(view).gallery) wireGallery(gi);
  scrollTo(0, y);
}
addEventListener("hashchange", () => {
  const h = location.hash || "#wardrobe";
  if (stack.length > 1 && stack[stack.length - 2] === h) stack.pop(); else if (stack[stack.length - 1] !== h) stack.push(h);
  route();
});

/* "← Back": the previous page if there is one in this tab, or the page the button names. */
function handleBackClick(e){
  const b = e.target.closest("[data-back]");
  if (!b) return false;
  if (stack.length > 1) history.back(); else location.hash = b.dataset.back;
  return true;
}
/* Each takes the click and returns true if it was theirs; the first one that does, wins. The order only matters
   where one button could match two, so keep new ones near the feature they belong with. */
const CLICK_HANDLERS = [
  handleWardrobeFilterClick, handleOutfitFilterClick, handleStyleClick, handleUsageClick, handleSharedLinksClick,
  handleReworkClick, handleEditClick, handleMendClick, handleDisownClick, handleNotesCheckClick, handleBuilderClick,
  handleWeighClick, handleMimicClick, handleRateClick, handleBackClick,
];
app.addEventListener("click", e => { CLICK_HANDLERS.some(handle => handle(e)); });

/* ================= start ================= */
(async function start(){
  try {
    const profile = await api("/api/profile");
    SHOW_IDS = profile.is_admin;
    const [garments, outfitList, sets, options, preferences, weighs, looks] = await Promise.all([
      api("/api/garments"), api("/api/outfits"), api("/api/sets"), api("/api/options"), api("/api/preferences"), api("/api/weighs"), api("/api/looks")]);
    WEIGHS = weighs; LOOKS = looks;
    Object.assign(prefs, preferences);
    G = garments; O = outfitList.map(adoptOutfit); SETS = sets; OPT = options;
    SETTINGS.locale ||= profile.language;
    document.documentElement.dataset.locale = profile.language;
    renderLanguage(profile);
    HEX = Object.fromEntries(options.colors.map(c => [c.name, c.hex]));
    document.getElementById("who").textContent = profile.name;
    renderActAs(profile);
    startHelp(profile.signed_in_as || profile.name);
    startLLMPicker(profile);
    usage.admin = profile.is_admin;
    sharedLinks.demo = profile.is_demo;
    reindex();
    builder.pieces = builder.pieces.filter(id => byId[id] && !isDisowned(byId[id]) && !isCandidate(byId[id]));
    if (builder.session) builder.session.ids = builder.session.ids.filter(id => outById[id]);
    renderBuilder();
    startInsights();
    route();
  } catch (e) {
    if (e.status === 401 || e.status === 403){ app.innerHTML = accessPage(e.status); hideSections(); return; }
    app.innerHTML = loadFailedPage(e.message);
  }
})();
