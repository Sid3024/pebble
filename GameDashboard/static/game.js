/* =============================================================
   Pebble Garden — Game Dashboard Logic
   ============================================================= */

const WS_URL = "ws://localhost:8765";

// ── Translations ─────────────────────────────────────────────
const STRINGS = {
  en: {
    title:            "🌸 Pebble Garden",
    noPods:           "No pods connected",
    pods:             (n) => `${n} pod${n !== 1 ? "s" : ""} connected`,
    progress:         (pct) => `Garden: ${pct}%`,
    teamProgress:     (pct) => `${pct}%`,
    badgeWaiting:     "Ready",
    badgePlaying:     "Growing!",
    badgeWon:         "Full Bloom!",
    waitingTitle:     "🌱 Pebble Garden",
    waitingSub:       "Pick up your pods and get ready to grow!",
    modeSingle:       "Single Team",
    modeCompetitive:  "Multiplayer",
    btnStart:         "Start Session",
    winTitle:         "🌸 Full Bloom! 🌸",
    winSub:           "Amazing work — the garden is complete!",
    teamWinsTitle:    (n) => `🏆 Team ${n} Wins! 🏆`,
    teamWinsSub:      (n) => `Congratulations Team ${n} — garden in full bloom!`,
    btnReset:         "Play Again",
    team:             (n) => `Team ${n}`,
    facilitator:      "▶ Start session",
    langBtn:          "中文",
  },
  zh: {
    title:            "🌸 卵石花园",
    noPods:           "未连接设备",
    pods:             (n) => `已连接 ${n} 个设备`,
    progress:         (pct) => `花园：${pct}%`,
    teamProgress:     (pct) => `${pct}%`,
    badgeWaiting:     "准备好了",
    badgePlaying:     "生长中！",
    badgeWon:         "全开了！",
    waitingTitle:     "🌱 卵石花园",
    waitingSub:       "拿起您的器材，准备开始！",
    modeSingle:       "单队模式",
    modeCompetitive:  "多人模式",
    btnStart:         "开始",
    winTitle:         "🌸 全部盛开！🌸",
    winSub:           "太棒了 — 花园完成了！",
    teamWinsTitle:    (n) => `🏆 队伍${["一","二"][n-1] || n}获胜！🏆`,
    teamWinsSub:      (n) => `恭喜队伍${["一","二"][n-1] || n} — 花园全部盛开！`,
    btnReset:         "再玩一次",
    team:             (n) => `队伍${["一","二"][n-1] || n}`,
    facilitator:      "▶ 开始",
    langBtn:          "EN",
  },
};

let lang = "en";

function t(key, ...args) {
  const val = STRINGS[lang][key];
  return typeof val === "function" ? val(...args) : val;
}

// ── Flower configuration ─────────────────────────────────────
const PETAL_COLORS = [
  "#FF5FA8", "#CC66DD", "#FF7030", "#FFD000", "#8855CC", "#FF3D6A",
];
const STEM_HEIGHTS = [
  195, 235, 210, 260, 230, 200, 250, 220, 245, 205,
  265, 225, 215, 255, 240, 208, 270, 232, 218, 248,
];
const NUM_PETALS = 8;

// ── Background tree configuration ────────────────────────────
const TREE_DEFS = [
  { left: "3%",  scale: 0.52, w1: 105, h1: 68, w2: 80,  h2: 60, w3: 56, h3: 50, tw: 13, th: 52 },
  { left: "15%", scale: 0.74, w1: 148, h1: 92, w2: 112, h2: 80, w3: 78, h3: 68, tw: 18, th: 70 },
  { left: "30%", scale: 0.62, w1: 124, h1: 78, w2: 95,  h2: 68, w3: 66, h3: 58, tw: 15, th: 60 },
  { left: "50%", scale: 0.68, w1: 135, h1: 85, w2: 103, h2: 74, w3: 72, h3: 63, tw: 16, th: 65 },
  { left: "68%", scale: 0.78, w1: 155, h1: 96, w2: 118, h2: 84, w3: 82, h3: 70, tw: 19, th: 74 },
  { left: "82%", scale: 0.60, w1: 116, h1: 73, w2: 89,  h2: 64, w3: 62, h3: 54, tw: 14, th: 56 },
  { left: "93%", scale: 0.55, w1: 108, h1: 68, w2: 82,  h2: 59, w3: 57, h3: 50, tw: 13, th: 52 },
];

// ── State ────────────────────────────────────────────────────
let socket        = null;
let lastPhase     = null;
let lastMode      = null;
let lastPodCount  = null;
let lastProgress  = null;
let selectedMode  = "single";   // user's choice in waiting overlay

let plantEls      = [];         // single mode
let teamPlantEls  = [[], []];   // competitive mode, indexed by team id

// ── Bootstrap ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  buildTrees();
  plantEls = buildGarden("garden", 1.0);
  teamPlantEls[0] = buildGarden("garden-0", 0.62);
  teamPlantEls[1] = buildGarden("garden-1", 0.62);
  attachButtons();
  connect();
});

// ── Language toggle ──────────────────────────────────────────
function applyLang() {
  document.getElementById("title").textContent                = t("title");
  document.getElementById("waiting-title").textContent        = t("waitingTitle");
  document.getElementById("waiting-sub").textContent          = t("waitingSub");
  document.getElementById("btn-start").textContent            = t("btnStart");
  document.getElementById("btn-mode-single").textContent      = t("modeSingle");
  document.getElementById("btn-mode-competitive").textContent = t("modeCompetitive");
  document.getElementById("win-sub").textContent              = t("winSub");
  document.getElementById("btn-reset").textContent            = t("btnReset");
  document.getElementById("facilitator-start").textContent    = t("facilitator");
  document.getElementById("lang-toggle").textContent          = t("langBtn");
  document.documentElement.lang                               = lang;

  // Update team labels
  [0, 1].forEach(i => {
    const el = document.getElementById(`team-label-${i}`);
    if (el) el.textContent = t("team", i + 1);
  });

  // Re-render dynamic strings using last known values
  if (lastPodCount !== null) updatePodCount(lastPodCount);
  if (lastProgress  !== null) updateProgress(lastProgress);
  if (lastPhase     !== null) updateBadge(lastPhase);

  // Re-render win title if win overlay is visible
  if (lastPhase === "won") {
    const isCompetitive = lastMode === "competitive";
    // winner index is stored on the overlay element
    const winOverlay = document.getElementById("win-overlay");
    const winner = winOverlay.dataset.winner;
    if (isCompetitive && winner !== undefined) {
      document.getElementById("win-title").textContent = t("teamWinsTitle", parseInt(winner) + 1);
      document.getElementById("win-sub").textContent   = t("teamWinsSub",   parseInt(winner) + 1);
    } else {
      document.getElementById("win-title").textContent = t("winTitle");
      document.getElementById("win-sub").textContent   = t("winSub");
    }
  }
}

// ── Build background trees ────────────────────────────────────
function buildTrees() {
  const container = document.getElementById("trees-bg");
  container.innerHTML = "";

  TREE_DEFS.forEach((def, i) => {
    const wrap = document.createElement("div");
    wrap.className = "tree-wrap";
    wrap.style.left = def.left;
    wrap.style.transform = `scale(${def.scale})`;

    const tree = document.createElement("div");
    tree.className = "tree";
    tree.id = `tree-${i}`;

    const canopy = document.createElement("div");
    canopy.className = "tree-canopy";

    ["l1", "l2", "l3"].forEach((cls, li) => {
      const layer = document.createElement("div");
      layer.className = `canopy-${cls}`;
      const w = def[`w${li+1}`], h = def[`h${li+1}`];
      layer.style.width  = w + "px";
      layer.style.height = h + "px";
      canopy.appendChild(layer);
    });

    const trunk = document.createElement("div");
    trunk.className = "tree-trunk";
    trunk.style.width  = def.tw + "px";
    trunk.style.height = def.th + "px";

    tree.appendChild(canopy);
    tree.appendChild(trunk);
    wrap.appendChild(tree);
    container.appendChild(wrap);
    tree.style.setProperty("--tree-growth", "1");
  });
}

// ── Build a flower garden ─────────────────────────────────────
// scale: 1.0 for single mode, ~0.62 for competitive (half-width panels)
function buildGarden(containerId, scale) {
  const garden = document.getElementById(containerId);
  if (!garden) return [];
  garden.innerHTML = "";
  const els = [];

  STEM_HEIGHTS.forEach((height, i) => {
    const color = PETAL_COLORS[i % PETAL_COLORS.length];

    const plant = document.createElement("div");
    plant.className = "plant";
    plant.id = `${containerId}-plant-${i}`;
    plant.style.setProperty("--petal",    color);
    plant.style.setProperty("--h",        Math.round(height * scale) + "px");
    plant.style.setProperty("--ph",       Math.round(380    * scale) + "px");
    plant.style.setProperty("--head-size",Math.round(100    * scale) + "px");
    plant.style.setProperty("--petal-w",  Math.round(24     * scale) + "px");
    plant.style.setProperty("--petal-h",  Math.round(40     * scale) + "px");
    plant.style.setProperty("--center-sz",Math.round(26     * scale) + "px");
    plant.style.setProperty("--growth",   "0");

    const head = document.createElement("div");
    head.className = "flower-head";

    const inner = document.createElement("div");
    inner.className = "flower-inner";

    for (let p = 0; p < NUM_PETALS; p++) {
      const petal = document.createElement("div");
      petal.className = "petal";
      petal.style.setProperty("--angle", (p * (360 / NUM_PETALS)).toString());
      inner.appendChild(petal);
    }

    const center = document.createElement("div");
    center.className = "flower-center";
    inner.appendChild(center);
    head.appendChild(inner);

    const stem = document.createElement("div");
    stem.className = "stem";
    const leafL = document.createElement("div"); leafL.className = "leaf l";
    const leafR = document.createElement("div"); leafR.className = "leaf r";
    stem.appendChild(leafL);
    stem.appendChild(leafR);

    plant.appendChild(head);
    plant.appendChild(stem);
    garden.appendChild(plant);
    els.push(plant);
  });

  return els;
}

// ── WebSocket ────────────────────────────────────────────────
function connect() {
  setConnDot(false);
  socket = new WebSocket(WS_URL);
  socket.onopen    = () => { setConnDot(true); console.log("[WS] connected"); };
  socket.onmessage = (evt) => {
    try { updateGame(JSON.parse(evt.data)); }
    catch (e) { console.warn("[WS] bad message", e); }
  };
  socket.onclose = () => { setConnDot(false); setTimeout(connect, 2000); };
  socket.onerror = () => socket.close();
}

function sendAction(action, extra = {}) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ action, ...extra }));
  }
}

// ── Main update ──────────────────────────────────────────────
function updateGame(state) {
  const mode   = state.mode  || "single";
  const phase  = state.phase || "waiting";
  const winner = state.winner ?? null;

  lastMode = mode;

  // Pod count
  const totalDevices = mode === "competitive"
    ? (state.teams || []).reduce((s, tm) => s + (tm.num_devices || 0), 0)
    : (state.num_devices || 0);
  updatePodCount(totalDevices);

  // Switch layout
  document.getElementById("scene").classList.toggle("competitive", mode === "competitive");

  // Phase UI (overlays + badge)
  updatePhaseUI(phase, mode, winner);

  // Garden / progress
  if (mode === "competitive") {
    (state.teams || []).forEach(team => updateTeam(team));
  } else {
    updateProgress(state.progress || 0);
    updatePlants(state.plants, plantEls);
  }
}

// ── Progress bar (single mode) ────────────────────────────────
function updateProgress(p) {
  lastProgress = p;
  const pct = Math.round(p * 100);
  document.getElementById("progress-fill").style.width   = pct + "%";
  document.getElementById("progress-label").textContent  = t("progress", pct);
}

// ── Flowers ──────────────────────────────────────────────────
function updatePlants(plants, els) {
  if (!plants || !els) return;
  plants.forEach(({ id, growth }) => {
    const el = els[id];
    if (!el) return;
    el.style.setProperty("--growth", growth.toFixed(4));
    el.classList.toggle("bloomed", growth >= 0.98);
  });
}

// ── Pod count ─────────────────────────────────────────────────
function updatePodCount(n) {
  lastPodCount = n;
  document.getElementById("pod-count").textContent =
    n === 0 ? t("noPods") : t("pods", n);
}

// ── Competitive team update ───────────────────────────────────
function updateTeam(team) {
  const i   = team.id;
  const pct = Math.round((team.progress || 0) * 100);
  document.getElementById(`team-progress-fill-${i}`).style.width    = pct + "%";
  document.getElementById(`team-progress-label-${i}`).textContent   = t("teamProgress", pct);
  updatePlants(team.plants, teamPlantEls[i]);
}

// ── Badge ─────────────────────────────────────────────────────
function updateBadge(phase) {
  const badge = document.getElementById("status-badge");
  badge.className = "";
  switch (phase) {
    case "waiting": badge.textContent = t("badgeWaiting"); badge.classList.add("waiting"); break;
    case "playing": badge.textContent = t("badgePlaying"); badge.classList.add("active");  break;
    case "won":     badge.textContent = t("badgeWon");     badge.classList.add("won");     break;
  }
}

// ── Phase / overlays ─────────────────────────────────────────
function updatePhaseUI(phase, mode, winner) {
  updateBadge(phase);

  const waiting    = document.getElementById("waiting-overlay");
  const win        = document.getElementById("win-overlay");
  const phaseChanged = phase !== lastPhase || mode !== lastMode;
  lastPhase = phase;

  switch (phase) {
    case "waiting":
      waiting.classList.remove("hidden");
      win.classList.remove("visible");
      delete win.dataset.winner;
      delete win.dataset.confettiDone;
      break;

    case "playing":
      waiting.classList.add("hidden");
      win.classList.remove("visible");
      break;

    case "won":
      waiting.classList.add("hidden");
      if (!win.classList.contains("visible") || phaseChanged) {
        // Set win overlay text
        if (mode === "competitive" && winner !== null) {
          win.dataset.winner = winner;
          document.getElementById("win-title").textContent = t("teamWinsTitle", winner + 1);
          document.getElementById("win-sub").textContent   = t("teamWinsSub",   winner + 1);
        } else {
          delete win.dataset.winner;
          document.getElementById("win-title").textContent = t("winTitle");
          document.getElementById("win-sub").textContent   = t("winSub");
        }
        win.classList.add("visible");
        if (!win.dataset.confettiDone) {
          launchConfetti();
          win.dataset.confettiDone = "1";
        }
      }
      break;
  }
}

// ── Buttons ──────────────────────────────────────────────────
function attachButtons() {
  document.getElementById("btn-start").addEventListener("click", () =>
    sendAction("start", { mode: selectedMode })
  );
  document.getElementById("btn-reset").addEventListener("click", () =>
    sendAction("reset")
  );
  document.getElementById("facilitator-start").addEventListener("click", () =>
    sendAction("start", { mode: selectedMode })
  );

  // Mode selector
  document.getElementById("btn-mode-single").addEventListener("click", () =>
    selectMode("single")
  );
  document.getElementById("btn-mode-competitive").addEventListener("click", () =>
    selectMode("competitive")
  );

  // Language toggle
  document.getElementById("lang-toggle").addEventListener("click", () => {
    lang = lang === "en" ? "zh" : "en";
    applyLang();
  });
}

function selectMode(mode) {
  selectedMode = mode;
  document.getElementById("btn-mode-single").classList.toggle("active", mode === "single");
  document.getElementById("btn-mode-competitive").classList.toggle("active", mode === "competitive");
}

// ── Confetti ─────────────────────────────────────────────────
const CONFETTI_COLORS = ["#ff69b4","#ffd700","#78e060","#cc66dd","#ff7030","#87ceeb"];

function launchConfetti() {
  for (let i = 0; i < 100; i++) {
    const el = document.createElement("div");
    el.className = "confetti";
    el.style.setProperty("--dur",   (2 + Math.random() * 2.5).toFixed(2) + "s");
    el.style.setProperty("--delay", (Math.random() * 2.0).toFixed(2)     + "s");
    el.style.left        = Math.random() * 100 + "vw";
    el.style.background  = CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)];
    el.style.borderRadius = Math.random() > 0.5 ? "50%" : "3px";
    document.body.appendChild(el);
    el.addEventListener("animationend", () => el.remove());
  }
}

// ── Connection dot ───────────────────────────────────────────
function setConnDot(connected) {
  document.getElementById("conn-dot").className = connected ? "connected" : "disconnected";
}
