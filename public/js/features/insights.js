/* The Ask pop-up, on every page: sends questions to /api/insights and shows the answers.
   The conversation lives here in memory, so moving between pages keeps it and a refresh clears it.
   Each question sends the conversation so far, because the server doesn't remember it.
   Its markup is in templates/insightsPanel.js and answers are drawn by core/markdown.js. */
"use strict";

const INSIGHTS_HISTORY_MESSAGES = 20;   // the server's limit: the 10 most recent questions and answers
const insights = {open: false, busy: false, error: "", messages: []};
const insightsRoot = document.getElementById("insights");

function drawInsights(){
  const log = document.getElementById("insights-log");
  log.innerHTML = (insights.messages.length || insights.busy ? insights.messages.map(insightMessage).join("") : insightEmpty())
    + (insights.busy ? insightBusy() : "")
    + (insights.error ? `<p class="formerr" role="alert">${esc(insights.error)}</p>` : "");
  document.getElementById("insights-send").disabled = insights.busy;
  const fresh = insightsRoot.querySelector("[data-i-new]");
  fresh.hidden = !insights.messages.length;
  fresh.disabled = insights.busy;
  /* Show the start of the latest answer, not its end, so a long answer reads from the top. */
  const questions = log.querySelectorAll("[data-i-question]");
  if (questions.length) log.scrollTop = questions[questions.length - 1].offsetTop - 8;
}
function showInsights(open){
  insights.open = open;
  const panel = document.getElementById("insights-panel"), opener = document.getElementById("insights-open");
  panel.hidden = !open;
  opener.hidden = open;
  opener.setAttribute("aria-expanded", open);
  if (open){ drawInsights(); document.getElementById("insights-box").focus(); }
  else opener.focus({preventScroll: true});
}
async function askInsights(){
  const box = document.getElementById("insights-box"), question = box.value.trim();
  if (!question || insights.busy) return;
  const history = insights.messages.slice(-INSIGHTS_HISTORY_MESSAGES).map(({role, content}) => ({role, content}));
  insights.messages.push({role: "user", content: question});
  insights.busy = true; insights.error = ""; box.value = "";
  drawInsights();
  try {
    const {answer, queries} = await api("/api/insights", {method: "POST", body: {question, history}});
    insights.messages.push({role: "assistant", content: answer, queries});
  } catch (e) {
    /* Take the question back out so the conversation still alternates, and leave it in the box to retry. */
    insights.messages.pop();
    insights.error = e.message;
    if (!box.value) box.value = question;
  }
  insights.busy = false;
  drawInsights();
  if (insights.open) box.focus({preventScroll: true});
}
function startInsights(){
  insightsRoot.innerHTML = insightsFrame();
  insightsRoot.hidden = false;
  insightsRoot.addEventListener("click", e => {
    if (e.target.closest("#insights-open")) return showInsights(true);
    if (e.target.closest("[data-i-close]")) return showInsights(false);
    if (e.target.closest("[data-i-new]")){ insights.messages = []; insights.error = ""; drawInsights(); document.getElementById("insights-box").focus(); return; }
    const example = e.target.closest("[data-i-example]");
    if (example){ const box = document.getElementById("insights-box"); box.value = example.dataset.iExample; box.focus(); return; }
    /* On a phone the panel covers the page, so step aside to show the garment. The conversation stays. */
    if (e.target.closest(".ia a[href^='#garment-']") && isPhone()) showInsights(false);
  });
  /* Opening "How I worked this out" should survive the next answer redrawing the conversation. */
  insightsRoot.addEventListener("toggle", e => {
    const work = e.target.closest?.("[data-i-work]");
    if (work) insights.messages[work.dataset.iWork].workOpen = work.open;
  }, true);
  insightsRoot.addEventListener("submit", e => { e.preventDefault(); askInsights(); });
  insightsRoot.addEventListener("keydown", e => {
    if (e.key === "Escape" && insights.open){ e.stopPropagation(); showInsights(false); return; }
    /* isComposing: Enter picks a word while typing Chinese or Japanese, and shouldn't send. */
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.target.id === "insights-box" && !isPhone()){ e.preventDefault(); askInsights(); }
  });
}
