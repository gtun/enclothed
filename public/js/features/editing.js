/* Inline editing on the garment page: opening the right editor and saving changes. */
"use strict";

let saving = false;
async function save(g, changes){
  if (saving) return;
  saving = true;
  try {
    const updated = await api(`/api/garments/${g.id}`, {method: "PATCH", body: changes});
    const i = G.findIndex(x => x.id === g.id);
    G[i] = updated;
    O.forEach(o => o.garments.forEach(x => { if (x.garment.id === g.id) x.garment = updated; }));
    reindex();
    toast("Saved");
  } catch (e) {
    toast(e.message, true);
  } finally {
    saving = false;
    refresh();
  }
}
const colorOptions = () => OPT.colors.map(c => ({value: c.name, label: c.name, hex: c.hex}));
const NONE = {value: null, label: "— none"};

function openEditor(field){
  const g = currentGarment(); if (!g) return;
  const host = document.querySelector(`[data-field="${field}"]`); if (!host) return;
  const f = FIELDS.find(x => x.key === field);
  const cancel = () => refresh();
  const setOne = v => { if (v === g[field]) return refresh(); save(g, {[field]: v}); };

  if (field === "category"){
    combo(host, {options: OPT.categories.map(c => ({value: c, label: c})), current: g.category, onCancel: cancel,
      onPick: v => {
        if (v === g.category) return refresh();
        const sub = document.querySelector('[data-field="subcategory"]');
        host.innerHTML = `<span class="cchip">${esc(v)}</span><div class="hintline">Now pick a ${esc(v)} subcategory to save</div>`;
        subcategoryEditor(sub, g, v);
      }});
  } else if (field === "subcategory"){
    subcategoryEditor(host, g, g.category);
  } else if (f && f.kind === "color"){
    combo(host, {options: colorOptions(), current: g[field], onCancel: cancel, onPick: setOne});
  } else if (f && f.kind === "colors"){
    multiEditor(host, g, field, colorOptions(), false);
  } else if (f && (f.kind === "level" || f.kind === "choice")){
    const opts = f.list().map(l => ({value: l.value, label: f.kind === "level" ? `${l.value} · ${l.label}` : l.label}));
    combo(host, {options: [...opts, NONE], current: g[field], onCancel: cancel, onPick: setOne});
  } else if (f && f.kind === "text"){
    combo(host, {options: f.suggest().map(v => ({value: v, label: v})), current: g[field], free: true, placeholder: "Type a value…", onCancel: cancel, onPick: setOne});
  } else if (field === "materials"){
    materialsEditor(host, g);
  } else if (field === "style_tags"){
    multiEditor(host, g, field, unique(G.flatMap(x => x.style_tags)).map(t => ({value: t, label: t})), true);
  } else if (field === "notes" || field === "label_text"){
    textEditor(host, g, field);
  }
}
function subcategoryEditor(host, g, category){
  const opts = (OPT.subcategories[category] || []).map(s => ({value: s, label: s}));
  combo(host, {options: opts, current: category === g.category ? g.subcategory : null, placeholder: `Type to filter ${category} subcategories…`,
    onCancel: () => refresh(),
    onPick: v => {
      if (category === g.category && v === g.subcategory) return refresh();
      save(g, category === g.category ? {subcategory: v} : {category, subcategory: v});
    }});
}
function multiEditor(host, g, field, options, free){
  const values = g[field].slice();
  const isColor = field !== "style_tags";
  host.innerHTML = `<div class="multi"><div class="have">${values.map((v, i) => `<span class="pill">${isColor ? `<span class="chip" style="background:${hex(v)}"></span>` : ""}${esc(v)}<button type="button" data-rm="${i}" aria-label="Remove ${esc(v)}">×</button></span>`).join("") || `<span class="empty">None yet</span>`}</div>
    <div class="btns"><button type="button" class="btn done-btn">Done</button><span class="hintline">Changes save as you go</span></div>
    <div class="adder"></div></div>`;
  host.querySelector(".have").addEventListener("click", e => {
    const b = e.target.closest("[data-rm]"); if (!b) return;
    const next = values.filter((_, i) => i !== +b.dataset.rm);
    save(g, {[field]: next}).then(() => openEditor(field));
  });
  host.querySelector(".done-btn").addEventListener("click", () => refresh());
  combo(host.querySelector(".adder"), {options: options.filter(o => !values.includes(o.value)), free, keepOpen: true, onCancel: () => refresh(),
    placeholder: isColor ? "Add a color…" : "Add a tag…",
    onPick: v => { if (v === null || values.includes(v)) return; save(g, {[field]: [...values, v]}).then(() => openEditor(field)); }});
  host.addEventListener("keydown", e => { if (e.key === "Escape") refresh(); });
}
function textEditor(host, g, field){
  host.innerHTML = `<textarea class="txt" rows="${field === "label_text" ? 5 : 3}" spellcheck="${field === "notes"}">${esc(g[field] || "")}</textarea>
    <div class="btns" style="margin-top:8px"><button type="button" class="btn primary" data-act="save">Save</button><button type="button" class="btn quiet" data-act="cancel">Cancel</button><span class="hintline">Ctrl+Enter to save · Esc to cancel</span></div>`;
  const ta = host.querySelector("textarea");
  const commit = () => { const v = ta.value.trim() || null; if (v === (g[field] || null)) return refresh(); save(g, {[field]: v}); };
  host.querySelector('[data-act="save"]').onclick = commit;
  host.querySelector('[data-act="cancel"]').onclick = () => refresh();
  ta.addEventListener("keydown", e => {
    if (e.key === "Escape"){ e.preventDefault(); refresh(); }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)){ e.preventDefault(); commit(); }
  });
  ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
}
function materialsEditor(host, g){
  let parts = JSON.parse(JSON.stringify(g.materials));
  const fibers = unique(G.flatMap(x => x.materials.flatMap(m => m.fibers.map(f => f.fiber))));
  const partNames = unique(G.flatMap(x => x.materials.map(m => m.part)));
  const listId = "fibers-" + g.id, partId = "parts-" + g.id;
  function draw(){
    host.innerHTML = `<div class="mats">
      <datalist id="${listId}">${fibers.map(f => `<option value="${esc(f)}">`).join("")}</datalist>
      <datalist id="${partId}">${partNames.map(f => `<option value="${esc(f)}">`).join("")}</datalist>
      ${parts.map((m, pi) => { const sum = m.fibers.reduce((n, f) => n + (+f.percent || 0), 0); return `<div class="mpart">
        <div class="top"><input class="txt" list="${partId}" data-p="${pi}" data-k="part" value="${esc(m.part || "")}" placeholder="Part (optional, e.g. shell, lining)" aria-label="Part name">
          ${parts.length > 1 ? `<button type="button" class="x" data-rmpart="${pi}" aria-label="Remove this part">×</button>` : ""}</div>
        ${m.fibers.map((f, fi) => `<div class="frow"><input class="txt" list="${listId}" data-p="${pi}" data-f="${fi}" data-k="fiber" value="${esc(f.fiber)}" placeholder="Fiber" aria-label="Fiber">
          <span class="pct"><input class="num" type="number" min="1" max="100" step="1" data-p="${pi}" data-f="${fi}" data-k="percent" value="${f.percent}" aria-label="Percent"></span>
          <button type="button" class="x" data-rmfiber="${pi}:${fi}" aria-label="Remove this fiber">×</button></div>`).join("")}
        <div class="btns"><button type="button" class="btn quiet" data-addfiber="${pi}">+ Fiber</button><span class="msum${sum === 100 ? "" : " off"}">total ${sum}%</span></div>
      </div>`; }).join("")}
      <div class="btns"><button type="button" class="btn quiet" data-addpart>+ Part</button></div>
      <div class="btns"><button type="button" class="btn primary" data-act="save">Save materials</button><button type="button" class="btn quiet" data-act="cancel">Cancel</button><span class="hintline" id="materr"></span></div>
    </div>`;
  }
  draw();
  host.addEventListener("input", e => {
    const el = e.target; if (!el.dataset.k) return;
    const m = parts[+el.dataset.p];
    if (el.dataset.k === "part") m.part = el.value;
    else if (el.dataset.k === "fiber") m.fibers[+el.dataset.f].fiber = el.value;
    else if (el.dataset.k === "percent"){ m.fibers[+el.dataset.f].percent = el.value === "" ? "" : +el.value;
      const sum = m.fibers.reduce((n, f) => n + (+f.percent || 0), 0);
      const s = el.closest(".mpart").querySelector(".msum"); s.textContent = `total ${sum}%`; s.classList.toggle("off", sum !== 100); }
  });
  host.addEventListener("click", e => {
    const t = e.target.closest("button"); if (!t) return;
    if (t.dataset.addfiber !== undefined){ parts[+t.dataset.addfiber].fibers.push({fiber: "", percent: ""}); draw(); focusLast(+t.dataset.addfiber); }
    else if (t.dataset.rmfiber){ const [p, f] = t.dataset.rmfiber.split(":").map(Number); parts[p].fibers.splice(f, 1); draw(); }
    else if (t.dataset.rmpart !== undefined){ parts.splice(+t.dataset.rmpart, 1); draw(); }
    else if (t.dataset.addpart !== undefined){ parts.push({part: "", fibers: [{fiber: "", percent: ""}]}); draw(); focusLast(parts.length - 1); }
    else if (t.dataset.act === "cancel") refresh();
    else if (t.dataset.act === "save"){
      const err = host.querySelector("#materr");
      const clean = parts.map(m => ({part: (m.part || "").trim() || null, fibers: m.fibers.filter(f => String(f.fiber).trim() || f.percent !== "")
        .map(f => ({fiber: String(f.fiber).trim(), percent: f.percent === "" ? NaN : Number(f.percent)}))})).filter(m => m.fibers.length);
      const bad = clean.flatMap(m => m.fibers).find(f => !f.fiber || !Number.isInteger(f.percent) || f.percent < 1 || f.percent > 100);
      if (bad){ err.textContent = "Each fiber needs a name and a whole-number percent from 1 to 100."; err.classList.add("err"); return; }
      save(g, {materials: clean});
    }
  });
  host.addEventListener("keydown", e => { if (e.key === "Escape") refresh(); });
  function focusLast(pi){ const els = host.querySelectorAll(`[data-p="${pi}"][data-k="fiber"]`); (els[els.length - 1] || host.querySelector(`[data-p="${pi}"]`))?.focus(); }
  host.querySelector("input")?.focus();
}
