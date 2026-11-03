/* The type-to-filter dropdown used for editing and for adding pieces. */
"use strict";

/* ================= combobox =================
   A text box with a filtered list. Enforced (default): only a listed option can be picked.
   Free: anything typed is accepted, and the list offers suggestions.
   keepOpen stays open after a pick, for adding several. scope is the area that counts as inside it:
   a click or Tab outside closes it, as do Esc and Enter on an empty box. */
let comboSeq = 0;
function combo(host, {options, current, free = false, placeholder = "Type to filter…", onPick, onCancel, keepOpen = false, autofocus = true, collapsed = false, scope = host}){
  const id = "cb" + (++comboSeq);
  host.innerHTML = `<div class="cb${collapsed ? " inline" : ""}"><input type="text" role="combobox" aria-expanded="true" aria-controls="${id}" aria-autocomplete="list" autocomplete="off" spellcheck="false" placeholder="${esc(placeholder)}">
    <span class="caret" aria-hidden="true">▾</span><div class="pop"><ul role="listbox" id="${id}"></ul><div class="hintline"></div></div></div>`;
  const wrap = host.querySelector(".cb"), input = wrap.querySelector("input"), pop = wrap.querySelector(".pop"), list = wrap.querySelector("ul"), hint = wrap.querySelector(".hintline");
  const curOpt = options.find(o => o.value === current);
  input.value = curOpt ? curOpt.label : (free && current ? String(current) : "");
  let typed = false, active = -1, shown = [], done = false, opened = !collapsed;
  const norm = s => String(s).toLowerCase().trim();
  function render(){
    if (!opened){ pop.hidden = true; input.setAttribute("aria-expanded", "false"); return; }
    pop.hidden = false; input.setAttribute("aria-expanded", "true");
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
    if (!q && keepOpen) return dismiss();
    if (!typed) return cancel();
    if (!q) return free && current ? pickFree() : cancel();   // emptying a free field that has a value clears it
    const exactI = shown.findIndex(o => norm(o.label) === q || norm(o.value ?? "") === q);
    if (exactI >= 0) return pickIndex(exactI);
    if (free) return pickFree();
    if (shown.length === 1) return pickIndex(0);
    reject();
  }
  const collapse = () => { input.value = ""; typed = false; active = -1; opened = false; render(); };
  const dismiss = () => { if (collapsed && opened) collapse(); else onCancel && onCancel(); };
  function leave(){
    if (keepOpen) return dismiss();
    if (done) return;
    if (!typed) return cancel();
    if (free) return pickFree();
    const q = norm(input.value), exactI = shown.findIndex(o => norm(o.label) === q);
    if (exactI >= 0) pickIndex(exactI); else cancel();
  }
  input.addEventListener("input", () => { typed = true; opened = true; active = norm(input.value) ? 0 : -1; render(); });
  input.addEventListener("keydown", e => {
    const total = shown.length + freeRowCount();
    if (e.key === "ArrowDown"){ e.preventDefault(); if (!opened){ opened = true; active = 0; render(); return; } active = Math.min(total - 1, active + 1); render(); }
    else if (e.key === "ArrowUp"){ e.preventDefault(); active = Math.max(0, active - 1); render(); }
    else if (e.key === "Enter"){ e.preventDefault();
      const sel = list.querySelector('[aria-selected="true"]');
      if (sel && sel.dataset.free) pickFree(); else if (sel && sel.dataset.i !== undefined) pickIndex(+sel.dataset.i); else commitTyped(); }
    else if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation();
      if (keepOpen) dismiss(); else cancel(); }
    else if (e.key === "Tab" && !keepOpen){ if (typed) commitTyped(); else cancel(); }
  });
  pop.addEventListener("mousedown", e => {
    e.preventDefault();   // keep focus in the box
    const li = e.target.closest("li"); if (!li || li.classList.contains("nomatch")) return;
    if (li.dataset.free) pickFree(); else pickIndex(+li.dataset.i);
  });
  /* Closing on click (not mouse-down) lets the click still land, so clicking another field opens it in one go.
     A click only counts if it also started outside: a drag out of the box, or the click that opened this, doesn't. */
  let downOutside = false;
  const onDown = e => { if (!gone()) downOutside = !scope.contains(e.target); };
  const onClick = () => { if (gone() || !downOutside) return; downOutside = false; leave(); };
  const onFocus = e => { if (!gone() && !downOutside && !scope.contains(e.target)) leave(); };
  const onKey = e => { if (e.key === "Escape" && !gone()){ if (keepOpen) dismiss(); else cancel(); } };
  const listeners = [["pointerdown", onDown, true], ["click", onClick, true], ["focusin", onFocus, false], ["keydown", onKey, false]];
  function gone(){
    if (wrap.isConnected) return false;
    listeners.forEach(([type, fn, capture]) => document.removeEventListener(type, fn, capture));
    return true;
  }
  listeners.forEach(([type, fn, capture]) => document.addEventListener(type, fn, capture));
  render();
  if (autofocus){ input.focus(); input.select(); }
  return {input};
}
