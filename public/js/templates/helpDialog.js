/* TEMPLATE: the help for each page type (HELP: headings and tips) and the dialog that shows it. */
"use strict";

const HELP = {
  wardrobe: {title: "Your wardrobe", tips: [
    "<b>Add garment</b>: photograph the front, the back and every label. AI fills in the details.",
    "Open a garment to see its outfits or correct a detail.",
    "The buttons under the heading filter by category, by sets, or by pieces not in any outfit yet. Grid, Large and List change the view.",
    "Use the <b>+</b> on a garment, or <b>Put together an outfit</b>, to start an outfit around pieces you choose.",
  ]},
  garment: {title: "A garment", tips: [
    "<b>Click any value</b> under Details to correct it. Good details mean better outfits.",
    "Styling notes are what the AI reads when it suggests outfits. Your own notes stay private and are never sent to it.",
    "<b>+ Add to outfit</b> puts this piece in the outfit builder.",
    "<b>I no longer own this</b> takes it out of your wardrobe but keeps it in your outfit history. You can add it back later.",
  ]},
  outfits: {title: "Your outfits", tips: [
    "<b>+ New outfit</b>: choose pieces, describe the occasion, or both. AI suggests outfits, or you can save your own.",
    "Outfits are grouped by what you asked for. The stripe shows each piece's main color, outer layer down to shoes.",
    "<b>Filters</b> search by request, date, formality and warmth.",
    "Outfits you dislike are hidden until you choose <b>Show disliked</b>.",
  ]},
  outfit: {title: "An outfit", tips: [
    "The top explains why the outfit works. Below it, each piece has its own styling advice.",
    "<b>Like</b> or <b>Dislike</b> it, and click again to clear your rating. Disliked outfits are hidden from your list.",
    "<b>Prev</b> and <b>Next</b> appear when there are other options for the same request.",
    "Open a piece to see that garment.",
  ]},
  results: {title: "New suggestions", tips: [
    "These are the outfits you just asked for, newest first, and they're already saved under Outfits.",
    "Open one to see the details and like or dislike it.",
    "<b>Change pieces or details and try again</b> takes you back to the outfit builder. New suggestions use AI each time.",
    "<b>Done</b> finishes this request.",
  ]},
  disowned: {title: "Disowned", tips: [
    "This is everything you no longer own, kept so your outfit history stays complete.",
    "<b>Garments</b> lists those pieces. <b>Outfits</b> lists outfits that include one.",
    "These won't be suggested in new outfits.",
    "To bring a piece back, open it and choose <b>Add this to my wardrobe again</b>.",
  ]},
  style: {title: "Your style", tips: [
    "Describe your tastes and needs in your own words. They're included with every outfit request.",
    "Words like <b>always</b>, <b>never</b> and <b>must</b> make something a rule. Everything else is a default that a specific request can override.",
    "<b>Save as written</b> keeps your words. <b>Improve with AI</b> shows a tidier version to compare, and that button uses AI.",
  ]},
  usage: {title: "Usage", tips: [
    "This page estimates what your AI calls cost: adding a garment, getting outfit suggestions, and Improve with AI.",
    "Choose a date range. The chart shows the estimated cost per day, split by type of call.",
    "These are estimates from token counts, not a bill.",
    "Only you and the site's admin can see your usage. The admin sees totals and costs, not your prompts.",
  ]},
};

function helpDialog(topic, firstVisit){
  const help = HELP[topic];
  return `<div class="dialog small" role="dialog" aria-modal="true" aria-labelledby="h-title">
    <div class="bhead"><h2 id="h-title">${esc(help.title)}</h2></div>
    <div class="bbody"><ul class="tips">${help.tips.map(t => `<li>${t}</li>`).join("")}</ul>
      ${firstVisit ? `<p class="bhint">To see this again, use the <b>?</b> at the top of the page.</p>` : ""}</div>
    <div class="bfoot"><button type="button" class="btn primary wide" data-h-close>Got it</button></div>
  </div>`;
}
