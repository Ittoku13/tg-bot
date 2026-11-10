const tg = window.Telegram.WebApp;
tg.expand();

const $ = (id) => document.getElementById(id);
const status = (msg) => { $("status").textContent = msg; };

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg.initData,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

let state = null;

function fill(state) {
  const s = state.settings;
  $("role").value = s.role_name;
  $("pick_time").value = s.pick_time;
  $("auto_pick").checked = s.auto_pick_enabled;
  $("exclude_last").checked = s.exclude_last;
  $("mock_chance").value = s.mock_chance;
  $("mock_cooldown").value = s.mock_cooldown_min;
  $("mock_mode").value = s.mock_mode;
  $("char-clean").classList.toggle("active", s.character === "clean");
  $("char-adult").classList.toggle("active", s.character === "adult");
  $("rating").textContent = state.rating_top || "Пока пусто";
  renderTargets(state);
  $("targets_block").hidden = s.mock_mode !== "targets";
}

function selectedTargets() {
  return [...document.querySelectorAll("#targets_list input:checked")]
    .map((cb) => Number(cb.value));
}

function renderTargets(state) {
  const chosen = new Set(state.mock_targets);
  const filter = $("targets_search").value.toLowerCase();
  const list = $("targets_list");
  list.innerHTML = "";
  for (const u of state.known_users) {
    const name = (u.display_name + (u.username ? " @" + u.username : "")).toLowerCase();
    if (filter && !name.includes(filter)) continue;
    const label = document.createElement("label");
    label.className = "check";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = u.user_id;
    cb.checked = chosen.has(u.user_id);
    label.append(cb, " " + u.display_name + (u.username ? " (@" + u.username + ")" : ""));
    list.append(label);
  }
}

async function load() {
  state = await api("/api/state");
  fill(state);
}

async function save() {
  await api("/api/role", { method: "POST", body: JSON.stringify({ role_name: $("role").value }) });
  await api("/api/pick_time", { method: "POST", body: JSON.stringify({ pick_time: $("pick_time").value }) });
  await api("/api/auto_pick", { method: "POST", body: JSON.stringify({ enabled: $("auto_pick").checked }) });
  await api("/api/exclude_last", { method: "POST", body: JSON.stringify({ enabled: $("exclude_last").checked }) });
  await api("/api/mock", {
    method: "POST",
    body: JSON.stringify({
      mock_chance: Number($("mock_chance").value),
      mock_cooldown_min: Number($("mock_cooldown").value),
      mock_mode: $("mock_mode").value,
    }),
  });
  if ($("mock_mode").value === "targets") {
    await api("/api/mock_targets", { method: "POST", body: JSON.stringify({ user_ids: selectedTargets() }) });
  }
  status("Сохранено");
  await load();
}

async function setCharacter(character) {
  await api("/api/character", { method: "POST", body: JSON.stringify({ character }) });
  status("Характер: " + character);
  await load();
}

$("save").onclick = () => save().catch((e) => status("Ошибка: " + e.message));
$("char-clean").onclick = () => setCharacter("clean").catch((e) => status("Ошибка: " + e.message));
$("char-adult").onclick = () => setCharacter("adult").catch((e) => status("Ошибка: " + e.message));
$("mock_mode").onchange = () => { $("targets_block").hidden = $("mock_mode").value !== "targets"; };
$("targets_search").oninput = () => renderTargets(state);
const resetRating = async () => {
  if (!confirm("Сбросить весь рейтинг? Это не отменить.")) return;
  await api("/api/reset_rating", { method: "POST" });
  status("Рейтинг сброшен");
  await load();
};
$("reset_rating").onclick = () => resetRating().catch((e) => status("Ошибка: " + e.message));

load().catch((e) => status("Ошибка загрузки: " + e.message));
