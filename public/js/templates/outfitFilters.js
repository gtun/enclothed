/* TEMPLATE: the filter box on the outfits page. */
"use strict";

function filterPanel(){
  const chip = (kind, l, label, full) => `<button type="button" data-ofilt-${kind}="${l.value}" aria-pressed="${ofilt[kind === "f" ? "formality" : "warmth"].includes(l.value)}" title="${esc(full)}">${esc(label)}</button>`;
  const n = activeFilterCount();
  const toggle = `<button type="button" class="btn ofilter-toggle" data-ofilt-toggle aria-expanded="${filtersOpen}" aria-controls="ofilters">Filters${n ? ` <span class="count">${n} on</span>` : ""} <span class="caret" aria-hidden="true">▾</span></button>`;
  if (!filtersOpen) return toggle + (n ? ` <button type="button" class="btn quiet" data-ofilt-clear>Clear filters</button>` : "");
  return toggle + `<div class="ofilters" id="ofilters" role="search" aria-label="Filter outfits">
    <div class="field"><label for="of-q">Request contains</label><input id="of-q" class="txt" type="search" data-ofilt="q" value="${esc(ofilt.q)}" placeholder="e.g. dinner" autocomplete="off"></div>
    <div class="field"><label for="of-from">From</label><input id="of-from" class="txt" type="date" data-ofilt="from" value="${esc(ofilt.from)}" max="${esc(ofilt.to)}"></div>
    <div class="field"><label for="of-to">To</label><input id="of-to" class="txt" type="date" data-ofilt="to" value="${esc(ofilt.to)}" min="${esc(ofilt.from)}"></div>
    <div class="field wide"><span class="flabel">Formality <em>(of the least formal piece)</em></span><div class="filters">${OPT.formality.map(l => chip("f", l, l.label, `${l.value} · ${l.label}`)).join("")}</div></div>
    <div class="field wide"><span class="flabel">Warmth <em>(of the warmest top layer)</em></span><div class="filters">${OPT.warmth.map(l => chip("w", l, l.label.split(",")[0], `${l.value} · ${l.label}`)).join("")}</div></div>
    ${filtersActive() ? `<button type="button" class="btn quiet" data-ofilt-clear>Clear filters</button>` : ""}
  </div>`;
}
