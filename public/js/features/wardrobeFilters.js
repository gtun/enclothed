/* What the wardrobe page shows: the category and scope filters, and the layout. The page's markup is in
   templates/wardrobePage.js. Clicks change them here, and builder.js clears the filters. */
"use strict";

let cat = "all", scope = "any";   // a category or "all"; "any", "sets" or "unstyled"
let wview = store.get("enclothed-wardrobe-view", "grid");   // "grid", "large" or "list"

/* The category, scope and layout buttons. */
function handleWardrobeFilterClick(e){
  const f = e.target.closest("[data-cat],[data-scope]");
  if (f){
    if (f.dataset.cat) cat = f.dataset.cat;
    if (f.dataset.scope) scope = f.dataset.scope;
    refresh(); return true;
  }
  const wv = e.target.closest("[data-wview]");
  if (wv){ wview = wv.dataset.wview; store.set("enclothed-wardrobe-view", wview); refresh(); return true; }
  return false;
}
