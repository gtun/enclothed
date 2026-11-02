/* The photo carousel on the garment page (arrows, keyboard, position). */
"use strict";

let galleryGo = null;
function wireGallery(startAt = 0){
  galleryGo = null;
  const track = document.getElementById("track"); if (!track) return;
  const n = track.children.length;
  const idx = () => Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
  const labels = [...track.querySelectorAll("img")].map(i => i.alt.split(", ").pop());
  const update = () => { const i = idx();
    document.getElementById("gcount").textContent = `${i + 1} / ${n} · ${labels[i] || ""}`;
    document.getElementById("gprev").disabled = i === 0; document.getElementById("gnext").disabled = i === n - 1; };
  const go = d => track.scrollTo({left:(idx() + d) * track.clientWidth, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  document.getElementById("gprev").onclick = () => go(-1);
  document.getElementById("gnext").onclick = () => go(1);
  track.addEventListener("scroll", () => requestAnimationFrame(update));
  if (startAt) track.scrollLeft = startAt * track.clientWidth;
  galleryGo = go; update();
}
const galleryIndex = () => { const t = document.getElementById("track"); return t ? Math.round(t.scrollLeft / Math.max(1, t.clientWidth)) : 0; };
