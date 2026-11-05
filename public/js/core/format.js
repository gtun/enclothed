/* Small helpers for turning data into text and HTML: escaping, plurals, dates (see settings.js), icons. */
"use strict";

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const hex = c => HEX[c] || "#999999";
/* Drop punctuation that ends the sentence rather than the address, and a closing bracket with no opening one. */
function trimUrl(url){
  for (;;){
    const t = url.replace(/[.,;:!?'"”’]+$/, ""), last = t.slice(-1), open = {")": "(", "]": "[", "}": "{"}[last];
    if (!open || t.split(last).length <= t.split(open).length) return t;
    url = t.slice(0, -1);
  }
}
/* Text as safe HTML, with http(s):// and www. addresses as links that open in a new tab. */
function linkify(text){
  const s = String(text ?? "");
  let html = "", at = 0;
  for (const m of s.matchAll(/\b(?:https?:\/\/|www\.)[^\s<>"]+/gi)){
    const url = trimUrl(m[0]), href = /^www\./i.test(url) ? `https://${url}` : url;
    html += `${esc(s.slice(at, m.index))}<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>`;
    at = m.index + url.length;
  }
  return html + esc(s.slice(at));
}
const pips = (n, max) => `<span class="pips">${Array.from({length:max},(_,i)=>`<i class="${i<n?'on':''}"></i>`).join("")}</span>`;
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
/* Date formats are set in settings.js. A timestamp from the server is UTC; it's shown in your local time.
   A plain day like "2026-11-01" (a garment's date added) is read as that local day, not shifted by time zone. */
const formatWith = (date, fmt) => typeof fmt === "function" ? fmt(date) : date.toLocaleString(SETTINGS.locale, fmt);
const asDate = value => /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(...value.split("-").map((n, i) => i === 1 ? n - 1 : +n)) : new Date(value);
const when = ts => formatWith(asDate(ts), SETTINGS.dates.short);
const whenLong = ts => formatWith(asDate(ts), SETTINGS.dates.long);
const whenDay = day => day ? formatWith(asDate(day), SETTINGS.dates.day) : "—";
const catRank = g => { const i = RAIL_ORDER.indexOf(g?.category); return i < 0 ? 99 : i; };
const setName = s => s ? (s.name || `Set #${s.id}`) : "";
/* Fixed terms are English in the data; these are what a person sees. The names come from /api/options. */
const categoryName = c => OPT.category_labels[c] ?? c;
const subcategoryName = s => OPT.subcategory_labels[s] ?? s;
const colorName = c => OPT.color_labels[c] ?? c;
const title = g => [g.brand, subcategoryName(g.subcategory)].filter(Boolean).join(" ");
const warmthShort = label => label.split(/[,，、]/)[0];   // "light, 18–25°C" → "light"
const levelLabel = (list, v) => (list.find(l => l.value === v) || {}).label || "";
const choiceLabel = (list, v) => (list.find(l => l.value === v) || {}).label || v;
const unique = arr => [...new Set(arr.filter(Boolean))].sort((a, b) => a.localeCompare(b));
const SET_ICON = `<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><rect x="1.5" y="4.5" width="8" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="6.5" y="1.5" width="8" height="10" rx="1.5" fill="var(--surface)" stroke="currentColor" stroke-width="1.4"/></svg>`;
const PEN = `<svg class="pen" viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M11.3 2.3a1.6 1.6 0 0 1 2.3 2.3L5.4 12.8l-3 .8.8-3z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
const THUMB_UP = `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 7v7H2.5V7zM5 7l3-5c1.2 0 1.8.8 1.6 2L9.2 6.5h3.6c.9 0 1.5.8 1.3 1.6l-1.2 4.9c-.2.6-.7 1-1.3 1H5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
const THUMB_DOWN = `<svg viewBox="0 0 16 16" aria-hidden="true" style="transform:rotate(180deg)"><path d="M5 7v7H2.5V7zM5 7l3-5c1.2 0 1.8.8 1.6 2L9.2 6.5h3.6c.9 0 1.5.8 1.3 1.6l-1.2 4.9c-.2.6-.7 1-1.3 1H5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>`;

const photoName = url => decodeURIComponent(url.split("/").pop()).replace(/\.\w+$/, "");
const mainPhoto = g => g.photos.length ? g.photos[0].url : null;
const thumb = g => g.photos.length ? g.photos[0].thumb_url : null;
