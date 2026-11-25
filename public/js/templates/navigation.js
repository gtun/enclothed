/* TEMPLATE: the text main.js's routing shows: each page's name in the browser tab, the page for an address that finds
   nothing, what "← Back" says, and the page shown when the wardrobe can't load. Keyed by view (main.js's ROUTES). */
"use strict";

/* The tab title is "<name> · enclothed", or just "enclothed" for the wardrobe and for a page that finds nothing. */
const PAGE_NAMES = {
  garment: g => title(g),
  outfit: o => o.aesthetic,
  weigh: g => `Weighing ${title(g)}`,
  look: l => l.title,
  looks: "Looks",
  weighed: "Weighing",
  outfits: "Outfits",
  results: "New suggestions",
  "disowned-garments": "Disowned garments",
  "disowned-outfits": "Disowned outfits",
  style: "Your style",
  usage: "Usage",
  shared: "Shared links",
};
function pageTitle(view, item){
  const name = typeof PAGE_NAMES[view] === "function" ? PAGE_NAMES[view](item) : PAGE_NAMES[view];
  return name ? `${name} · enclothed` : "enclothed";
}

const notFound = (heading, href, link) => `<div class="state"><h1>${heading}</h1><p><a href="${href}">${link}</a></p></div>`;
const NOT_FOUND_PAGES = {
  garment: () => notFound("Garment not found", "#wardrobe", "Back to the wardrobe"),
  outfit: () => notFound("Outfit not found", "#outfits", "Back to outfits"),
  weigh: () => notFound("Not found", "#weighed", "Back to Weighing"),
  look: () => notFound("Look not found", "#looks", "Back to Looks"),
};

/* What "← Back" says, by the page it goes back to. */
const BACK_LABELS = {
  garment: "← Back to garment",
  outfit: "← Back to outfit",
  weigh: "← Back to the verdict",
  weighed: "← Weighing",
  look: "← Back to the look",
  looks: "← Looks",
  results: "← New suggestions",
  outfits: "← Outfits",
  "disowned-garments": "← Disowned garments",
  "disowned-outfits": "← Disowned outfits",
};
const backLabel = view => BACK_LABELS[view] || "← Wardrobe";

const loadFailedPage = message => `<div class="state"><h1>Couldn't load your wardrobe</h1><p>${esc(message)}</p><p>Check that the server is running (<code>uv run fastapi dev src/enclothed/api.py</code>), then refresh.</p></div>`;
