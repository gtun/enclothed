/* Dialogs over the page (class "overlay"): the element, the scroll lock, the stack, and where focus goes back to.
   Dialogs stack: the latest one shown is drawn on top, and everything else on the page, including the dialogs under
   it, is inert (no clicks, focus or typing) until it closes. The LLM picker opened from Add garment is one case.
   Each dialog keeps its own keys and clicks: the upload dialog must let L reach llmPicker.js, for instance, while
   help and share stop keys. Only index.html loads this; share.html has no dialogs. */
"use strict";

const overlayStack = [];   // the open dialogs, bottom first

/* The dialog's element, made the first time it's asked for. setup(ov) runs only then, to add its listeners. */
function dialogOverlay(id, setup){
  let ov = document.getElementById(id);
  if (!ov){
    ov = document.createElement("div"); ov.id = id; ov.className = "overlay";
    document.body.appendChild(ov);
    setup(ov);
  }
  return ov;
}

const anyOverlayOpen = () => overlayStack.length > 0;
const topOverlay = () => overlayStack.at(-1) || null;   // the one dialog that can be used now

/* Only the top dialog can be used. With none open, the whole page can. */
function settleOverlays(){
  const top = topOverlay();
  for (const el of document.body.children){
    if (el.tagName !== "SCRIPT") el.inert = !!top && el !== top;
  }
}

function leaveStack(ov){
  const at = overlayStack.indexOf(ov);
  if (at >= 0) overlayStack.splice(at, 1);
}

function showOverlay(ov){
  leaveStack(ov);   // a dialog shown again moves to the top
  overlayStack.push(ov);
  document.body.appendChild(ov);   // last on the page, so it's drawn over the others (they share one z-index)
  ov.hidden = false;
  settleOverlays();
  document.body.style.overflow = "hidden";   // the page behind doesn't scroll
}

/* Empties the dialog, so nothing in it is left to find or focus. The dialog under it, if any, can be used again.
   returnFocus is skipped if it's no longer on the page. */
function hideOverlay(ov, returnFocus = null){
  ov.hidden = true; ov.innerHTML = "";
  leaveStack(ov);
  settleOverlays();
  if (!anyOverlayOpen()) document.body.style.overflow = "";
  if (returnFocus && document.contains(returnFocus)) returnFocus.focus();
}
