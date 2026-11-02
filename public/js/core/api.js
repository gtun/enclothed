/* Talking to the server: api() for JSON requests, errorText() for readable error messages. */
"use strict";

async function api(path, options = {}){
  const init = {headers: {"Accept": "application/json"}, ...options};
  if (options.body !== undefined){ init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); }
  let res;
  try { res = await fetch(path, init); }
  catch (e) { throw new Error("Couldn't reach the server. Is it still running?"); }
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error(errorText(data, res.status));
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
