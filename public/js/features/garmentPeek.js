/* Hovering or keyboard-focusing a garment named in AI prose (garmentRefs in templates/shared.js) shows its main photo.
   On a phone the tap simply opens the garment. One floating box, reused; it never takes the pointer. */
"use strict";

let peekBox = null;
function showPeek(link){
  const g = byId[link.dataset.gref]; if (!g) return;
  if (!peekBox){ peekBox = Object.assign(document.createElement("div"), {className: "peek", hidden: true}); peekBox.setAttribute("role", "tooltip"); document.body.append(peekBox); }
  peekBox.innerHTML = `<div class="peekph">${ph(g, thumb(g), true)}</div><span>${esc(title(g))}${SHOW_IDS ? ` <small>#${g.id}</small>` : ""}</span>`;
  peekBox.hidden = false;
  // Below the link, or above when there's no room; kept inside the window.
  const r = link.getBoundingClientRect(), w = peekBox.offsetWidth, h = peekBox.offsetHeight;
  const top = r.bottom + 8 + h > innerHeight ? r.top - h - 8 : r.bottom + 8;
  peekBox.style.top = `${Math.max(8, top)}px`;
  peekBox.style.left = `${Math.min(Math.max(8, r.left + r.width / 2 - w / 2), innerWidth - w - 8)}px`;
}
const hidePeek = () => { if (peekBox) peekBox.hidden = true; };
const peekLink = e => e.target.closest?.("[data-gref]");
document.addEventListener("mouseover", e => { const l = peekLink(e); if (l) showPeek(l); });
document.addEventListener("mouseout", e => { const l = peekLink(e); if (l && !l.contains(e.relatedTarget)) hidePeek(); });
document.addEventListener("focusin", e => { const l = peekLink(e); if (l) showPeek(l); });
document.addEventListener("focusout", e => { if (peekLink(e)) hidePeek(); });
addEventListener("scroll", hidePeek, {passive: true});
addEventListener("hashchange", hidePeek);
