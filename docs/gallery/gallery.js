// Playback is deliberately opt-in, including when reduced motion is requested.
// Only one GIF loads/plays at a time; hidden results never keep animating.
const cards = [...document.querySelectorAll("article")];
const filters = Object.fromEntries(
  ["search", "family", "action", "kind"].map((id) => [id, document.getElementById(id)]),
);
let playing = null;
function pause() {
  if (!playing) return;
  const image = document.getElementById(playing.dataset.play);
  image.src = image.dataset.poster;
  playing.textContent = "Play";
  playing.setAttribute("aria-pressed", "false");
  playing = null;
}
for (const button of document.querySelectorAll("[data-play]"))
  button.addEventListener("click", () => {
    const same = playing === button;
    pause();
    if (same) return;
    playing = button;
    const image = document.getElementById(button.dataset.play);
    image.src = image.dataset.animation;
    button.textContent = "Pause";
    button.setAttribute("aria-pressed", "true");
  });
function filter() {
  pause();
  const query = filters.search.value.toLowerCase().trim();
  let count = 0;
  for (const card of cards) {
    card.hidden =
      !card.dataset.search.includes(query) ||
      (filters.family.value && !card.dataset.families.split(" ").includes(filters.family.value)) ||
      (filters.action.value && card.dataset.action !== filters.action.value) ||
      (filters.kind.value && card.dataset.kind !== filters.kind.value);
    if (!card.hidden) count++;
  }
  document.getElementById("count").textContent = `${count} ${count === 1 ? "example" : "examples"}`;
  document.getElementById("empty").hidden = count > 0;
}
function readFilters() {
  const query = new URLSearchParams(location.search);
  filters.search.value = (query.get("search") || "").slice(0, 160);
  for (const key of ["family", "action", "kind"])
    filters[key].value = [...filters[key].options].some((option) => option.value === query.get(key))
      ? query.get(key)
      : "";
  filter();
}
for (const input of Object.values(filters))
  input.addEventListener("input", () => {
    filter();
    const query = new URLSearchParams();
    for (const [key, control] of Object.entries(filters))
      if (control.value) query.set(key, control.value);
    const url = new URL(location.href);
    url.search = query.toString();
    // file:// previews can deny history changes; filtering must still work.
    try {
      history.replaceState(null, "", url);
    } catch {
      /* Local preview. */
    }
  });
addEventListener("popstate", readFilters);
readFilters();
async function copy(text, label, note) {
  document.getElementById("copy-result").hidden = false;
  document.getElementById("copy-label").textContent = label;
  const field = document.getElementById("copy-text");
  field.value = text;
  try {
    await navigator.clipboard.writeText(text);
    document.getElementById("copy-note").textContent = "Copied. " + note;
  } catch {
    field.select();
    document.getElementById("copy-note").textContent = "Select and copy the text above. " + note;
  }
}
for (const button of document.querySelectorAll("[data-command]"))
  button.addEventListener("click", () =>
    copy(
      button.dataset.command,
      "Local Studio command",
      "Download the JSON first, then run this from its folder with NiriFX installed.",
    ),
  );
document.getElementById("share-view").addEventListener("click", () => {
  const url = new URL("https://jturbide.github.io/niri-fx/gallery/");
  for (const [key, control] of Object.entries(filters))
    if (control.value) url.searchParams.set(key, control.value);
  url.hash = location.hash;
  copy(url.href, "Gallery link", "The link preserves filters; previews still start paused.");
});
document.getElementById("pause-all").addEventListener("click", pause);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) pause();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") pause();
});

document.documentElement.dataset.galleryReady = "true";
