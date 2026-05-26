/* =============================================================
   Pebble Garden — Game Dashboard Logic
   ============================================================= */

const WS_URL = "ws://localhost:8765";

// ── Translations ─────────────────────────────────────────────
const STRINGS = {
  zh: {
    title:          "🌸 卵石花园",
    noPods:         "未连接设备",
    pods:           (n) => `已连接 ${n} 个设备`,
    progress:       (pct) => `花园：${pct}%`,
    badgeWaiting:   "准备好了",
    badgePlaying:   "生长中！",
    badgeWon:       "全开了！",
    waitingTitle:   "🌱 卵石花园",
    waitingSub:     "拿起您的器材，准备开始！",
    btnStart:       "开始",
    winTitle:       "🌸 全部盛开！🌸",
    winSub:         "太棒了 — 花园完成了！",
    btnReset:       "再玩一次",
    facilitator:    "▶ 开始",
    langBtn:        "EN",
  },
  en: {
    title:          "🌸 Pebble Garden",
    noPods:         "No pods connected",
    pods:           (n) => `${n} pod${n !== 1 ? "s" : ""} connected`,
    progress:       (pct) => `Garden: ${pct}%`,
    badgeWaiting:   "Ready",
    badgePlaying:   "Growing!",
    badgeWon:       "Full Bloom!",
    waitingTitle:   "🌱 Pebble Garden",
    waitingSub:     "Pick up your pods and get ready to grow!",
    btnStart:       "Start Session",
    winTitle:       "🌸 Full Bloom! 🌸",
    winSub:         "Amazing work — the garden is complete!",
    btnReset:       "Play Again",
    facilitator:    "▶ Start session",
    langBtn:        "中文",
  },
};

let lang = "en";

// ── Flower configuration ─────────────────────────────────────
const PETAL_COLORS = [
  "#FF5FA8", // deep pink
  "#CC66DD", // orchid purple
  "#FF7030", // vivid orange
  "#FFD000", // golden yellow
  "#8855CC", // violet
  "#FF3D6A", // hot coral
];
// Varied stem heights (px) for a natural, staggered look — 20 flowers
const STEM_HEIGHTS = [
  195, 235, 210, 260, 230, 200, 250, 220, 245, 205,
  265, 225, 215, 255, 240, 208, 270, 232, 218, 248,
];
const NUM_PETALS   = 8; // 8 petals = fuller, more visible flower

// ── Background tree configuration ────────────────────────────
// left: CSS left value, scale: visual size (smaller = farther away)
const TREE_DEFS = [
  { left: "3%",  scale: 0.52, w1: 105, h1: 68, w2: 80, h2: 60, w3: 56, h3: 50, tw: 13, th: 52 },
  { left: "15%", scale: 0.74, w1: 148, h1: 92, w2: 112, h2: 80, w3: 78, h3: 68, tw: 18, th: 70 },
  { left: "30%", scale: 0.62, w1: 124, h1: 78, w2: 95, h2: 68, w3: 66, h3: 58, tw: 15, th: 60 },
  { left: "50%", scale: 0.68, w1: 135, h1: 85, w2: 103, h2: 74, w3: 72, h3: 63, tw: 16, th: 65 },
  { left: "68%", scale: 0.78, w1: 155, h1: 96, w2: 118, h2: 84, w3: 82, h3: 70, tw: 19, th: 74 },
  { left: "82%", scale: 0.60, w1: 116, h1: 73, w2: 89, h2: 64, w3: 62, h3: 54, tw: 14, th: 56 },
  { left: "93%", scale: 0.55, w1: 108, h1: 68, w2: 82, h2: 59, w3: 57, h3: 50, tw: 13, th: 52 },
];

// ── State ────────────────────────────────────────────────────
let socket       = null;
let lastPhase    = null;
let lastPodCount = null;
let lastProgress = null;
let plantEls     = [];

// ── Bootstrap ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  buildTrees();
  buildGarden();
  attachButtons();
  connect();
});

// ── Language toggle ──────────────────────────────────────────
function t(key, ...args) {
  const val = STRINGS[lang][key];
  return typeof val === "function" ? val(...args) : val;
}

function applyLang() {
  document.getElementById("title").textContent          = t("title");
  document.getElementById("waiting-title").textContent  = t("waitingTitle");
  document.getElementById("waiting-sub").textContent    = t("waitingSub");
  document.getElementById("btn-start").textContent      = t("btnStart");
  document.getElementById("win-title").textContent      = t("winTitle");
  document.getElementById("win-sub").textContent        = t("winSub");
  document.getElementById("btn-reset").textContent      = t("btnReset");
  document.getElementById("facilitator-start").textContent = t("facilitator");
  document.getElementById("lang-toggle").textContent    = t("langBtn");
  document.documentElement.lang                         = lang;

  // Re-render dynamic strings using last known state
  if (lastPodCount !== null) updatePodCount(lastPodCount);
  if (lastProgress  !== null) updateProgress(lastProgress);
  if (lastPhase     !== null) updateBadge(lastPhase);
}

// ── Build background trees ────────────────────────────────────
function buildTrees() {
  const container = document.getElementById("trees-bg");
  container.innerHTML = "";
  treeEls = [];

  TREE_DEFS.forEach((def, i) => {
    // Outer wrapper handles position + size scale
    const wrap = document.createElement("div");
    wrap.className = "tree-wrap";
    wrap.style.left = def.left;
    wrap.style.transform = `scale(${def.scale})`;

    // Inner tree element handles growth animation via --tree-growth
    const tree = document.createElement("div");
    tree.className = "tree";
    tree.id = `tree-${i}`;

    // Canopy (three stacked oval layers, bottom-to-top)
    const canopy = document.createElement("div");
    canopy.className = "tree-canopy";

    const l1 = document.createElement("div");
    l1.className = "canopy-l1";
    l1.style.width  = def.w1 + "px";
    l1.style.height = def.h1 + "px";

    const l2 = document.createElement("div");
    l2.className = "canopy-l2";
    l2.style.width  = def.w2 + "px";
    l2.style.height = def.h2 + "px";

    const l3 = document.createElement("div");
    l3.className = "canopy-l3";
    l3.style.width  = def.w3 + "px";
    l3.style.height = def.h3 + "px";

    // Append layers: column-reverse means l1 (bottom/widest) renders at bottom
    canopy.appendChild(l1);
    canopy.appendChild(l2);
    canopy.appendChild(l3);

    // Trunk
    const trunk = document.createElement("div");
    trunk.className = "tree-trunk";
    trunk.style.width  = def.tw + "px";
    trunk.style.height = def.th + "px";

    tree.appendChild(canopy);
    tree.appendChild(trunk);
    wrap.appendChild(tree);
    container.appendChild(wrap);
    // Trees are static background decoration — always fully visible
    tree.style.setProperty("--tree-growth", "1");
  });
}

// ── Build foreground flowers ──────────────────────────────────
function buildGarden() {
  const garden = document.getElementById("garden");
  garden.innerHTML = "";
  plantEls = [];

  STEM_HEIGHTS.forEach((height, i) => {
    const color = PETAL_COLORS[i % PETAL_COLORS.length];

    const plant = document.createElement("div");
    plant.className = "plant";
    plant.id = `plant-${i}`;
    plant.style.setProperty("--petal",  color);
    plant.style.setProperty("--h",      height + "px");
    plant.style.setProperty("--growth", "0");

    // Flower head
    const head = document.createElement("div");
    head.className = "flower-head";

    // Inner wrapper (scale + sway are applied here, not on head)
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

    // Stem + leaves
    const stem = document.createElement("div");
    stem.className = "stem";
    const leafL = document.createElement("div"); leafL.className = "leaf l";
    const leafR = document.createElement("div"); leafR.className = "leaf r";
    stem.appendChild(leafL);
    stem.appendChild(leafR);

    plant.appendChild(head);
    plant.appendChild(stem);
    garden.appendChild(plant);
    plantEls.push(plant);
  });
}

// ── WebSocket ────────────────────────────────────────────────
function connect() {
  setConnDot(false);
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    setConnDot(true);
    console.log("[WS] connected");
  };

  socket.onmessage = (evt) => {
    try { updateGame(JSON.parse(evt.data)); }
    catch (e) { console.warn("[WS] bad message", e); }
  };

  socket.onclose = () => {
    setConnDot(false);
    setTimeout(connect, 2000);
  };

  socket.onerror = () => socket.close();
}

function sendAction(action) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ action }));
  }
}

// ── Main update ──────────────────────────────────────────────
function updateGame(state) {
  const { phase, progress, num_devices, plants } = state;
  updateProgress(progress);
  updatePlants(plants);
  updatePodCount(num_devices);
  updatePhaseUI(phase, progress);
}

// ── Progress bar ─────────────────────────────────────────────
function updateProgress(p) {
  lastProgress = p;
  const pct = Math.round(p * 100);
  document.getElementById("progress-fill").style.width  = pct + "%";
  document.getElementById("progress-label").textContent = t("progress", pct);
}

// ── Flowers ──────────────────────────────────────────────────
function updatePlants(plants) {
  if (!plants) return;
  plants.forEach(({ id, growth }) => {
    const el = plantEls[id];
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

// ── Badge only (called on lang switch too) ────────────────────
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
function updatePhaseUI(phase, progress) {
  const phaseChanged = phase !== lastPhase;
  lastPhase = phase;
  updateBadge(phase);

  if (!phaseChanged) return;

  const waiting = document.getElementById("waiting-overlay");
  const win     = document.getElementById("win-overlay");

  switch (phase) {
    case "waiting":
      waiting.classList.remove("hidden");
      win.classList.remove("visible");
      break;
    case "playing":
      waiting.classList.add("hidden");
      win.classList.remove("visible");
      break;
    case "won":
      waiting.classList.add("hidden");
      win.classList.add("visible");
      launchConfetti();
      break;
  }
}

// ── Buttons ──────────────────────────────────────────────────
function attachButtons() {
  document.getElementById("btn-start").addEventListener("click", () => sendAction("start"));
  document.getElementById("btn-reset").addEventListener("click", () => sendAction("reset"));
  document.getElementById("facilitator-start").addEventListener("click", () => sendAction("start"));
  document.getElementById("lang-toggle").addEventListener("click", () => {
    lang = lang === "zh" ? "en" : "zh";
    applyLang();
  });
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
