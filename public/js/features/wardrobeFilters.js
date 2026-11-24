/* What the wardrobe page shows: the category and scope filters, and the layout. The page's markup is in
   templates/wardrobePage.js; main.js changes these on click, and builder.js clears the filters. */
"use strict";

let cat = "all", scope = "any";   // a category or "all"; "any", "sets" or "unstyled"
let wview = store.get("enclothed-wardrobe-view", "grid");   // "grid", "large" or "list"
