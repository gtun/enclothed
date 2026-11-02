/* The small message that pops up at the bottom ("Saved", errors). */
"use strict";

let toastTimer = null;
function toast(msg, isErr){
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.toggle("err", !!isErr); t.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), isErr ? 6000 : 1800);
}
