/* The language dropdown. It sets the language of the wardrobe being viewed, so an admin
   viewing as someone sees and changes that person's. A reload redraws everything in it. */
"use strict";

const languagePicker = document.getElementById("language");
function renderLanguage(profile){
  languagePicker.innerHTML = languageOptions(OPT.languages);
  languagePicker.value = profile.language;
  languagePicker.dataset.saved = profile.language;
  languagePicker.hidden = false;
}
languagePicker.addEventListener("change", async () => {
  languagePicker.disabled = true;
  try {
    await api("/api/language", {method: "PUT", body: {language: languagePicker.value}});
    location.reload();
  } catch (e) {
    toast(e.message, true);
    languagePicker.value = languagePicker.dataset.saved;
    languagePicker.disabled = false;
  }
});
