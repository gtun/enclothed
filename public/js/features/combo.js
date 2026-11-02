/* The type-to-filter dropdown used for editing and for adding pieces. */
"use strict";

/* ================= combobox =================
   A text box with a filtered list. Enforced (default): only a listed option can be picked.
   Free: anything typed is accepted, and the list offers suggestions. */
let comboSeq = 0;
function combo(host, {options, current, free = false, placeholder = "Type to filter…", onPick, onCancel, keepOpen = false, autofocus = true, collapsed = false}){
  const id = "cb" + (++comboSeq);
  host.innerHTML = `<div class="cb${keepOpen ? " inline" : ""}"><input type="text" role="combobox" aria-expanded="true" aria-controls="${id}" aria-autocomplete="list" autocomplete="off" spellcheck="false" placeholder="${esc(placeholder)}">
    <span class="caret" aria-hidden="true">▾</span><ul role="listbox" id="${id}"></ul></div>
    <div class="hintline">${free ? "Enter to save · Esc to cancel" : "Pick from the list · Esc to cancel"}</div>`;
  const wrap = host.querySelector(".cb"), input = wrap.querySelector("input"), list = wrap.querySelector("ul"), hint = host.querySelector(".hintline");
  const curOpt = options.find(o => o.value === current);
  input.value = curOpt ? curOpt.label : (free && current ? String(current) : "");
  let typed = false, active = -1, shown = [], done = false, opened = !collapsed;
  const norm = s => String(s).toLowerCase().trim();
  function render(){
    if (!opened){ list.hidden = true; hint.hidden = true; input.setAttribute("aria-expanded", "false"); return; }
    list.hidden = false; hint.hidden = false; input.setAttribute("aria-expanded", "true");
    const q = typed ? norm(input.value) : "";
    shown = q ? options.filter(o => norm(o.label).includes(q) || norm(o.value ?? "").includes(q)) : options.slice();
    const exact = free && q && options.some(o => norm(o.label) === q);
    let html = shown.map((o, i) => `<li role="option" id="${id}-${i}" data-i="${i}" aria-selected="${i === active}" class="${o.value === current ? "cur" : ""}">${o.hex ? `<span class="chip" style="background:${o.hex}"></span>` : ""}${esc(o.label)}</li>`).join("");
    if (free && q && !exact) html = `<li role="option" id="${id}-free" data-free="1" class="free" aria-selected="${active === shown.length}">Use <b>“${esc(input.value.trim())}”</b></li>` + html;
    if (!html) html = `<li class="nomatch" aria-disabled="true">No match. Clear the box to see every option.</li>`;
    list.innerHTML = html;
    const el = active >= 0 ? list.querySelector(`[aria-selected="true"]`) : null;
    if (el){ input.setAttribute("aria-activedescendant", el.id); el.scrollIntoView({block:"nearest"}); } else input.removeAttribute("aria-activedescendant");
    wrap.classList.remove("invalid"); hint.classList.remove("err");
    hint.textContent = keepOpen ? (free ? "Enter to add · Esc when done" : "Pick to add · Esc when done") : free ? "Enter to save · Esc to cancel" : "Pick from the list · Esc to cancel";
  }
  const freeRowCount = () => (list.querySelector("[data-free]") ? 1 : 0);
  function pickIndex(i){ if (done) return; done = !keepOpen; const v = shown[i].value; if (keepOpen){ input.value = ""; typed = false; active = -1; if (collapsed) opened = false; render(); } onPick(v); }
  function pickFree(){ if (done) return; const v = input.value.trim(); done = !keepOpen; onPick(v === "" ? null : v); if (keepOpen){ input.value = ""; typed = false; render(); input.focus(); } }
  function cancel(){ if (done) return; done = true; onCancel && onCancel(); }
  function reject(){ wrap.classList.add("invalid"); hint.classList.add("err"); hint.textContent = "Not one of the options. Pick one from the list."; }
  function commitTyped(){
    const q = norm(input.value);
    if (!typed) return keepOpen ? null : cancel();
    const exactI = shown.findIndex(o => norm(o.label) === q || norm(o.value ?? "") === q);
    if (exactI >= 0) return pickIndex(exactI);
    if (free) return pickFree();
    if (shown.length === 1) return pickIndex(0);
    reject();
  }
  const collapse = () => { input.value = ""; typed = false; active = -1; opened = false; render(); };
  input.addEventListener("input", () => { typed = true; opened = true; active = norm(input.value) ? 0 : -1; render(); });
  input.addEventListener("keydown", e => {
    const total = shown.length + freeRowCount();
    if (e.key === "ArrowDown"){ e.preventDefault(); if (!opened){ opened = true; active = 0; render(); return; } active = Math.min(total - 1, active + 1); render(); }
    else if (e.key === "ArrowUp"){ e.preventDefault(); active = Math.max(0, active - 1); render(); }
    else if (e.key === "Enter"){ e.preventDefault();
      const sel = list.querySelector('[aria-selected="true"]');
      if (sel && sel.dataset.free) pickFree(); else if (sel && sel.dataset.i !== undefined) pickIndex(+sel.dataset.i); else commitTyped(); }
    else if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation();
      if (keepOpen){ if (collapsed && opened) collapse(); else onCancel && onCancel(); } else cancel(); }
    else if (e.key === "Tab" && !keepOpen){ if (typed) commitTyped(); else cancel(); }
  });
  list.addEventListener("mousedown", e => {
    const li = e.target.closest("li"); if (!li || li.classList.contains("nomatch")) return;
    e.preventDefault();
    if (li.dataset.free) pickFree(); else pickIndex(+li.dataset.i);
  });
  input.addEventListener("blur", () => setTimeout(() => {
    if (done || host.contains(document.activeElement)) return;
    if (keepOpen){ if (collapsed) collapse(); return; }
    if (!typed) return cancel();
    const q = norm(input.value);
    if (free) return pickFree();
    const exactI = shown.findIndex(o => norm(o.label) === q);
    if (exactI >= 0) pickIndex(exactI); else cancel();
  }, 120));
  render();
  if (autofocus){ input.focus(); input.select(); }
  return {input};
}
