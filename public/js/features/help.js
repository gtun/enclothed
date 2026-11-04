/* Help for each page type: opens by itself the first time someone sees that type, and from the ? button after that.
   Its text is in templates/helpDialog.js. What each person has seen is kept per browser, under their own name. */
"use strict";

let helpKey = null, helpSeen = [];   // helpSeen stays in memory too, for browsers that block storage
const helpBtn = document.getElementById("help-btn");

/* A disowned page counts as one type, whichever tab comes first. */
const helpTopic = view => view.startsWith("disowned") ? "disowned" : view;

/* me is the person signed in, so an admin looking at someone else's wardrobe doesn't use up that person's help. */
function startHelp(me){
  helpKey = `enclothed-help-seen:${me}`;
  helpSeen = store.get(helpKey, []);
  helpBtn.hidden = false;
}
function openHelp(view, firstVisit = false){
  let ov = document.getElementById("help");
  if (!ov){ ov = document.createElement("div"); ov.id = "help"; ov.className = "overlay"; document.body.appendChild(ov);
    ov.addEventListener("click", e => { if (e.target === ov || e.target.closest("[data-h-close]")) closeHelp(); });
    ov.addEventListener("keydown", e => {
      e.stopPropagation();   // arrow keys shouldn't move the photos behind the dialog
      if (e.key === "Escape") closeHelp();
      if (e.key === "Tab") e.preventDefault();   // "Got it" is the only thing to focus
    }); }
  ov.dataset.returnFocus = firstVisit ? "" : "yes";
  ov.innerHTML = helpDialog(helpTopic(view), firstVisit);
  ov.hidden = false; document.body.style.overflow = "hidden";
  ov.querySelector("[data-h-close]").focus();
}
function closeHelp(){
  const ov = document.getElementById("help");
  if (!ov || ov.hidden) return;
  ov.hidden = true; ov.innerHTML = ""; document.body.style.overflow = "";
  if (ov.dataset.returnFocus) helpBtn.focus();
}
function showHelpOnce(view){
  const topic = helpTopic(view);
  if (helpSeen.includes(topic)) return;
  helpSeen = [...helpSeen, topic];
  store.set(helpKey, helpSeen);
  openHelp(view, true);
}
helpBtn.addEventListener("click", () => openHelp(current));
