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
for (const input of Object.values(filters)) input.addEventListener("input", filter);
document.getElementById("pause-all").addEventListener("click", pause);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) pause();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") pause();
});

document.documentElement.dataset.galleryReady = "true";
