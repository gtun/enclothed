/* Talking to the server: api() for JSON requests, errorText() for readable error messages. */
"use strict";

/* The LLM an admin picked for this tab (hold L and click an AI button: features/llmPicker.js). sessionStorage, so it
   lasts through refreshes in this tab only, and every other tab keeps its own. The server ignores it for anyone
   who isn't an admin. Sent with every request; only the AI endpoints read it. */
const LLM_PICK_KEY = "enclothed-llm";
function pickedLLM(){ try { return sessionStorage.getItem(LLM_PICK_KEY); } catch (e) { return null; } }
function llmHeaders(){ const picked = pickedLLM(); return picked ? {"X-LLM-Provider": picked} : {}; }

async function api(path, options = {}){
  const init = {...options, headers: {"Accept": "application/json", ...llmHeaders(), ...(options.headers || {})}};
  if (options.body !== undefined){ init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); }
  let res;
  try { res = await fetch(path, init); }
  catch (e) { throw new Error("Couldn't reach the server. Is it still running?"); }
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (!res.ok){ const error = new Error(errorText(data, res.status)); error.status = res.status; throw error; }
  return data;
}
function errorText(data, status){
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map(e => {
    const field = (e.loc || []).filter(x => x !== "body" && typeof x === "string").join(" › ");
    return (field ? field + ": " : "") + String(e.msg || "").replace(/^Value error, /, "");
  }).join("; ");
  return `Request failed (${status})`;
}
