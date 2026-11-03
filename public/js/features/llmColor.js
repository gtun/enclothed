/* Picks the color of AI buttons (class "llm-action") from the wardrobe; see aiButtonColor in settings.js. */
"use strict";

const _rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255);
function luminance(h){
  const [r, g, b] = _rgb(h).map(c => c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrastRatio = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
function saturation(h){
  const [r, g, b] = _rgb(h), max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
  return max === min ? 0 : (max - min) / (1 - Math.abs(2 * l - 1));
}
const LIGHT_GARMENT = 0.3;   // primary colors brighter than this count as "light-colored garments"

/* The most common accent among light (or dark) garments that is colorful and stands out on bg. */
function wardrobeAccent(lightGarments, bg){
  const counts = {};
  OWNED.forEach(g => {
    if ((luminance(hex(g.primary_color)) > LIGHT_GARMENT) !== lightGarments) return;
    g.accent_colors.forEach(c => { counts[c] = (counts[c] || 0) + 1; });
  });
  return Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name]) => hex(name))
    .find(h => saturation(h) >= 0.3 && contrastRatio(h, bg) >= 3) || null;
}
function themeBackground(theme){
  const root = document.documentElement, was = root.getAttribute("data-theme");
  root.setAttribute("data-theme", theme);
  const bg = getComputedStyle(root).getPropertyValue("--bg").trim();
  root.setAttribute("data-theme", was);
  return bg;
}
function applyLlmColors(){
  let style = document.getElementById("llm-colors");
  if (!style){ style = document.createElement("style"); style.id = "llm-colors"; document.head.appendChild(style); }
  if (SETTINGS.aiButtonColor !== "wardrobe"){ style.textContent = ""; return; }
  const rule = (theme, light) => {
    const bg = themeBackground(theme);
    if (!/^#[0-9a-f]{6}$/i.test(bg)) return "";
    const c = wardrobeAccent(light, bg);
    if (!c) return "";
    const on = contrastRatio(c, "#ffffff") >= contrastRatio(c, "#121212") ? "#ffffff" : "#121212";
    return `:root[data-theme="${theme}"]{--llm:${c};--on-llm:${on}}`;
  };
  style.textContent = rule("light", true) + "\n" + rule("dark", false);
}
