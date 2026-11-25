/* TEMPLATE: small boxes that float by what opened them: the "wore it" date picker (features/wears.js) and the photo
   preview of a garment or outfit named in AI prose (features/garmentPeek.js). */
"use strict";

const wearForm = today => `<label for="wear-day">Wore it on</label><input id="wear-day" class="txt" type="date" value="${today}" max="${today}" required>
    <div class="row"><button type="button" class="btn primary" data-wear-save>Log wear</button><button type="button" class="btn quiet" data-wear-cancel>Cancel</button></div>`;

const peekOutfit = pieces => `<div class="peekrow">${pieces.map(p => `<div class="peekph">${ph(p, thumb(p), true)}</div>`).join("")}</div><span>Open in the outfit builder</span>`;
const peekGarment = g => `<div class="peekph">${ph(g, thumb(g), true)}</div><span>${esc(title(g))}${SHOW_IDS ? ` <small>#${g.id}</small>` : ""}</span>`;
