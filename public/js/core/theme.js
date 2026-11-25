/* The Day / Evening buttons, on the app and on share links. The choice is kept per browser, and each page's <head>
   applies it before the page draws, so it never flashes the other one. */
"use strict";

function paintTheme(){
  const t = document.documentElement.getAttribute("data-theme");
  document.querySelectorAll("[data-t]").forEach(b => b.setAttribute("aria-pressed", b.dataset.t === t));
}
document.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => {
  document.documentElement.setAttribute("data-theme", b.dataset.t);
  try { localStorage.setItem("enclothed-theme", b.dataset.t); } catch (e) {}
  paintTheme();
}));
paintTheme();
