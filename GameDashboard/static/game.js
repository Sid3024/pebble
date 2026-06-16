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
    score:            (s) => `Score: ${s} pts`,
    scoreSimilarity:  (s, p) => `Score: ${s} pts · Match: ${p}%`,
    teamScore:        (s) => `${s} pts`,
    teamScoreSimilarity: (s, p) => `${s} pts · ${p}% match`,
    durationLabel:    "Game Duration",
    durMin:           (s) => s < 60 ? `${s} sec` : `${s/60} min`,
    badgeWaiting:     "Ready",
    badgePlaying:     "Growing!",
    badgeWon:         "Time's Up!",
    badgeSelecting:   "Picking Teams",
    badgeInstructor:  "Pick Instructor",
    waitingTitle:     "🌱 Pebble Garden",
    waitingSub:       "Pick up your pods and get ready to grow!",
    modeSingle:       "Single Team",
    modeCompetitive:  "Multiplayer",
    btnStart:         "Start Session",
    winTitle:         "🌸 Time's Up! 🌸",
    winSub:           (s) => `Final score: ${s} pts — amazing work!`,
    teamWinsTitle:    (n) => `🏆 Team ${n} Wins! 🏆`,
    teamWinsSub:      (s0, s1) => `Team 1: ${s0} pts\nTeam 2: ${s1} pts`,
    teamTieTitle:     "🌸 It's a Tie! 🌸",
    teamTieSub:       (s0, s1) => `Team 1: ${s0} pts\nTeam 2: ${s1} pts`,
    btnReset:         "Play Again",
    team:             (n) => `Team ${n}`,
    facilitator:      "▶ Start session",
    langBtn:          "中文",
    tsTitle:          (n) => `Team ${n} — Join Up! ${["🔵","🔴"][n-1]}`,
    tsSub:            (n) => `Shake your weights to join Team ${n}!`,
    tsShakingIn:      "shaking in ✓",
    tsWaiting:        "waiting…",
    tsLocked:         "locked in ✓",
    tsFull:           "Team Full! ✓",
    tsJoined:         "joined",
    tsNextTeam:       "Next: Team 2 →",
    tsBeginGame:      "Let's Play! 🌸",
    tsPeople:         (n) => n === 1 ? "1 person" : `${n} people`,
    instructorTitle:  "Class Setup",
    instructorSub:    "Instructor, shake your pod to begin.",
    instructorCard:   "Instructor",
    instructorWaiting:"waiting for shake",
    instructorReady:  "leading ✓",
    instructorNext:   "Next",
  },
  zh: {
    title:            "🌸 卵石花园",
    noPods:           "未连接设备",
    pods:             (n) => `已连接 ${n} 个设备`,
    score:            (s) => `得分：${s} 分`,
    scoreSimilarity:  (s, p) => `得分：${s} 分 · 匹配：${p}%`,
    teamScore:        (s) => `${s} 分`,
    teamScoreSimilarity: (s, p) => `${s} 分 · 匹配 ${p}%`,
    durationLabel:    "游戏时长",
    durMin:           (s) => s < 60 ? `${s} 秒` : `${s/60} 分钟`,
    badgeWaiting:     "准备好了",
    badgePlaying:     "生长中！",
    badgeWon:         "时间到！",
    badgeSelecting:   "选择队伍",
    badgeInstructor:  "选择教练",
    waitingTitle:     "🌱 卵石花园",
    waitingSub:       "拿起您的器材，准备开始！",
    modeSingle:       "单队模式",
    modeCompetitive:  "多人模式",
    btnStart:         "开始",
    winTitle:         "🌸 时间到！🌸",
    winSub:           (s) => `最终得分：${s} 分 — 太棒了！`,
    teamWinsTitle:    (n) => `🏆 队伍${["一","二"][n-1] || n}获胜！🏆`,
    teamWinsSub:      (s0, s1) => `队伍一：${s0} 分\n队伍二：${s1} 分`,
    teamTieTitle:     "🌸 平局！🌸",
    teamTieSub:       (s0, s1) => `队伍一：${s0} 分\n队伍二：${s1} 分`,
    btnReset:         "再玩一次",
    team:             (n) => `队伍${["一","二"][n-1] || n}`,
    facilitator:      "▶ 开始",
    langBtn:          "EN",
    tsTitle:          (n) => `队伍${["一","二"][n-1] || n} — 加入！${["🔵","🔴"][n-1]}`,
    tsSub:            (n) => `摇动器材加入队伍${["一","二"][n-1] || n}！`,
    tsShakingIn:      "已加入 ✓",
    tsWaiting:        "等待中…",
    tsLocked:         "已锁定 ✓",
    tsFull:           "队伍已满！✓",
    tsJoined:         "人已加入",
    tsNextTeam:       "下一队：队伍二 →",
    tsBeginGame:      "开始游戏！🌸",
    tsPeople:         (n) => `${n} 人`,
    instructorTitle:  "课程准备",
    instructorSub:    "教练，摇动设备开始。",
    instructorCard:   "教练",
    instructorWaiting:"等待摇动",
    instructorReady:  "引领中 ✓",
    instructorNext:   "下一步",
  },
};

let lang = "en";

function t(key, ...args) {
  const val = STRINGS[lang][key];
  return typeof val === "function" ? val(...args) : val;
}

// ── Flower sprites (from flower_sprites_v3.svg) ───────────────
// 10 colour variations: Sunny, Blush, Lavender, Coral, Sky,
//                       Mint,  Peach, Crimson,  Violet, Butter
// ViewBox "-60 -80 120 290" captures full flower (petals at y≈-70,
// stem bottom at y≈200).  Stem is drawn first so petals sit on top.

function _makeFlower(pA, pB, ps, co, ci, cs) {
  const pts = Array.from({length:12}, (_,i) =>
    `<ellipse cx="0" cy="-44" rx="11" ry="26" fill="${i%2?pB:pA}" stroke="${ps}" stroke-width="1.6" transform="rotate(${i*30})"  />`
  ).join('');
  return `<rect x="-5" y="18" width="10" height="182" rx="5" fill="#5cb040" stroke="#2a6020" stroke-width="1.8"/>
<g transform="translate(-18,110) rotate(-40)"><ellipse cx="0" cy="0" rx="24" ry="11" fill="#6cc848" stroke="#2a6020" stroke-width="1.6"/></g>
<g transform="translate(18,130) rotate(40)"><ellipse cx="0" cy="0" rx="24" ry="11" fill="#6cc848" stroke="#2a6020" stroke-width="1.6"/></g>
${pts}
<circle cx="0" cy="0" r="21" fill="${co}" stroke="${cs}" stroke-width="2.2"/>
<circle cx="0" cy="0" r="13" fill="${ci}" stroke="${cs}" stroke-width="1.2"/>
<circle cx="-4" cy="-4" r="2.2" fill="#503020" opacity="0.6"/>
<circle cx="4"  cy="-2" r="1.8" fill="#503020" opacity="0.5"/>
<circle cx="0"  cy="5"  r="1.8" fill="#503020" opacity="0.5"/>`;
}

const FLOWER_TYPES = [
  { color:'#f5a800', svg:_makeFlower('#ffe040','#ffd828','#c89000','#f5a800','#ffc840','#a06000') }, // Sunny
  { color:'#e8507a', svg:_makeFlower('#ffb8cc','#ff90aa','#c04880','#e8507a','#ff80a0','#900040') }, // Blush
  { color:'#b880e0', svg:_makeFlower('#d4aaee','#b880e0','#7040b0','#f5c000','#ffe060','#a07000') }, // Lavender
  { color:'#ff6040', svg:_makeFlower('#ff8060','#ff5a30','#c04020','#fff0d0','#ffffff','#c06020') }, // Coral
  { color:'#70b8f0', svg:_makeFlower('#a8d8f8','#70b8f0','#3070c0','#f8e060','#fff5a0','#c09800') }, // Sky
  { color:'#70ddb8', svg:_makeFlower('#b0f0d8','#70ddb8','#208060','#f0f8f0','#ffffff','#208060') }, // Mint
  { color:'#ffb070', svg:_makeFlower('#ffd0a0','#ffb070','#d06820','#f07820','#ffa040','#904000') }, // Peach
  { color:'#e82030', svg:_makeFlower('#e82030','#b00018','#800010','#d0a000','#f0c820','#806000') }, // Crimson
  { color:'#9060d8', svg:_makeFlower('#9060d8','#6030b0','#400890','#c8e020','#e8f840','#607000') }, // Violet
  { color:'#f0e080', svg:_makeFlower('#fff8c0','#f0e080','#c09040','#c06818','#e08030','#804010') }, // Butter
];

// Flower display dimensions at scale=1.0
const FLOWER_W  = 80;          // px width
const FLOWER_H  = 210;         // px height (stem bottom → petal tips)
const FLOWER_VB = "-60 -80 120 290";

// Dummy placeholder kept to avoid breaking old references
const FLOWER_BASE_PX = FLOWER_W;


// Golden ratio positioning — beautiful spread, no clustering
const φ = 0.618033988749895;
// X: 8–92% — covers the full usable width of each garden panel
function flowerX(id) { return ((id * φ) % 1) * 84 + 8; }

// Y: 1–44% from the bottom of the garden container — spreads across the full height
// Uses a complementary golden-ratio multiplier so X and Y are uncorrelated
function flowerY(id) { return ((id * 0.381966 * 2.3) % 1) * 43 + 1; }


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
let socket           = null;
let lastPhase        = null;
let lastMode         = null;
let lastPodCount     = null;
let lastProgress     = null;
let selectedMode     = "single";
let selectedDuration = 60;
let lastTSCounts     = [-1, -1];
let lastStateTeams   = null;   // last competitive teams array (for win overlay)
let lastStateSingle  = null;   // last single state (for win overlay)

// Garden objects — el: DOM container, els: sparse array of plant elements, scale: size factor
const SINGLE_GARDEN = { el: null, els: [], scale: 1.0 };
const TEAM_GARDENS  = [
  { el: null, els: [], scale: 0.62 },
  { el: null, els: [], scale: 0.62 },
];

// ── Bootstrap ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  SINGLE_GARDEN.el   = document.getElementById("garden");
  TEAM_GARDENS[0].el = document.getElementById("garden-0");
  TEAM_GARDENS[1].el = document.getElementById("garden-1");
  attachButtons();
  connect();
});

function clearGarden(g) {
  if (g.el) g.el.innerHTML = "";
  g.els = [];
}
function clearAllGardens() {
  clearGarden(SINGLE_GARDEN);
  TEAM_GARDENS.forEach(g => clearGarden(g));
}

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

  // Update team labels (competitive game view)
  [0, 1].forEach(i => {
    const el = document.getElementById(`team-label-${i}`);
    if (el) el.textContent = t("team", i + 1);
  });

  // Duration selector
  document.getElementById("duration-label").textContent = t("durationLabel");
  document.querySelectorAll(".dur-btn").forEach(btn => {
    btn.textContent = t("durMin", parseInt(btn.dataset.secs));
  });

  // Team selection overlay strings
  document.getElementById("btn-confirm-instructor").textContent = t("instructorNext");
  document.getElementById("btn-next-team").textContent  = t("tsNextTeam");
  document.getElementById("btn-begin-game").textContent = t("tsBeginGame");
  const nameI = document.getElementById("ts-card-name-instructor");
  if (nameI) nameI.textContent = t("instructorCard");
  [0, 1].forEach(i => {
    const nameEl = document.getElementById(`ts-card-name-${i}`);
    if (nameEl) nameEl.textContent = t("team", i + 1);
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

// ── Spawn one flower into a garden container ──────────────────
function spawnFlower(gardenEl, id, scale) {
  const typeIndex = id % FLOWER_TYPES.length;
  const w = Math.round(FLOWER_W * scale);
  const h = Math.round(FLOWER_H * scale);

  const plant = document.createElement("div");
  plant.className = "plant";
  plant.style.left   = flowerX(id) + "%";
  plant.style.bottom = flowerY(id) + "%";   // vertical spread across garden
  plant.dataset.type = typeIndex;
  plant.dataset.h    = h;

  // Clip container starts at height 0; animated to h after insertion
  const clip = document.createElement("div");
  clip.className = "plant-clip";
  clip.style.cssText = `width:${w}px; height:0px; position:relative; overflow:hidden;`;

  // SVG anchored to bottom so stem appears first as clip grows
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", FLOWER_VB);
  svg.style.cssText =
    `width:${w}px; height:${h}px; position:absolute; bottom:0; display:block; overflow:visible;`;
  svg.innerHTML = FLOWER_TYPES[typeIndex].svg;

  clip.appendChild(svg);
  plant.appendChild(clip);
  gardenEl.appendChild(plant);
  return plant;
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
  const totalDevices = state.total_connected ?? (
    mode === "competitive"
      ? (state.teams || []).reduce((s, tm) => s + (tm.num_devices || 0), 0)
      : (state.num_devices || 0)
  );
  updatePodCount(totalDevices);

  if (phase === "instructor_select" || phase === "team_select") {
    updateSelectionOverlay(state);
    return;
  }

  // Hide team-select overlay if we've moved past it
  document.getElementById("team-select-overlay").classList.remove("visible");

  // Switch layout
  document.getElementById("scene").classList.toggle("competitive", mode === "competitive");

  // Phase UI (overlays + badge)
  updatePhaseUI(phase, mode, winner);

  // Timer
  updateTimer(state.time_remaining ?? 0, phase);

  // Cache for win overlay
  if (mode === "competitive") lastStateTeams  = state.teams || [];
  else                         lastStateSingle = state;

  // Garden / progress
  if (mode === "competitive") {
    (state.teams || []).forEach(team => updateTeam(team));
  } else {
    updateProgress(state.score, state.progress, state.similarity);
    updatePlants(state.plants, SINGLE_GARDEN);
  }
}

// ── Combined selection overlay (instructor → team 1 → team 2) ─
function updateSelectionOverlay(state) {
  const overlay = document.getElementById("team-select-overlay");
  overlay.classList.add("visible");
  document.getElementById("waiting-overlay").classList.add("hidden");
  document.getElementById("scene").classList.toggle("competitive", state.mode === "competitive");

  const phase = state.phase;
  const step  = state.team_select_step ?? 0;
  const teams = state.teams || [{id:0,num_devices:0},{id:1,num_devices:0}];
  const t0    = teams.find(tm => tm.id === 0) || {num_devices: 0, quota: null, locked: false};
  const t1    = teams.find(tm => tm.id === 1) || {num_devices: 0};
  const counts = [t0.num_devices || 0, t1.num_devices || 0];

  // Badge
  const badge = document.getElementById("status-badge");
  badge.className = "active";
  badge.textContent = phase === "instructor_select" ? t("badgeInstructor") : t("badgeSelecting");

  // Title / subtitle
  if (phase === "instructor_select") {
    document.getElementById("ts-title").textContent    = t("instructorTitle");
    document.getElementById("ts-subtitle").textContent = t("instructorSub");
  } else {
    document.getElementById("ts-title").textContent    = t("tsTitle", step + 1);
    document.getElementById("ts-subtitle").textContent = t("tsSub",   step + 1);
  }

  // ── Instructor card ───────────────────────────────────────
  const cardI  = document.getElementById("ts-card-instructor");
  const labelI = document.getElementById("ts-card-label-instructor");
  const countI = document.getElementById("ts-count-instructor");
  document.getElementById("ts-card-name-instructor").textContent = t("instructorCard");

  if (phase === "instructor_select") {
    if (state.instructor) {
      // Instructor locked in — waiting for facilitator to press Next
      cardI.className    = "ts-card ts-full";
      countI.textContent = "1";
      labelI.textContent = t("instructorReady");
    } else {
      cardI.className    = "ts-card ts-active ts-instructor-active";
      countI.textContent = "0";
      labelI.textContent = t("instructorWaiting");
    }
  } else {
    // team_select — instructor is confirmed, lock the card
    cardI.className    = "ts-card ts-full";
    countI.textContent = "1";
    labelI.textContent = t("instructorReady");
  }

  // Single mode: only the instructor needs to lock in — no teams.
  const isSingle = state.mode !== "competitive";
  document.getElementById("ts-cards").classList.toggle("ts-cards-single", isSingle);
  document.getElementById("ts-card-0").classList.toggle("hidden", isSingle);
  document.getElementById("ts-card-1").classList.toggle("hidden", isSingle);
  if (isSingle) {
    document.getElementById("btn-next-team").style.display  = "none";
    document.getElementById("btn-begin-game").style.display = "none";
    document.getElementById("btn-confirm-instructor").style.display =
      (phase === "instructor_select" && !!state.instructor) ? "" : "none";
    return;
  }

  // ── Team 1 card ───────────────────────────────────────────
  const card0  = document.getElementById("ts-card-0");
  const label0 = document.getElementById("ts-card-label-0");
  document.getElementById("ts-card-name-0").textContent = t("team", 1);

  // Animate count bump
  if (counts[0] !== lastTSCounts[0]) {
    lastTSCounts[0] = counts[0];
    const el = document.getElementById("ts-count-0");
    el.textContent = counts[0];
    el.classList.remove("ts-count-bump");
    void el.offsetWidth;
    el.classList.add("ts-count-bump");
  }

  if (phase === "instructor_select") {
    card0.className    = "ts-card ts-waiting";
    label0.textContent = t("tsWaiting");
  } else if (step > 0) {
    card0.className    = "ts-card ts-locked";
    label0.textContent = t("tsLocked");
  } else if (t0.locked) {
    card0.className    = "ts-card ts-full";
    label0.textContent = t("tsFull");
  } else {
    card0.className    = "ts-card ts-active";
    label0.textContent = t0.quota
      ? `${counts[0]} / ${t0.quota} ${t("tsJoined")}`
      : t("tsShakingIn");
  }

  // ── Team 2 card ───────────────────────────────────────────
  const card1  = document.getElementById("ts-card-1");
  const label1 = document.getElementById("ts-card-label-1");
  document.getElementById("ts-card-name-1").textContent = t("team", 2);

  // Animate count bump
  if (counts[1] !== lastTSCounts[1]) {
    lastTSCounts[1] = counts[1];
    const el = document.getElementById("ts-count-1");
    el.textContent = counts[1];
    el.classList.remove("ts-count-bump");
    void el.offsetWidth;
    el.classList.add("ts-count-bump");
  }

  if (phase === "instructor_select" || step === 0) {
    card1.className    = "ts-card ts-waiting";
    label1.textContent = t("tsWaiting");
  } else {
    card1.className    = "ts-card ts-active";
    label1.textContent = t("tsShakingIn");
  }

  // ── Buttons ───────────────────────────────────────────────
  // "Next" — confirm instructor, only once instructor has shaken in
  document.getElementById("btn-confirm-instructor").style.display =
    (phase === "instructor_select" && !!state.instructor) ? "" : "none";
  // "Next: Team 2" — only during team_select step 0
  document.getElementById("btn-next-team").style.display =
    (phase === "team_select" && step === 0) ? "" : "none";
  // "Let's Play" — only during team_select step 1
  document.getElementById("btn-begin-game").style.display =
    (phase === "team_select" && step === 1) ? "" : "none";
}

// ── Score display (single mode) ──────────────────────────────
function updateProgress(score, progress, similarity = null) {
  lastProgress = progress;
  const pct = Math.round((similarity ?? 0) * 100);
  document.getElementById("progress-label").textContent =
    similarity === null ? t("score", score ?? 0) : t("scoreSimilarity", score ?? 0, pct);
}

// ── Countdown timer ───────────────────────────────────────────
function updateTimer(timeRemaining, phase) {
  const el = document.getElementById("timer-display");
  if (phase !== "playing") {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  const secs  = Math.max(0, Math.ceil(timeRemaining));
  const m     = Math.floor(secs / 60);
  const s     = secs % 60;
  el.textContent = `⏱ ${m}:${s.toString().padStart(2, "0")}`;
  el.classList.toggle("timer-urgent", secs <= 10);
}

// ── Flowers ──────────────────────────────────────────────────
function updatePlants(plants, g) {
  if (!plants || !g || !g.el) return;
  plants.forEach(({ id, growth }) => {
    if (!g.els[id]) {
      const el   = spawnFlower(g.el, id, g.scale);
      g.els[id]  = el;
      const clip = el.querySelector(".plant-clip");
      const h    = parseInt(el.dataset.h);
      // Double rAF: browser must paint height:0 before we set the target height,
      // otherwise the CSS transition has no starting point and the flower just pops.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (clip) clip.style.height = h + "px";
        el.classList.toggle("bloomed", growth >= 0.98);
      }));
    } else {
      g.els[id].classList.toggle("bloomed", growth >= 0.98);
    }
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
  const i = team.id;
  const pct = Math.round((team.similarity ?? 0) * 100);
  document.getElementById(`team-score-label-${i}`).textContent =
    team.similarity === undefined ? t("teamScore", team.score ?? 0) : t("teamScoreSimilarity", team.score ?? 0, pct);
  updatePlants(team.plants, TEAM_GARDENS[i]);
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
      document.getElementById("team-select-overlay").classList.remove("visible");
      delete win.dataset.winner;
      delete win.dataset.confettiDone;
      lastTSCounts = [-1, -1];
      if (phaseChanged) clearAllGardens();
      break;

    case "playing":
      waiting.classList.add("hidden");
      win.classList.remove("visible");
      break;

    case "won":
      waiting.classList.add("hidden");
      if (!win.classList.contains("visible") || phaseChanged) {
        if (mode === "competitive") {
          const teams  = lastStateTeams || [];
          const s0     = teams.find(t => t.id === 0)?.score ?? 0;
          const s1     = teams.find(t => t.id === 1)?.score ?? 0;
          if (winner === null) {
            document.getElementById("win-title").textContent = t("teamTieTitle");
            document.getElementById("win-sub").textContent   = t("teamTieSub", s0, s1);
          } else {
            win.dataset.winner = winner;
            document.getElementById("win-title").textContent = t("teamWinsTitle", winner + 1);
            document.getElementById("win-sub").textContent   = t("teamWinsSub", s0, s1);
          }
        } else {
          const score = lastStateSingle?.score ?? 0;
          delete win.dataset.winner;
          document.getElementById("win-title").textContent = t("winTitle");
          document.getElementById("win-sub").textContent   = t("winSub", score);
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
    sendAction("start", { mode: selectedMode, duration: selectedDuration })
  );
  document.getElementById("btn-reset").addEventListener("click", () =>
    sendAction("reset")
  );
  document.getElementById("btn-confirm-instructor").addEventListener("click", () =>
    sendAction("confirm_instructor")
  );
  document.getElementById("btn-next-team").addEventListener("click", () =>
    sendAction("next_team")
  );
  document.getElementById("btn-begin-game").addEventListener("click", () =>
    sendAction("begin_game")
  );
  document.getElementById("facilitator-start").addEventListener("click", () =>
    sendAction("start", { mode: selectedMode, duration: selectedDuration })
  );

  // Mode selector
  document.getElementById("btn-mode-single").addEventListener("click", () =>
    selectMode("single")
  );
  document.getElementById("btn-mode-competitive").addEventListener("click", () =>
    selectMode("competitive")
  );

  // Duration selector
  document.querySelectorAll(".dur-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      selectedDuration = parseInt(btn.dataset.secs);
      document.querySelectorAll(".dur-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

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

// ── Fullscreen ────────────────────────────────────────────────
(function () {
  const btn = document.getElementById("btn-fullscreen");

  function isFs() { return !!document.fullscreenElement; }

  function update() {
    btn.textContent = isFs() ? "✕" : "⛶";
    btn.title       = isFs() ? "Exit fullscreen  (Esc)" : "Enter fullscreen";
  }

  function toggle() {
    if (isFs()) document.exitFullscreen();
    else        document.documentElement.requestFullscreen();
  }

  btn.addEventListener("click", toggle);

  // Esc is handled natively by the browser, but listen anyway to keep icon in sync
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isFs()) document.exitFullscreen();
  });

  document.addEventListener("fullscreenchange", update);
  update();
})();

// ── Connection dot ───────────────────────────────────────────
function setConnDot(connected) {
  document.getElementById("conn-dot").className = connected ? "connected" : "disconnected";
}
