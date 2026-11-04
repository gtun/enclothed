/* What someone sees when they can't get in: no account yet (403) or signed out (401). */
"use strict";

function accessPage(status){
  if (status === 403) return `<div class="state"><h1>You don't have an account yet</h1>
    <p>You signed in, but this email isn't set up here. Ask the person who runs this site to add you.</p>
    <p><a href="/cdn-cgi/access/logout">Sign in with a different email</a></p></div>`;
  return `<div class="state"><h1>You're signed out</h1>
    <p><a href="/">Sign in again</a></p></div>`;
}
function actAsBar(profile, users){
  if (profile.signed_in_as) return `<span>You're in <b>${esc(profile.name)}</b>'s wardrobe. Anything you change saves there.</span>
    <button type="button" data-act-as="">Back to mine</button>`;
  const others = users.filter(u => u.username !== profile.name);
  if (!others.length) return "";
  return `<label for="act-as">Open another wardrobe</label>
    <select id="act-as"><option value="">Choose a person</option>${others.map(u => `<option value="${u.id}">${esc(u.username)}</option>`).join("")}</select>`;
}
