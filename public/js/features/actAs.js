/* The admin's switch between wardrobes. The server decides what's allowed; this only asks. */
"use strict";

async function renderActAs(profile){
  const bar = document.getElementById("actbar");
  if (!profile.is_admin) return;
  const html = actAsBar(profile, await api("/api/users"));
  bar.innerHTML = html;
  bar.hidden = !html;
  bar.classList.toggle("acting", !!profile.signed_in_as);
}
async function switchWardrobe(userId){
  try { await api("/api/act-as", {method: "PUT", body: {user_id: userId}}); }
  catch (e) { toast(e.message); return; }
  location.hash = "#wardrobe";
  location.reload();
}
function hideSections(){
  document.querySelector(".bar nav").style.display = "none";
}
document.getElementById("actbar").addEventListener("change", e => {
  if (e.target.id === "act-as" && e.target.value) switchWardrobe(+e.target.value);
});
document.getElementById("actbar").addEventListener("click", e => {
  if (e.target.closest("[data-act-as]")) switchWardrobe(null);
});
