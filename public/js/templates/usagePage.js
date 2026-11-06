/* TEMPLATE: the Usage page (totals, daily chart, breakdown, most expensive calls, and an admin's Everyone table). */
"use strict";

const USAGE_RANGES = [["7", "7 days"], ["30", "30 days"], ["month", "This month"], ["all", "All time"]];
const USAGE_KINDS = [["tagging", "Tagging"], ["outfits", "Outfits"], ["style", "Style"], ["insights", "Insights"]];
const USAGE_TOP_CALLS = 10;
const kindLabel = kind => USAGE_KINDS.find(([k]) => k === kind)[1];
const usd = n => n === null ? "no price" : `$${n.toFixed(n > 0 && n < 1 ? 3 : 2)}`;
const count = n => n.toLocaleString(SETTINGS.locale);
const callTokens = c => c.input_tokens + c.output_tokens + c.cache_write_tokens + c.cache_read_tokens;
function usageTotals(calls){
  const cost = calls.reduce((sum, c) => sum + (c.cost_usd || 0), 0);
  const tokens = calls.reduce((sum, c) => sum + callTokens(c), 0);
  const unpriced = calls.filter(c => c.cost_usd === null).length;
  return {calls: calls.length, tokens, cost, unpriced};
}
const usageTable = (head, rows, label) => `<div class="utable"><table aria-label="${esc(label)}"><thead><tr>${head.map(([text, cls]) => `<th scope="col"${cls ? ` class="${cls}"` : ""}>${esc(text)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;

function everyoneTable(){
  const rowOf = (id, name, calls) => {
    const t = usageTotals(calls), n = kind => calls.filter(c => c.kind === kind).length;
    const last = calls.length ? when(calls[calls.length - 1].timestamp) : "—";
    return `<tr><th scope="row"><button type="button" class="ulink" data-usage-person="${id ?? ""}" aria-pressed="${usage.person === id}">${esc(name)}</button></th>
      <td class="n">${t.calls}</td>${USAGE_KINDS.map(([k]) => `<td class="n opt">${n(k)}</td>`).join("")}<td class="n opt">${count(t.tokens)}</td><td class="n">${usd(t.cost)}</td><td class="n opt">${esc(last)}</td></tr>`;
  };
  const people = usage.users.map(u => ({...u, calls: usage.calls.filter(c => c.user_id === u.id)}))
    .sort((a, b) => usageTotals(b.calls).cost - usageTotals(a.calls).cost || a.username.localeCompare(b.username));
  const head = [["Person"], ["Calls", "n"], ...USAGE_KINDS.map(([, label]) => [label, "n opt"]), ["Tokens", "n opt"], ["Est. cost", "n"], ["Last used", "n opt"]];
  return `<section class="panel"><h4>Everyone <small>select a person to see only their usage</small></h4>
    ${usageTable(head, [rowOf(null, "Everyone", usage.calls), ...people.map(p => rowOf(p.id, p.username, p.calls))], "Usage by person")}</section>`;
}

/* A rounded rectangle along the top only, so a stack keeps one rounded end at its top. */
const roundTop = (x, y, w, h, r) => `M${x} ${y + h}V${y + r}Q${x} ${y} ${x + r} ${y}H${x + w - r}Q${x + w} ${y} ${x + w} ${y + r}V${y + h}Z`;
const niceMax = n => { const step = 10 ** Math.floor(Math.log10(n)); return [1, 2, 5, 10].map(m => m * step).find(v => v >= n); };
function usageChart(days){
  const W = Math.max(240, Math.min(app.clientWidth, 1148) - 30), H = 190;
  const left = 46, right = 4, top = 8, bottom = 22, plotW = W - left - right, plotH = H - top - bottom;
  const most = Math.max(...days.map(d => d.total));
  const yMax = most > 0 ? niceMax(most) : 1;
  const y = v => top + plotH - v / yMax * plotH;
  const slot = plotW / days.length, barW = Math.min(28, Math.max(1, slot - 2));
  const ticks = [0, yMax / 2, yMax].map(v => `<line class="ugrid" x1="${left}" x2="${W - right}" y1="${y(v)}" y2="${y(v)}"/><text class="uaxis" x="${left - 6}" y="${y(v) + 4}" text-anchor="end">$${v.toFixed(yMax < 0.1 ? 3 : 2)}</text>`).join("");
  const bars = days.map((d, i) => {
    const x = left + slot * i + (slot - barW) / 2;
    const parts = USAGE_KINDS.filter(([k]) => d[k] > 0);
    let base = top + plotH, marks = "";
    parts.forEach(([k], j) => {
      const h = Math.max(1.5, d[k] / yMax * plotH), end = j === parts.length - 1;
      const gap = end ? 0 : Math.min(2, h / 2);
      const r = end ? Math.min(4, barW / 2, h) : 0;
      marks += `<path class="useg-${k}" d="${roundTop(x, base - h + gap, barW, h - gap, r)}"/>`;
      base -= h;
    });
    const label = `${whenDay(d.day)}: ${usd(d.total)}`;
    return marks + `<rect class="uhit" x="${left + slot * i}" y="${top}" width="${slot}" height="${plotH}" data-usage-day="${d.day}" aria-label="${esc(label)}"${d.calls ? ` tabindex="0"` : ""}/>`;
  }).join("");
  const ends = days.length > 1 ? [[0, "start"], [days.length - 1, "end"]] : [[0, "middle"]];
  if (days.length >= 5) ends.splice(1, 0, [Math.floor((days.length - 1) / 2), "middle"]);
  const labels = ends.map(([i, anchor]) => { const c = left + slot * i + slot / 2;
    const x = anchor === "start" ? left : anchor === "end" ? W - right : c;
    return `<text class="uaxis" x="${x}" y="${H - 6}" text-anchor="${anchor}">${esc(when(days[i].day))}</text>`; }).join("");
  return `<div class="uchart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Estimated cost per day">${ticks}${bars}${labels}</svg><div class="utip" id="utip" hidden></div></div>`;
}
function dayTable(days){
  const rows = days.filter(d => d.calls).reverse().map(d => `<tr><th scope="row">${esc(whenDay(d.day))}</th><td class="n">${d.calls}</td>${USAGE_KINDS.map(([k]) => `<td class="n">${usd(d[k])}</td>`).join("")}<td class="n">${usd(d.total)}</td></tr>`);
  return usageTable([["Day"], ["Calls", "n"], ...USAGE_KINDS.map(([, label]) => [label, "n"]), ["Total", "n"]], rows, "Estimated cost per day");
}
function breakdownTable(calls){
  const groups = {};
  calls.forEach(c => { (groups[`${c.kind}|${c.model}`] ||= []).push(c); });
  const sum = (list, key) => list.reduce((n, c) => n + c[key], 0);
  const rows = Object.values(groups).sort((a, b) => usageTotals(b).cost - usageTotals(a).cost).map(list => {
    const priced = list.every(c => c.cost_usd !== null);
    return `<tr><th scope="row">${esc(kindLabel(list[0].kind))}</th><td class="opt">${esc(list[0].model)}</td><td class="n">${list.length}</td><td class="n opt">${count(sum(list, "input_tokens"))}</td><td class="n opt">${count(sum(list, "output_tokens"))}</td><td class="n opt">${count(sum(list, "cache_write_tokens"))}</td><td class="n opt">${count(sum(list, "cache_read_tokens"))}</td><td class="n">${usd(priced ? usageTotals(list).cost : null)}</td></tr>`; });
  const read = sum(calls, "cache_read_tokens"), allInput = sum(calls, "input_tokens") + sum(calls, "cache_write_tokens") + read;
  return usageTable([["Type"], ["Model", "opt"], ["Calls", "n"], ["Input", "n opt"], ["Output", "n opt"], ["Cache write", "n opt"], ["Cache read", "n opt"], ["Est. cost", "n"]], rows, "Usage by type and model")
    + (read ? `<p class="bhint">${Math.round(read / allInput * 100)}% of input tokens were read from the cache, the cheapest kind.</p>` : "");
}
function topCallsTable(calls){
  const showPerson = usage.users && usage.person === null;
  const name = id => (usage.users.find(u => u.id === id) || {}).username || `#${id}`;
  const rows = [...calls].sort((a, b) => (b.cost_usd ?? -1) - (a.cost_usd ?? -1)).slice(0, USAGE_TOP_CALLS).map(c =>
    `<tr><th scope="row"><span class="opt">${esc(whenLong(c.timestamp))}</span><span class="only-sm">${esc(when(c.timestamp))}</span></th>${showPerson ? `<td class="opt">${esc(name(c.user_id))}</td>` : ""}<td>${esc(kindLabel(c.kind))}</td><td class="opt">${esc(c.model)}</td><td class="n opt">${count(callTokens(c))}</td><td class="n">${usd(c.cost_usd)}</td></tr>`);
  return usageTable([["When"], ...(showPerson ? [["Person", "opt"]] : []), ["Type"], ["Model", "opt"], ["Tokens", "n opt"], ["Est. cost", "n"]], rows, "Most expensive calls");
}

function usagePage(){
  const pressed = key => `aria-pressed="${usage.range === key}"`;
  const ranges = `<div class="filters" role="toolbar" aria-label="Date range">${USAGE_RANGES.map(([key, label]) => `<button type="button" data-usage-range="${key}" ${pressed(key)}>${esc(label)}</button>`).join("")}</div>`;
  const hero = stats => `<header class="hero"><div><h1>Usage</h1><p class="sub">What your AI calls cost, estimated from their token counts. This isn't a bill.</p></div>${stats}</header>`;
  if (usage.error) return hero("") + ranges + `<p class="empty">${esc(usage.error)}</p>`;
  if (!usage.calls) return hero("") + ranges + `<div class="busy" role="status"><span class="spin" aria-hidden="true"></span>Loading…</div>`;
  const calls = usage.person === null ? usage.calls : usage.calls.filter(c => c.user_id === usage.person);
  const t = usageTotals(calls);
  const stats = `<div class="stats"><div><b>${usd(t.cost)}</b>estimated</div><div><b>${count(t.calls)}</b>${t.calls === 1 ? "call" : "calls"}</div><div><b>${count(t.tokens)}</b>tokens</div></div>`;
  const who = usage.person === null ? "" : `<p class="bhint">Showing ${esc((usage.users.find(u => u.id === usage.person) || {}).username)}.</p>`;
  const body = !calls.length ? `<p class="empty">No AI calls in this range.</p>` : (() => {
    const days = usageDays(calls);
    return `<section class="panel"><h4>Estimated cost per day</h4>
        <div class="ulegend">${USAGE_KINDS.map(([k, label]) => `<span><i class="ukey-${k}"></i>${esc(label)}</span>`).join("")}</div>
        ${usageChart(days)}
        <details><summary>Show as a table</summary>${dayTable(days)}</details></section>
      <section class="panel"><h4>Breakdown</h4>${breakdownTable(calls)}</section>
      <section class="panel"><h4>Most expensive calls</h4>${topCallsTable(calls)}</section>`; })();
  const noPrice = t.unpriced ? `<p class="bhint">${plural(t.unpriced, "call")} used a model with no price set, so the estimate is low.</p>` : "";
  return `${hero(stats)}${ranges}${noPrice}
    <main class="usage">${usage.users ? everyoneTable() : ""}${who}${body}</main>`;
}
