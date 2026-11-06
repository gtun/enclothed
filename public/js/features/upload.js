/* The Add garment dialog: choosing photos and sending them. Its markup is in templates/uploadDialog.js. */
"use strict";

let upload = {files: [], busy: false};
function openUpload(){
  upload = {files: [], busy: false, prompt: "", notes: ""};
  let ov = document.getElementById("upload");
  if (!ov){ ov = document.createElement("div"); ov.id = "upload"; ov.className = "overlay"; document.body.appendChild(ov);
    ov.addEventListener("click", uploadClick); ov.addEventListener("change", uploadChange); ov.addEventListener("input", e => {
      if (e.target.id === "u-prompt") upload.prompt = e.target.value; if (e.target.id === "u-notes") upload.notes = e.target.value; });
    ov.addEventListener("keydown", e => { if (e.key === "Escape" && !upload.busy) closeUpload(); }); }
  ov.hidden = false; document.body.style.overflow = "hidden";
  renderUpload();
  ov.querySelector("[data-u-close]").focus();
}
function closeUpload(keepPhotos = false){
  if (!keepPhotos) upload.files.forEach(f => URL.revokeObjectURL(f.url));
  const ov = document.getElementById("upload"); ov.hidden = true; ov.innerHTML = ""; document.body.style.overflow = "";
}
function renderUpload(){
  const ov = document.getElementById("upload");
  ov.innerHTML = uploadDialog();
  ov.querySelectorAll("[data-u-img]").forEach(img => { img.onerror = () => {
    const name = document.createElement("span"); name.className = "fname"; name.textContent = upload.files[+img.dataset.uImg]?.file.name || "photo"; img.replaceWith(name); }; });
}
const OPT_UPLOAD_MAX = 10;
function uploadChange(e){
  const input = e.target.closest("[data-u-input]"); if (!input) return;
  const room = OPT_UPLOAD_MAX - upload.files.length;
  const picked = [...input.files].slice(0, room);
  if (input.files.length > room) toast(`Only ${OPT_UPLOAD_MAX} photos per garment; the rest were skipped.`, true);
  upload.files.push(...picked.map(file => ({file, url: URL.createObjectURL(file)})));
  renderUpload();
}
async function uploadClick(e){
  if (e.target.id === "upload" && !upload.busy) return closeUpload();
  const t = e.target.closest("button"); if (!t) return;
  if (t.hasAttribute("data-u-close")) closeUpload();
  else if (t.dataset.uRm){ const [gone] = upload.files.splice(+t.dataset.uRm, 1); URL.revokeObjectURL(gone.url); renderUpload(); }
  else if (t.hasAttribute("data-u-submit")){
    upload.busy = true; renderUpload();
    const form = new FormData();
    upload.files.forEach(f => form.append("photos", f.file, f.file.name || "photo.jpg"));
    if (upload.prompt.trim()) form.append("prompt_message", upload.prompt);
    if (upload.notes.trim()) form.append("notes", upload.notes);
    try {
      let res;
      try { res = await fetch("/api/garments/drafts", {method: "POST", body: form}); }
      catch (err) { throw new Error("Couldn't reach the server. Is it still running?"); }
      let data = null; try { data = await res.json(); } catch (err) {}
      if (!res.ok) throw new Error(errorText(data, res.status));
      const photos = upload.files.map(f => f.url);
      closeUpload(true);
      openReview({mode: "new", g: data.garment, draftId: data.id, photos});
    } catch (err) {
      upload.busy = false; renderUpload();
      const box = document.getElementById("u-err"); if (box) box.textContent = err.message;
    }
  }
}
