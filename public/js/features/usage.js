/* The Usage page: loads calls for the chosen range and handles its clicks and the chart's tooltip. Its markup is in templates/usagePage.js. */
"use strict";

let usage = {admin: false, range: "30", calls: null, users: null, person: null, error: "", days: {}};
let usageRequest = 0;   // the latest load, so a slow answer for an old range is ignored

function usageStart(range){
  const now = new Date();
  if (range === "all") return null;
  if (range === "month") return new Date(now.getFullYear(), now.getMonth(), 1);
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - (+range - 1));
}
/* One entry per local day from the start of the range (or the first call) through today, including quiet days. */
function usageDays(calls){
  const first = usageStart(usage.range) || new Date(calls[0].timestamp);
  const byDay = {};
  calls.forEach(c => {
    const d = byDay[localDay(new Date(c.timestamp))] ||= {calls: 0, total: 0, tagging: 0, outfits: 0, style: 0, insights: 0, weigh: 0};
    d.calls++; d.total += c.cost_usd || 0; d[c.kind] += c.cost_usd || 0;
  });
  const days = [], today = localDay(Date.now());
  for (let i = 0; ; i++){
    const day = localDay(new Date(first.getFullYear(), first.getMonth(), first.getDate() + i));
    days.push({day, calls: 0, total: 0, tagging: 0, outfits: 0, style: 0, insights: 0, weigh: 0, ...byDay[day]});
    if (day >= today) break;
  }
  usage.days = Object.fromEntries(days.map(d => [d.day, d]));
  return days;
}
async function loadUsage(){
  const id = ++usageRequest, start = usageStart(usage.range);
  const query = start ? `?from=${encodeURIComponent(start.toISOString())}` : "";
  try {
    const data = await api((usage.admin ? "/api/usage/all" : "/api/usage") + query);
    if (id !== usageRequest) return;
    usage.calls = usage.admin ? data.calls : data;
    usage.users = usage.admin ? data.users : null;
    usage.error = "";
  } catch (e) {
    if (id !== usageRequest) return;
    usage.error = e.message;
  }
  if (current === "usage") refresh();
}
function handleUsageClick(e){
  const range = e.target.closest("[data-usage-range]");
  if (range){ usage.range = range.dataset.usageRange; usage.calls = null; refresh(); loadUsage(); return true; }
  const person = e.target.closest("[data-usage-person]");
  if (person){ const id = person.dataset.usagePerson ? +person.dataset.usagePerson : null;
    usage.person = usage.person === id ? null : id; refresh(); return true; }
  return false;
}
function showUsageTip(target){
  const tip = document.getElementById("utip"), d = usage.days[target.dataset.usageDay];
  if (!tip || !d) return;
  const row = (label, value, kind) => { const line = document.createElement("div");
    if (kind){ const key = document.createElement("i"); key.className = `ukey-${kind}`; line.append(key); }
    const b = document.createElement("b"); b.textContent = value; line.append(b, ` ${label}`); return line; };
  tip.replaceChildren(row(whenDay(d.day), usd(d.total)),
    ...USAGE_KINDS.filter(([k]) => d[k] > 0).map(([k, label]) => row(label, usd(d[k]), k)), row(d.calls === 1 ? "call" : "calls", String(d.calls)));
  tip.hidden = false;
  const box = tip.parentElement.getBoundingClientRect(), hit = target.getBoundingClientRect();
  const x = hit.left - box.left + hit.width / 2;
  tip.style.left = `${Math.max(0, Math.min(x - tip.offsetWidth / 2, box.width - tip.offsetWidth))}px`;
}
const hideUsageTip = () => { const tip = document.getElementById("utip"); if (tip) tip.hidden = true; };
for (const type of ["pointerover", "focusin"]) document.addEventListener(type, e => {
  const hit = e.target.closest?.("[data-usage-day]");
  if (hit) showUsageTip(hit); else hideUsageTip();
});
