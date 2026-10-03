const STORAGE_KEY = "still-good-profile";
const STAR_LIMIT = 3;

const selected = new Set();
const soon = new Set();
let skipIds = [];
let busy = false;

const board = document.querySelector("#chip-board");
const cookButton = document.querySelector("#cook");
const anotherButton = document.querySelector("#another");
const note = document.querySelector("#note");
const nameInput = document.querySelector("#friend-name");

function defaults() {
  return {
    name: "your friend",
    diet: "vegetarian",
    allergies: [],
    wontEat: [],
    minutes: 15,
    skill: "follow",
  };
}

function loadProfile() {
  const profile = defaults();
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (saved && typeof saved === "object") Object.assign(profile, saved);
  } catch (_err) {
    /* keep defaults */
  }
  nameInput.value = profile.name || defaults().name;
  checkRadio("diet", profile.diet);
  checkRadio("minutes", String(profile.minutes));
  checkRadio("skill", profile.skill);
  checkBoxes("allergy", profile.allergies || []);
  checkBoxes("wont", profile.wontEat || []);
  paintName();
}

function checkRadio(name, value) {
  const input = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (input) input.checked = true;
}

function checkBoxes(name, values) {
  const wanted = new Set(values);
  document.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
    input.checked = wanted.has(input.value);
  });
}

function currentProfile() {
  const name = nameInput.value.trim() || "your friend";
  return {
    name,
    diet: document.querySelector('input[name="diet"]:checked').value,
    allergies: checkedValues("allergy"),
    wont_eat: checkedValues("wont"),
    minutes: Number(document.querySelector('input[name="minutes"]:checked').value),
    skill: document.querySelector('input[name="skill"]:checked').value,
  };
}

function checkedValues(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);
}

function saveProfile() {
  const profile = currentProfile();
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      name: profile.name,
      diet: profile.diet,
      allergies: profile.allergies,
      wontEat: profile.wont_eat,
      minutes: profile.minutes,
      skill: profile.skill,
    }),
  );
  paintName();
}

function paintName() {
  const name = nameInput.value.trim() || "your friend";
  document.querySelector("#for-name").textContent = `for ${name}`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function starLabel(item, starred) {
  return starred ? `Use ${item.label} soon` : `Mark ${item.label} use soon`;
}

function renderBoard(ingredients) {
  const groups = [
    ["pantry", "Pantry"],
    ["fridge", "Fridge"],
  ];
  board.replaceChildren();
  groups.forEach(([key, title]) => {
    const heading = document.createElement("h3");
    heading.className = "group-title";
    heading.textContent = title;
    const wrap = document.createElement("div");
    wrap.className = "chips";
    ingredients.filter((item) => item.group === key).forEach((item) => {
      wrap.append(renderChip(item));
    });
    board.append(heading, wrap);
  });
  refreshChips();
}

function renderChip(item) {
  const chip = document.createElement("div");
  chip.className = "chip";
  chip.dataset.id = item.id;

  const main = document.createElement("button");
  main.type = "button";
  main.className = "chip-main";
  main.dataset.chip = item.id;
  main.setAttribute("aria-pressed", "false");
  main.innerHTML = `<svg class="check" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5L20 7" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></path></svg><span>${escapeHtml(item.label)}</span>`;

  const star = document.createElement("button");
  star.type = "button";
  star.className = "chip-star";
  star.dataset.star = item.id;
  star.setAttribute("aria-pressed", "false");
  star.setAttribute("aria-label", starLabel(item, false));
  star.innerHTML = `<svg class="star-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.6l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 16.1 7.2 18.5l.9-5.4L4.2 9.3l5.4-.8L12 3.6z" fill="currentColor"></path></svg><span class="star-caption">Star</span>`;

  main.addEventListener("click", () => toggleChip(item.id));
  star.addEventListener("click", () => toggleStar(item, star));
  chip.append(main, star);
  return chip;
}

function toggleChip(id) {
  if (selected.has(id)) {
    selected.delete(id);
    soon.delete(id);
  } else {
    selected.add(id);
  }
  refreshChips();
}

function toggleStar(item, button) {
  const id = item.id;
  if (soon.has(id)) {
    soon.delete(id);
  } else {
    if (!selected.has(id)) selected.add(id);
    if (soon.size >= STAR_LIMIT) {
      setStarStatus(`Three is the limit. Unstar one before starring ${item.label}.`);
      button.focus();
      refreshChips();
      return;
    }
    soon.add(id);
  }
  refreshChips();
}

function refreshChips() {
  document.querySelectorAll(".chip").forEach((chip) => {
    const id = chip.dataset.id;
    const on = selected.has(id);
    const starred = soon.has(id);
    chip.classList.toggle("is-on", on);
    chip.classList.toggle("is-soon", starred);
    const main = chip.querySelector(".chip-main");
    const star = chip.querySelector(".chip-star");
    const caption = chip.querySelector(".star-caption");
    main.setAttribute("aria-pressed", on ? "true" : "false");
    star.setAttribute("aria-pressed", starred ? "true" : "false");
    const label = main.querySelector("span").textContent;
    star.setAttribute("aria-label", starred ? `Use ${label} soon` : `Mark ${label} use soon`);
    caption.textContent = starred ? "Use soon" : "Star";
  });
  setStarStatus(`Starred ${soon.size} of ${STAR_LIMIT}.`);
  cookButton.disabled = busy || selected.size === 0;
  if (!busy) {
    cookButton.textContent = selected.size ? "What's still good?" : "Pick at least one thing";
  }
}

function setStarStatus(text) {
  document.querySelector("#star-status").textContent = text;
}

function setNoteEmpty() {
  note.dataset.noteStatus = "empty";
  document.querySelector("#origin-badge").hidden = true;
  document.querySelector("#fallback-line").hidden = true;
  document.querySelector("#note-title").textContent = "Your note will land here.";
  document.querySelector("#note-why").textContent = "Pick what you have, then ask what is still good.";
  document.querySelector("#note-steps").replaceChildren();
  document.querySelector("#model-line").hidden = true;
  document.querySelector("#used-label").hidden = true;
  document.querySelector("#used-ingredients").replaceChildren();
  document.querySelector("#remaining-line").hidden = true;
  anotherButton.hidden = true;
}

function showWriting() {
  note.dataset.noteStatus = "writing";
  document.querySelector("#origin-badge").hidden = true;
  document.querySelector("#fallback-line").hidden = true;
  document.querySelector("#note-title").textContent = "Writing the note…";
  document.querySelector("#note-why").textContent = "Gemma is at the counter on this machine. The dish is already chosen.";
  document.querySelector("#note-steps").replaceChildren();
  document.querySelector("#model-line").hidden = true;
  anotherButton.hidden = true;
}

function showProblem(message) {
  note.dataset.noteStatus = "error";
  document.querySelector("#origin-badge").hidden = true;
  document.querySelector("#fallback-line").hidden = true;
  document.querySelector("#note-title").textContent = "The note did not come back.";
  document.querySelector("#note-why").textContent = message;
  document.querySelector("#note-steps").replaceChildren();
  document.querySelector("#model-line").hidden = true;
  anotherButton.hidden = true;
}

function showNoMatch(message) {
  note.dataset.noteStatus = "none";
  document.querySelector("#origin-badge").hidden = true;
  document.querySelector("#fallback-line").hidden = true;
  document.querySelector("#note-title").textContent = "Nothing fits tonight.";
  document.querySelector("#note-why").textContent = message;
  document.querySelector("#note-steps").replaceChildren();
  document.querySelector("#model-line").hidden = true;
  document.querySelector("#used-label").hidden = true;
  document.querySelector("#used-ingredients").replaceChildren();
  document.querySelector("#remaining-line").hidden = true;
  anotherButton.hidden = true;
}

function seconds(ms) {
  return `${(Number(ms) / 1000).toFixed(1)}s`;
}

function showNote(data) {
  note.dataset.noteStatus = data.source;
  note.dataset.recipeId = data.recipe_id;
  const badge = document.querySelector("#origin-badge");
  badge.hidden = false;
  badge.dataset.origin = data.source;
  badge.textContent = data.source === "gemma" ? "From Gemma" : "Fallback note";

  const fallback = document.querySelector("#fallback-line");
  if (data.message) {
    fallback.hidden = false;
    fallback.textContent = data.message;
  } else {
    fallback.hidden = true;
    fallback.textContent = "";
  }

  document.querySelector("#note-title").textContent = data.title;
  document.querySelector("#note-why").textContent = data.why;
  const steps = document.querySelector("#note-steps");
  steps.replaceChildren();
  data.steps.forEach((step) => {
    const li = document.createElement("li");
    li.textContent = step;
    steps.append(li);
  });

  const meta = document.querySelector("#model-line");
  meta.hidden = false;
  meta.textContent = `${data.model_label}, on this machine · ${data.model} · ${seconds(data.generation_ms)}`;

  document.querySelector("#used-label").hidden = false;
  const used = document.querySelector("#used-ingredients");
  used.replaceChildren();
  data.ingredients.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item.label;
    used.append(li);
  });

  const remaining = document.querySelector("#remaining-line");
  remaining.hidden = false;
  remaining.textContent = data.remaining
    ? `${data.remaining} other match${data.remaining === 1 ? "" : "es"} if this one does not suit.`
    : "That is the last match for this fridge.";
  anotherButton.hidden = false;
  anotherButton.disabled = data.remaining === 0;
  anotherButton.textContent = data.remaining ? "Another" : "That's the last match";
}

async function ask(isAnother) {
  if (busy || selected.size === 0) return;
  if (!isAnother) skipIds = [];
  busy = true;
  cookButton.disabled = true;
  cookButton.textContent = "Writing the note…";
  anotherButton.disabled = true;
  showWriting();
  const profile = currentProfile();
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile,
        selected: [...selected],
        use_soon: [...soon],
        skip: skipIds,
      }),
      signal: AbortSignal.timeout(320000),
    });
    const data = await response.json();
    if (!response.ok) {
      showProblem(data.detail || "The kitchen could not read that request.");
      return;
    }
    if (!data.ok) {
      showNoMatch(data.message);
      return;
    }
    skipIds.push(data.recipe_id);
    showNote(data);
  } catch (_err) {
    showProblem("The note did not come back in time. Try again.");
  } finally {
    busy = false;
    refreshChips();
  }
}

async function boot() {
  loadProfile();
  document.querySelectorAll("input").forEach((input) => {
    input.addEventListener("change", saveProfile);
    input.addEventListener("input", saveProfile);
  });
  cookButton.addEventListener("click", () => ask(false));
  anotherButton.addEventListener("click", () => ask(true));
  try {
    const response = await fetch("/api/catalog");
    if (!response.ok) throw new Error("catalog");
    const data = await response.json();
    renderBoard(data.ingredients);
  } catch (_err) {
    document.querySelector("#board-error").hidden = false;
    document.querySelector("#board-error").textContent = "The fridge list did not load. Refresh the page.";
  }
  refreshChips();
}

setNoteEmpty();
boot();
