/* The Add garment dialog: choosing, pasting or dropping photos, and sending them. Its markup is in templates/uploadDialog.js. */
"use strict";

let upload = {files: [], busy: false};
/* purpose is "add" (Add garment) or "weigh" (should I buy this?). Both tag the photos the same way; they part at review. */
function openUpload(purpose = "add"){
  upload = {files: [], busy: false, prompt: "", notes: "", purpose};
  let ov = document.getElementById("upload");
  if (!ov){ ov = document.createElement("div"); ov.id = "upload"; ov.className = "overlay"; document.body.appendChild(ov);
    ov.addEventListener("click", uploadClick); ov.addEventListener("change", uploadChange); ov.addEventListener("input", e => {
      if (e.target.id === "u-prompt") upload.prompt = e.target.value; if (e.target.id === "u-notes") upload.notes = e.target.value; });
    ov.addEventListener("keydown", e => { if (e.key === "Escape" && !upload.busy) closeUpload(); });
    ov.addEventListener("dragover", e => { if (!hasDraggedFiles(e) || upload.busy) return; e.preventDefault(); ov.classList.add("dropping"); });
    ov.addEventListener("dragleave", e => { if (!ov.contains(e.relatedTarget)) ov.classList.remove("dropping"); });
    ov.addEventListener("drop", e => { ov.classList.remove("dropping"); if (!hasDraggedFiles(e)) return; e.preventDefault();
      if (!upload.busy) addUploadFiles(e.dataTransfer.files); }); }
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
/* Every way in (picker, camera, paste, drop) ends here. Non-images are skipped; the server re-checks anyway. */
function addUploadFiles(fileList){
  const all = [...fileList], images = all.filter(f => f.type.startsWith("image/"));
  if (images.length < all.length) toast("Only photos can be added; other files were skipped.", true);
  if (!images.length) return;
  const room = OPT_UPLOAD_MAX - upload.files.length;
  if (images.length > room) toast(`Only ${OPT_UPLOAD_MAX} photos per garment; the rest were skipped.`, true);
  upload.files.push(...images.slice(0, room).map(file => ({file, url: URL.createObjectURL(file)})));
  renderUpload();
}
function uploadChange(e){
  const input = e.target.closest("[data-u-input]"); if (!input) return;
  addUploadFiles(input.files);
}
const hasDraggedFiles = e => [...(e.dataTransfer?.types || [])].includes("Files");
const isTextField = el => el?.matches?.("input:not([type=file]), textarea, [contenteditable]:not([contenteditable=false])");

/* Clipboard images (a screenshot, "Copy image" in a browser, a photo copied from Photos). They usually
   arrive named "image.png", so each gets its own name for the previews and any server error message. */
let pasteCount = 0;
function clipboardImages(e){
  return [...(e.clipboardData?.items || [])]
    .filter(item => item.kind === "file" && item.type.startsWith("image/"))
    .map(item => item.getAsFile()).filter(Boolean)
    .map(f => new File([f], `pasted-${++pasteCount}.${f.type.split("/")[1] || "png"}`, {type: f.type}));
}
/* Paste works anywhere: inside the dialog it adds the photos; elsewhere it opens Add garment
   (or Weigh, on the weigh pages) with them. Text pastes into text fields are left alone. */
document.addEventListener("paste", e => {
  const images = clipboardImages(e); if (!images.length) return;
  // Copying from a spreadsheet or document puts text *and* a picture of it on the clipboard: in a text field, the text wins.
  if (isTextField(e.target) && e.clipboardData.types.includes("text/plain")) return;
  const ov = document.getElementById("upload");
  if (ov && !ov.hidden){ e.preventDefault(); if (!upload.busy) addUploadFiles(images); return; }
  if ([...document.querySelectorAll(".overlay")].some(o => !o.hidden)) return;   // another dialog is open
  e.preventDefault();
  openUpload(location.hash.startsWith("#weigh") ? "weigh" : "add");
  addUploadFiles(images);
});
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
      openReview({mode: upload.purpose === "weigh" ? "weigh" : "new", g: data.garment, draftId: data.id, photos});
    } catch (err) {
      upload.busy = false; renderUpload();
      const box = document.getElementById("u-err"); if (box) box.textContent = err.message;
    }
  }
}
