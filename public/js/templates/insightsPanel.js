/* TEMPLATE: the Ask pop-up: its frame, the example questions, and each question and answer. */
"use strict";

const INSIGHT_EXAMPLES = ["How many pieces do I own?", "What aesthetic best describes my wardrobe?", "Show me a table of my pieces by brand"];
const INSIGHT_NOTICE = "Questions and answers are saved so Gary can improve enclothed.";

const insightsFrame = () => `
  <button type="button" class="btn llm-action insights-open" id="insights-open" aria-expanded="false" aria-controls="insights-panel">Ask your wardrobe</button>
  <section class="insights-panel" id="insights-panel" aria-label="Ask your wardrobe" hidden>
    <div class="bhead">
      <h2>Ask your wardrobe</h2>
      <button type="button" class="btn quiet" data-i-new hidden>New conversation</button>
      <button type="button" class="iconbtn" data-i-close aria-label="Close">×</button>
    </div>
    <div class="ilog" id="insights-log" aria-live="polite"></div>
    <form class="ifoot" id="insights-form">
      <textarea class="txt" id="insights-box" rows="2" maxlength="2000" aria-label="Your question" placeholder="Ask anything about your clothes"></textarea>
      <div class="ifoot-row">
        <p class="bhint">${esc(INSIGHT_NOTICE)}</p>
        <button type="submit" class="btn llm-action" id="insights-send">Ask</button>
      </div>
    </form>
  </section>`;

const insightEmpty = () => `<div class="istart">
  <p>Ask about what you own, what's missing, or your style. Try one of these:</p>
  ${INSIGHT_EXAMPLES.map(q => `<button type="button" class="btn" data-i-example="${esc(q)}">${esc(q)}</button>`).join("")}
</div>`;

/* One garment inside a line of text. An id that isn't in this wardrobe shows nothing. */
function insightGarmentRef(id){
  const g = byId[id];
  return g ? `<a class="iref${fadeClass(g)}" href="#garment-${g.id}" aria-label="${esc(title(g))}" title="${esc(title(g))}">${ph(g, thumb(g), true)}</a>` : "";
}
function insightGarmentRow(ids){
  const pieces = ids.map(id => byId[id]).filter(Boolean);
  if (!pieces.length) return "";
  return `<div class="inset">${pieces.map(g => `<a class="mini" href="#garment-${g.id}"><div class="ph${fadeClass(g)}">${ph(g, thumb(g), true)}${goneMark(g)}</div><span>${esc(subcategoryName(g.subcategory))}</span><em>${esc(g.brand || "")}</em></a>`).join("")}</div>`;
}
const insightWork = (m, index) => m.queries?.length ? `<details class="iwork" data-i-work="${index}"${m.workOpen ? " open" : ""}>
  <summary>How I worked this out</summary>
  <p>The ${m.queries.length === 1 ? "search" : "searches"} I ran on your wardrobe:</p>
  ${m.queries.map(sql => `<pre>${esc(sql)}</pre>`).join("")}
</details>` : "";

function insightMessage(m, index){
  if (m.role === "user") return `<p class="iq" data-i-question>${esc(m.content)}</p>`;
  return `<div class="ia">${renderMarkdown(m.content, insightGarmentRef, insightGarmentRow)}${insightWork(m, index)}</div>`;
}
const insightBusy = () => `<div class="busy"><span class="spin" aria-hidden="true"></span>Checking your wardrobe…</div>`;
