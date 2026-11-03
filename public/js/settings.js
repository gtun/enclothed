/* settings.js: things you may want to change. Loaded first, so everything else can use it. */
"use strict";

const SETTINGS = {
  /* Language and region for dates, e.g. "en-US", "en-GB", "ja-JP", "zh-TW".
     undefined = whatever your browser is set to. */
  locale: undefined,

  /* Date formats. Each is a set of Intl.DateTimeFormat options:
     weekday: "short" | "long"; year: "numeric" | "2-digit"; month: "numeric" | "2-digit" | "short" | "long";
     day: "numeric" | "2-digit"; hour / minute: "numeric" | "2-digit"; hour12: true | false.
     Or replace one with a function that gets a Date and returns text, for full control:
       short: d => `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`, */
  dates: {
    short: {month: "short", day: "numeric"},                                                    // cards and lists: "Nov 1"
    long: {weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}, // outfit page: "Sun, Nov 1, 9:12 PM"
    day: {year: "numeric", month: "short", day: "numeric"},                                     // garment "Added": "Nov 1, 2026"
  },

  /* Color of buttons that call the AI (and so spend tokens), e.g. "Generate outfit suggestions".
     "wardrobe": picked from your own clothes. For Day, the most common colorful accent among
                 light-colored garments; for Evening, among dark-colored garments. Falls back to
                 theme.css when nothing colorful enough is found.
     "theme":    always use --llm / --on-llm from css/theme.css. */
  aiButtonColor: "wardrobe",

  /* Garments you no longer own, in the places they can still appear. outfitCard applies on the
     Disowned outfits page, and outfitPage on any outfit with a disowned piece.
     "fade": show them dimmed, marked "no longer owned".
     "hide": leave them out. */
  disowned: {
    outfitPage: "fade",   // the pieces on an outfit's page
    outfitCard: "fade",   // the photo strip on outfit cards
    sets: "fade",         // "Part of a set" on a garment's page
    pairedWith: "hide",   // "Often paired with" on a garment's page
  },
};
