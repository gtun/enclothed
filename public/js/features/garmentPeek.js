/* Hovering or keyboard-focusing a garment named in AI prose (garmentRefs in templates/shared.js) shows its main photo;
   an outfit link shows a strip of its pieces, and clicking it opens them in the outfit builder.
   On a phone the tap simply follows the link. One floating box, reused; it never takes the pointer. */
"use strict";

let peekBox = null;
function showPeek(link){
  const outfit = link.dataset.oref ? link.dataset.oref.split(",").map(id => byId[id]).filter(Boolean) : null;
  const g = byId[link.dataset.gref]; if (!outfit && !g) return;
  if (!peekBox){ peekBox = Object.assign(document.createElement("div"), {className: "peek", hidden: true}); peekBox.setAttribute("role", "tooltip"); document.body.append(peekBox); }
  peekBox.classList.toggle("outfit", !!outfit);
  peekBox.innerHTML = outfit
    ? `<div class="peekrow">${outfit.map(p => `<div class="peekph">${ph(p, thumb(p), true)}</div>`).join("")}</div><span>Open in the outfit builder</span>`
    : `<div class="peekph">${ph(g, thumb(g), true)}</div><span>${esc(title(g))}${SHOW_IDS ? ` <small>#${g.id}</small>` : ""}</span>`;
  peekBox.hidden = false;
  // Below the link, or above when there's no room; kept inside the window.
  const r = link.getBoundingClientRect(), w = peekBox.offsetWidth, h = peekBox.offsetHeight;
  const top = r.bottom + 8 + h > innerHeight ? r.top - h - 8 : r.bottom + 8;
  peekBox.style.top = `${Math.max(8, top)}px`;
  peekBox.style.left = `${Math.min(Math.max(8, r.left + r.width / 2 - w / 2), innerWidth - w - 8)}px`;
}
const hidePeek = () => { if (peekBox) peekBox.hidden = true; };
const peekLink = e => e.target.closest?.("[data-gref],[data-oref]");
document.addEventListener("mouseover", e => { const l = peekLink(e); if (l) showPeek(l); });
document.addEventListener("mouseout", e => { const l = peekLink(e); if (l && !l.contains(e.relatedTarget)) hidePeek(); });
document.addEventListener("focusin", e => { const l = peekLink(e); if (l) showPeek(l); });
document.addEventListener("focusout", e => { if (peekLink(e)) hidePeek(); });
addEventListener("scroll", hidePeek, {passive: true});
addEventListener("hashchange", hidePeek);
document.addEventListener("click", e => {
  const link = e.target.closest?.("[data-oref]"); if (!link) return;
  e.preventDefault();   // a link (so it wraps like text), but it opens the builder rather than going anywhere
  hidePeek();
  openPiecesInBuilder(link.dataset.oref.split(",").map(Number));
});
