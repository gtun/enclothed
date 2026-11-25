/* TEMPLATE: the type-to-filter dropdown (features/combo.js): the box, and the list it shows as you type. */
"use strict";

const comboBox = (id, collapsed, placeholder) => `<div class="cb${collapsed ? " inline" : ""}"><input type="text" role="combobox" aria-expanded="true" aria-controls="${id}" aria-autocomplete="list" autocomplete="off" spellcheck="false" placeholder="${esc(placeholder)}">
    <span class="caret" aria-hidden="true">▾</span><div class="pop"><ul role="listbox" id="${id}"></ul><div class="hintline"></div></div></div>`;

/* shown are the options that match; active is the highlighted row, where the "Use …" row counts as shown.length.
   freeText is what was typed, when it can be used as it is; that row goes first. */
function comboList(id, shown, active, current, freeText){
  let html = shown.map((o, i) => `<li role="option" id="${id}-${i}" data-i="${i}" aria-selected="${i === active}" class="${o.value === current ? "cur" : ""}">${o.hex ? `<span class="chip" style="background:${o.hex}"></span>` : ""}${esc(o.label)}</li>`).join("");
  if (freeText !== null) html = `<li role="option" id="${id}-free" data-free="1" class="free" aria-selected="${active === shown.length}">Use <b>“${esc(freeText)}”</b></li>` + html;
  return html || `<li class="nomatch" aria-disabled="true">No match. Clear the box to see every option.</li>`;
}

function comboHint(keepOpen, free){
  if (keepOpen) return free ? "Enter to add · Esc when done" : "Pick to add · Esc when done";
  return free ? "Enter to save · Esc to cancel" : "Pick from the list · Esc to cancel";
}
const COMBO_REJECT = "Not one of the options. Pick one from the list.";
