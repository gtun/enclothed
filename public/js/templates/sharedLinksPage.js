/* TEMPLATE: the Shared links page (your live share links, each with its label, dates and a copy button). */
"use strict";

const SHARE_KIND_LABEL = {garment: "Garment", outfit: "Outfit"};

/* "in 3 days", "5 hours ago": in the page's language, from the browser's own translations. */
function relativeTime(ts){
  const seconds = (new Date(ts) - Date.now()) / 1000;
  const [value, unit] = Math.abs(seconds) >= 86400 ? [seconds / 86400, "day"]
    : Math.abs(seconds) >= 3600 ? [seconds / 3600, "hour"] : [seconds / 60, "minute"];
  return new Intl.RelativeTimeFormat(SETTINGS.locale, {numeric: "auto"}).format(Math.round(value), unit);
}
const bothTimes = (label, ts) => `<div class="slwhen"><small>${esc(label)}</small><b>${esc(relativeTime(ts))}</b><small>${esc(whenLong(ts))}</small></div>`;
/* The page builds the label so fixed terms are translated: an outfit's name, or a garment's brand and subcategory. */
const shareLabel = row => row.kind === "outfit" ? row.aesthetic || "Outfit" : title(row) || "Garment";

function sharedLinkRow(row){
  const confirming = sharedLinks.confirm === row.token, busy = sharedLinks.busy === row.token;
  const t = esc(row.token);
  const actions = confirming
    ? `<div class="slconfirm"><p class="dnote">Revoke this link? It stops working right away for everyone who has it.</p>
         <div class="hero-actions"><button type="button" class="btn primary" data-revoke-yes="${t}" ${busy ? "disabled" : ""}>Yes, revoke it</button><button type="button" class="btn" data-revoke-no ${busy ? "disabled" : ""}>Keep it</button></div></div>`
    : `<div class="slbtns"><button type="button" class="btn" data-copy-share="${esc(row.path)}">Copy link</button><button type="button" class="btn quiet" data-revoke="${t}">Revoke</button></div>`;
  return `<li class="slrow">
    <div class="slwhat"><a href="${esc(row.path)}" target="_blank" rel="noopener">${esc(shareLabel(row))}</a><small>${esc(SHARE_KIND_LABEL[row.kind])}</small></div>
    ${bothTimes("Created", row.created_at)}${bothTimes("Expires", row.expires_at)}
    ${actions}</li>`;
}

function sharedLinksPage(){
  const intro = sharedLinks.demo
    ? "Links made in the demo that still work. Everyone in the demo shares this list."
    : "Links you've made that still work. Anyone with a link can open it until it expires.";
  const hero = `<header class="hero"><div><h1>Shared links</h1><p class="sub">${esc(intro)}</p></div></header>`;
  if (sharedLinks.error) return hero + `<p class="empty">${esc(sharedLinks.error)}</p>`;
  if (!sharedLinks.rows) return hero + `<div class="busy" role="status"><span class="spin" aria-hidden="true"></span>Loading…</div>`;
  if (!sharedLinks.rows.length) return hero + `<p class="empty">No live links. Use <b>Share</b> on a garment or outfit page to make one.</p>`;
  return `${hero}<main class="usage"><section class="panel"><ul class="sllist" aria-label="Shared links">${sharedLinks.rows.map(sharedLinkRow).join("")}</ul></section></main>`;
}
