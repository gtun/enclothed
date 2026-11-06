/* The shared data: garments (G), outfits (O), sets, options, and the lookups built from them. */
"use strict";

let G = [], O = [], SETS = [], OPT = null;
let SHOW_IDS = false;
let OWNED = [], DISOWNED = [], SHOWN = [], DISOWNED_O = [];   // garments split by ownership, outfits split by whether they have a disowned piece (indexes.js)
let byId = {}, outById = {}, setById = {}, outfitsOf = {}, allOutfitsOf = {}, REQUESTS = [], HEX = {};
const RAIL_ORDER = ["outerwear", "top", "bottom", "one-piece", "shoes", "accessory"];

const store = {
  get(k, d){ try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};
let showDisliked = store.get("enclothed-show-disliked", false);
