/* The photo carousel on the garment page (arrows, keyboard, position). Going past the last photo returns to the first; there's no wrap the other way. */
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
    document.getElementById("gprev").disabled = i === 0; document.getElementById("gnext").disabled = n < 2; };
  const go = d => track.scrollTo({left:(idx() + d >= n ? 0 : idx() + d) * track.clientWidth, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  document.getElementById("gprev").onclick = () => go(-1);
  document.getElementById("gnext").onclick = () => go(1);
  track.addEventListener("scroll", () => requestAnimationFrame(update));
  /* The track can't scroll past its end, so a swipe or side-scroll there is caught by hand. On a wheel or
     trackpad it has to start after a pause, or the tail of the scroll that reached the last photo would wrap. */
  const atEnd = () => idx() === n - 1;
  let lastWheel = -Infinity, touchX = null;
  track.addEventListener("wheel", e => {
    const fresh = e.timeStamp - lastWheel > 200; lastWheel = e.timeStamp;
    if (fresh && atEnd() && e.deltaX > Math.abs(e.deltaY)) go(1);
  }, {passive: true});
  track.addEventListener("touchstart", e => { touchX = atEnd() ? e.touches[0].clientX : null; }, {passive: true});
  track.addEventListener("touchend", e => { if (touchX !== null && touchX - e.changedTouches[0].clientX > 40) go(1); }, {passive: true});
  if (startAt) track.scrollLeft = startAt * track.clientWidth;
  galleryGo = go; update();
}
const galleryIndex = () => { const t = document.getElementById("track"); return t ? Math.round(t.scrollLeft / Math.max(1, t.clientWidth)) : 0; };
