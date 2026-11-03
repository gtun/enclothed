/* After a color edit: find the old color in the styling notes and offer to update it.
   Nothing changes without a yes, since a word like "gold" or "black tie" may not mean the garment's color. */
"use strict";

let notesChecks = [];   // waiting prompts, oldest first: {id, from, to}. to is null while a color is removed with no replacement yet.

const garmentColors = g => [g.primary_color, ...g.secondary_colors, ...g.accent_colors];

/* Whole-word matches of a color in text, either spelling of gray. A match inside a longer color
   doesn't count: "light gray" isn't a mention of gray, so those names are matched first and dropped. */
function colorMentions(text, color){
  const pattern = name => name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/gray/g, "gr[ae]y");
  const names = OPT.colors.map(c => c.name).filter(n => n.includes(color)).sort((a, b) => b.length - a.length);
  const re = new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.map(pattern).join("|")})(?![\\p{L}\\p{N}])`, "giu");
  return [...text.matchAll(re)].filter(m => m[0].toLowerCase().replace("grey", "gray") === color);
}
function highlightMentions(text, color){
  let html = "", at = 0;
  for (const m of colorMentions(text, color)){
    html += `${esc(text.slice(at, m.index))}<mark>${esc(m[0])}</mark>`;
    at = m.index + m[0].length;
  }
  return html + esc(text.slice(at));
}
/* Keep the look of the word being replaced: Black → Navy, BLACK → NAVY. */
const likeCase = (word, to) => word === word.toUpperCase() ? to.toUpperCase()
  : word[0] === word[0].toUpperCase() ? to[0].toUpperCase() + to.slice(1) : to;
function replaceMentions(text, from, to){
  let result = "", at = 0;
  for (const m of colorMentions(text, from)){
    result += text.slice(at, m.index) + likeCase(m[0], to);
    at = m.index + m[0].length;
  }
  return result + text.slice(at);
}

/* A color changed from one value to another (to = null: removed). Changing it again updates or cancels what's waiting. */
function flagColorChange(id, from, to){
  notesChecks = notesChecks.filter(c => !(c.id === id && (c.from === to || c.from === from)));
  const earlier = notesChecks.find(c => c.id === id && c.to === from);
  if (earlier) earlier.to = to;
  if (colorMentions(byId[id].styling_notes, from).length) notesChecks.push({id, from, to});
}
/* A color added right after one was removed is taken as its replacement. */
function pairReplacement(id, to){
  const waiting = notesChecks.findLast(c => c.id === id && !c.to);
  if (!waiting) return;
  if (waiting.from === to) notesChecks = notesChecks.filter(c => c !== waiting);
  else waiting.to = to;
}
/* The prompt to show for this garment. One whose mentions have since been edited away is dropped. */
function currentCheck(g){
  notesChecks = notesChecks.filter(c => c.id !== g.id || colorMentions(g.styling_notes, c.from).length);
  return notesChecks.find(c => c.id === g.id);
}
const focusNotesCheck = () => document.querySelector(".notecheck [data-nc]")?.focus({preventScroll: true});

function handleNotesCheckClick(e){
  const b = e.target.closest("[data-nc]"); if (!b) return false;
  const g = currentGarment(), c = g && currentCheck(g); if (!c) return true;
  notesChecks = notesChecks.filter(x => x !== c);
  if (b.dataset.nc === "yes"){
    save(g, {styling_notes: replaceMentions(g.styling_notes, c.from, c.to)}).then(focusNotesCheck);
  } else if (b.dataset.nc === "manual"){
    refresh();
    openEditor("styling_notes");
    const ta = document.querySelector('[data-field="styling_notes"] textarea');
    const [first] = colorMentions(ta.value, c.from);
    ta.setSelectionRange(first.index, first.index + first[0].length);
    ta.scrollIntoView({block: "center"});
  } else {
    refresh();
    focusNotesCheck();
  }
  return true;
}
