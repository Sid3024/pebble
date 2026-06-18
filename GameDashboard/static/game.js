/* =============================================================
   Pebble Garden — Game Dashboard Logic
   =============================================================

   PURPOSE:
     This file contains ALL interactive logic for the Pebble Garden
     game dashboard. It manages:
       - WebSocket connection to the Python game server
       - Real-time game state rendering (flowers, scores, timer)
       - UI phase transitions (waiting -> team_select -> playing -> won)
       - SVG flower generation and growth animations
       - Bilingual text support (English / Chinese)
       - Facilitator button handlers (start, reset, mode, duration)
       - Confetti celebration animation
       - Fullscreen toggle

   HOW IT WORKS:
     On page load, the script connects to the WebSocket server at
     ws://localhost:8765. The server sends JSON game state messages
     every ~150ms. Each message triggers updateGame(), which:
       1. Determines the current mode (single vs competitive)
       2. Updates the pod count display
       3. Routes to the appropriate phase handler (waiting, team_select,
          playing, won)
       4. Updates flower gardens — spawning new SVG flowers and
          animating their growth via CSS clip-height transitions

   LIBRARIES / DEPENDENCIES:
     - No external JS libraries. Pure vanilla JavaScript.
     - Relies on the browser's native WebSocket API.
     - SVG flowers are generated entirely in code (no external SVGs).
     - CSS transitions in style.css handle all animations.

   KEY DESIGN DECISIONS:
     - Flowers use golden-ratio-based positioning (phi = 0.618...)
       to achieve a natural, evenly-spread distribution without
       grid patterns or random clustering.
     - Each flower is an SVG with 12 petal ellipses, a stem, two
       leaves, and a multi-layered center. 10 color variations.
     - Growth animation uses a "clip container" trick: an outer div
       starts at height 0 and transitions to full height, revealing
       the flower from stem-up. Double requestAnimationFrame ensures
       the browser paints the initial state before animating.
     - State diffing: only new flowers are spawned; existing ones
       are not re-created, just updated (bloomed class toggle).
     - The STRINGS object holds all UI text in both languages,
       with function values for parameterized strings.

   SECTIONS DEFINED:
     1. STRINGS / i18n — Translation tables and t() helper
     2. FLOWER_TYPES — SVG flower color definitions
     3. Positioning — Golden-ratio X/Y functions
     4. TREE_DEFS — Background tree configuration
     5. State variables — Game state tracking
     6. Bootstrap — DOMContentLoaded initialization
     7. Language toggle — applyLang() function
     8. Background trees — buildTrees() DOM construction
     9. Flower spawning — spawnFlower() SVG creation
    10. WebSocket — connect(), sendAction()
    11. Main update — updateGame() dispatcher
    12. Phase handlers — updateTeamSelect(), updatePhaseUI()
    13. Garden updates — updatePlants(), updateTeam()
    14. UI helpers — updateProgress(), updateTimer(), updateBadge(),
                     updatePodCount()
    15. Button handlers — attachButtons(), selectMode()
    16. Confetti — launchConfetti() celebration effect
    17. Fullscreen — IIFE for fullscreen toggle
    18. Connection dot — setConnDot()

   RELATIONSHIP TO PEBBLE PROJECT:
     This is the visual frontend of the Pebble system. It receives
     game state from the Python WebSocket server (which aggregates
     data from physical BLE sensor pods) and renders it as an
     interactive flower garden. The LEDLight subsystem mirrors
     the score ratio on a physical LED strip.
   ============================================================= */

/* WebSocket server URL — the Python game server runs locally */
const WS_URL = "ws://localhost:8765";

// ── Translations ─────────────────────────────────────────────
// Complete bilingual string table for English ("en") and Chinese ("zh").
// Static strings are plain values; dynamic strings (those needing runtime
// parameters like score or team number) are functions that return the
// formatted string. The t() helper below resolves either form.
const STRINGS = {
  en: {
    title:            "🌸 Pebble Garden",
    noPods:           "No pods connected",
    pods:             (n) => `${n} pod${n !== 1 ? "s" : ""} connected`,
    score:            (s) => `Score: ${s} pts`,
    teamScore:        (s) => `${s} pts`,
    durationLabel:    "Game Duration",
    durMin:           (s) => s < 60 ? `${s} sec` : `${s/60} min`,
    badgeWaiting:     "Ready",
    badgePlaying:     "Growing!",
    badgeWon:         "Time's Up!",
    badgeSelecting:   "Picking Teams",
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
  },
  zh: {
    title:            "🌸 卵石花园",
    noPods:           "未连接设备",
    pods:             (n) => `已连接 ${n} 个设备`,
    score:            (s) => `得分：${s} 分`,
    teamScore:        (s) => `${s} 分`,
    durationLabel:    "游戏时长",
    durMin:           (s) => s < 60 ? `${s} 秒` : `${s/60} 分钟`,
    badgeWaiting:     "准备好了",
    badgePlaying:     "生长中！",
    badgeWon:         "时间到！",
    badgeSelecting:   "选择队伍",
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
  },
};

/* Current language setting — toggled by the language button */
let lang = "en";

/**
 * Translation helper — looks up a string key in the current language table.
 * If the value is a function (for parameterized strings like scores),
 * it calls the function with the provided arguments.
 * Usage: t("score", 42) -> "Score: 42 pts" (en) or "得分：42 分" (zh)
 */
function t(key, ...args) {
  const val = STRINGS[lang][key];
  return typeof val === "function" ? val(...args) : val;
}

// ── Flower sprites ───────────────────────────────────────────
// Procedurally generated SVG flowers in 10 color variations:
//   Sunny, Blush, Lavender, Coral, Sky, Mint, Peach, Crimson, Violet, Butter
//
// Each flower consists of (bottom to top):
//   - A green rectangular stem (rect) with rounded ends
//   - Two leaf ellipses angled off the stem (at y=110 and y=130)
//   - 12 petal ellipses arranged in a radial pattern (rotated 30 degrees apart),
//     alternating between two petal colors (pA and pB)
//   - An outer center circle and inner center circle (the "eye")
//   - Three small dark dots on the center for texture
//
// ViewBox "-60 -80 120 290" — coordinates place petals at y~-70 (top)
// and stem bottom at y~200. Stem is drawn first in SVG order so petals
// naturally layer on top.

/**
 * Generates the inner SVG markup for a single flower.
 *
 * @param {string} pA  — Primary petal fill color (even petals)
 * @param {string} pB  — Secondary petal fill color (odd petals)
 * @param {string} ps  — Petal stroke color
 * @param {string} co  — Outer center circle fill color
 * @param {string} ci  — Inner center circle fill color
 * @param {string} cs  — Center circles stroke color
 * @returns {string}   — SVG elements as an HTML string
 */
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

/* Array of 10 flower color variations. Each entry has:
   - color: the dominant hue (used as the flower's "identity" color)
   - svg: pre-built SVG markup string from _makeFlower()
   Flowers are assigned to plants by (plant_id % 10). */
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

/* Flower display dimensions at scale=1.0 (before per-garden scaling).
   These define the SVG viewBox and the rendered pixel size. */
const FLOWER_W  = 80;          // px width of the flower SVG element
const FLOWER_H  = 210;         // px height (from stem bottom to petal tips)
const FLOWER_VB = "-60 -80 120 290";  // SVG viewBox attribute string

// Legacy alias — kept to avoid breaking any old references elsewhere
const FLOWER_BASE_PX = FLOWER_W;


/* ── Golden-ratio positioning ────────────────────────────────
   Instead of random placement (which clusters) or a grid (which
   looks artificial), flowers are positioned using the golden ratio
   (phi = 0.618...). Multiplying a sequential ID by phi and taking
   the fractional part produces a quasi-random sequence that fills
   the space evenly — known as a "low-discrepancy sequence".

   This gives each flower a unique, well-spread position without
   needing to track occupied spots or check for collisions. */

const φ = 0.618033988749895;  // Golden ratio conjugate

/**
 * Compute the horizontal position (%) for a flower with the given ID.
 * Maps to 8%–92% of the garden width, leaving margins on each side.
 */
function flowerX(id) { return ((id * φ) % 1) * 84 + 8; }

/**
 * Compute the vertical position (% from bottom) for a flower.
 * Maps to 1%–44% from the garden bottom, spreading flowers across
 * the visible grass area.
 * Uses a different multiplier (0.381966 * 2.3) than flowerX so that
 * X and Y positions are uncorrelated — avoiding diagonal patterns.
 */
function flowerY(id) { return ((id * 0.381966 * 2.3) % 1) * 43 + 1; }


// ── Background tree configuration ────────────────────────────
// Array of 7 decorative trees positioned along the horizon.
// Each tree has 3 canopy layers (l1=largest, l3=smallest) stacked
// vertically, plus a trunk. Properties:
//   left:  horizontal position (CSS percentage)
//   scale: overall size multiplier (applied via CSS transform)
//   w1-w3, h1-h3: width/height in px for each canopy layer
//   tw, th: trunk width/height in px
// Trees are purely visual — they don't interact with game logic.
const TREE_DEFS = [
  { left: "3%",  scale: 0.52, w1: 105, h1: 68, w2: 80,  h2: 60, w3: 56, h3: 50, tw: 13, th: 52 },
  { left: "15%", scale: 0.74, w1: 148, h1: 92, w2: 112, h2: 80, w3: 78, h3: 68, tw: 18, th: 70 },
  { left: "30%", scale: 0.62, w1: 124, h1: 78, w2: 95,  h2: 68, w3: 66, h3: 58, tw: 15, th: 60 },
  { left: "50%", scale: 0.68, w1: 135, h1: 85, w2: 103, h2: 74, w3: 72, h3: 63, tw: 16, th: 65 },
  { left: "68%", scale: 0.78, w1: 155, h1: 96, w2: 118, h2: 84, w3: 82, h3: 70, tw: 19, th: 74 },
  { left: "82%", scale: 0.60, w1: 116, h1: 73, w2: 89,  h2: 64, w3: 62, h3: 54, tw: 14, th: 56 },
  { left: "93%", scale: 0.55, w1: 108, h1: 68, w2: 82,  h2: 59, w3: 57, h3: 50, tw: 13, th: 52 },
];

// ── Application State ────────────────────────────────────────
// These variables track the current game state and user selections.
// "last*" variables cache the previous state to detect changes and
// avoid unnecessary DOM updates (a simple form of state diffing).

let socket           = null;    // WebSocket instance (reconnects automatically)
let lastPhase        = null;    // Previous game phase ("waiting"/"playing"/"won"/"team_select")
let lastMode         = null;    // Previous game mode ("single"/"competitive")
let lastPodCount     = null;    // Previous connected pod count (for re-rendering on lang change)
let lastProgress     = null;    // Previous progress value (for re-rendering on lang change)
let selectedMode     = "single";   // Facilitator's chosen mode (before game starts)
let selectedDuration = 120;        // Facilitator's chosen duration in seconds (default 2 min)
let lastTSCounts     = [-1, -1];   // Previous team-select member counts (to detect bumps)
let lastStateTeams   = null;       // Cached competitive teams array (used for win overlay text)
let lastStateSingle  = null;       // Cached single-mode state (used for win overlay text)

/* Garden objects — each represents one flower garden container.
   - el:    reference to the DOM container element
   - els:   sparse array indexed by plant ID; each entry is the plant's DOM element
   - scale: size multiplier for flowers (1.0 for single mode, 0.62 for competitive
             since each garden is only half the screen width)
*/
const SINGLE_GARDEN = { el: null, els: [], scale: 1.0 };
const TEAM_GARDENS  = [
  { el: null, els: [], scale: 0.62 },   // Team 0 (left panel, blue)
  { el: null, els: [], scale: 0.62 },   // Team 1 (right panel, orange)
];

// ── Bootstrap ────────────────────────────────────────────────
// When the DOM is fully loaded, wire up garden references, attach
// all button event listeners, and initiate the WebSocket connection.
document.addEventListener("DOMContentLoaded", () => {
  // Cache references to the garden container elements
  SINGLE_GARDEN.el   = document.getElementById("garden");
  TEAM_GARDENS[0].el = document.getElementById("garden-0");
  TEAM_GARDENS[1].el = document.getElementById("garden-1");
  attachButtons();   // Set up all button click handlers
  connect();         // Start WebSocket connection (auto-reconnects)
});

/**
 * Remove all flower elements from a single garden and reset its tracking array.
 * Called when transitioning back to the waiting phase so flowers start fresh.
 */
function clearGarden(g) {
  if (g.el) g.el.innerHTML = "";
  g.els = [];
}

/**
 * Clear all gardens (single-mode garden + both competitive gardens).
 * Used on phase reset to ensure no stale flowers remain from a previous game.
 */
function clearAllGardens() {
  clearGarden(SINGLE_GARDEN);
  TEAM_GARDENS.forEach(g => clearGarden(g));
}

// ── Language toggle ──────────────────────────────────────────
/**
 * Apply the current language (lang variable) to ALL UI text elements.
 * This function updates every visible string on the page using the t()
 * helper, which looks up the correct translation from the STRINGS table.
 *
 * Called when:
 *   - The user clicks the language toggle button
 *   - Potentially on initial load if a non-default language is set
 *
 * Also re-renders dynamic values (pod count, progress, badge, win text)
 * using cached state so numbers update with the new language format.
 */
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
  document.getElementById("btn-next-team").textContent  = t("tsNextTeam");
  document.getElementById("btn-begin-game").textContent = t("tsBeginGame");
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
/**
 * Dynamically construct decorative background trees from TREE_DEFS.
 *
 * Each tree is built as nested divs:
 *   tree-wrap (positioned + scaled) -> tree (flex column) ->
 *     tree-canopy (3 stacked layers: l1 biggest, l3 smallest) + tree-trunk
 *
 * The canopy layers overlap vertically (negative margins in CSS) to create
 * a bushy tree silhouette. CSS gives them flat pixel-art-style colors.
 * The --tree-growth custom property is set to 1 for full visibility.
 *
 * Trees are appended to #trees-bg, which is positioned at the horizon line
 * (bottom: 32%) with pointer-events: none so they don't block clicks.
 */
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
/**
 * Create a new flower element and append it to a garden container.
 *
 * The flower is built as a layered DOM structure:
 *   .plant (positioned via golden-ratio X/Y) ->
 *     .plant-clip (overflow:hidden div, height starts at 0) ->
 *       <svg> (positioned at bottom of clip, contains flower graphics)
 *
 * Growth animation trick: The clip container starts at height=0, hiding
 * the entire flower. When we later set its height to the full flower
 * height, CSS transition smoothly reveals the flower from bottom (stem)
 * to top (petals). The SVG is anchored to the bottom of the clip, so
 * the stem appears first as the clip grows upward.
 *
 * @param {HTMLElement} gardenEl — The garden container to append to
 * @param {number} id — Unique plant ID (determines color and position)
 * @param {number} scale — Size multiplier (1.0 for single, 0.62 for competitive)
 * @returns {HTMLElement} — The created .plant element
 */
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
/**
 * Establish a WebSocket connection to the Python game server.
 *
 * Connection lifecycle:
 *   - On open: update the connection dot to green, log to console
 *   - On message: parse JSON and call updateGame() to render state
 *   - On close: update dot to red, schedule reconnect after 2 seconds
 *   - On error: close the socket (which triggers the onclose reconnect)
 *
 * This creates a self-healing connection loop: if the server goes down,
 * the dashboard will keep trying to reconnect every 2 seconds until it
 * comes back.
 */
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

/**
 * Send an action message to the Python game server via WebSocket.
 * Actions include: "start" (with mode + duration), "reset", "next_team",
 * "begin_game". The server processes these to advance game state.
 *
 * @param {string} action — The action name to send
 * @param {object} extra  — Additional key-value pairs to include in the message
 */
function sendAction(action, extra = {}) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ action, ...extra }));
  }
}

// ── Main update ──────────────────────────────────────────────
/**
 * Central game state handler — called on every WebSocket message (~150ms).
 *
 * Receives the full game state from the server and routes to the
 * appropriate rendering functions based on mode and phase.
 *
 * State object shape (varies by mode):
 *   Single mode:  { mode, phase, num_devices, score, progress, plants, time_remaining }
 *   Competitive:  { mode, phase, teams: [{id, score, plants, num_devices}], time_remaining, winner }
 *   Team select:  { mode, phase:"team_select", team_select_step, teams }
 *
 * Flow:
 *   1. Extract mode and phase
 *   2. Update pod count display
 *   3. If team_select phase -> show team selection overlay and return early
 *   4. Otherwise -> update layout (single vs competitive CSS class)
 *   5. Update phase UI (show/hide overlays, update badge)
 *   6. Update timer display
 *   7. Cache state for win overlay text
 *   8. Update garden plants or team scores
 */
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

  // Team selection phase — special overlay, skip normal layout
  if (phase === "team_select") {
    updateTeamSelect(state);
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
    updateProgress(state.score, state.progress);
    updatePlants(state.plants, SINGLE_GARDEN);
  }
}

// ── Team selection overlay ────────────────────────────────────
/**
 * Render the team selection overlay during the "team_select" phase.
 * This overlay is used only in competitive mode, before gameplay begins.
 *
 * Two-step process controlled by state.team_select_step:
 *   Step 0: Team 1 is actively accepting members (card glows blue).
 *           Team 2 card is dimmed ("waiting"). "Next: Team 2" button visible.
 *   Step 1: Team 1 is locked. Team 2 is actively accepting (card glows orange).
 *           "Let's Play!" button visible.
 *
 * Member counts are animated with a bounce effect (ts-count-bump class)
 * whenever the count changes, achieved by removing and re-adding the class
 * with a reflow trigger (void offsetWidth) in between.
 *
 * Cards can also show "Team Full!" state when a quota is reached.
 */
function updateTeamSelect(state) {
  const overlay = document.getElementById("team-select-overlay");
  overlay.classList.add("visible");
  document.getElementById("waiting-overlay").classList.add("hidden");

  const step  = state.team_select_step ?? 0;
  const teams = state.teams || [{id:0,num_devices:0},{id:1,num_devices:0}];
  const t0    = teams.find(tm => tm.id === 0) || {num_devices: 0, quota: null, locked: false};
  const t1    = teams.find(tm => tm.id === 1) || {num_devices: 0};
  const counts = [t0.num_devices || 0, t1.num_devices || 0];

  document.getElementById("ts-title").textContent    = t("tsTitle", step + 1);
  document.getElementById("ts-subtitle").textContent = t("tsSub",   step + 1);

  const badge = document.getElementById("status-badge");
  badge.className = "active";
  badge.textContent = t("badgeSelecting");

  document.getElementById("btn-next-team").style.display  = step === 0 ? "" : "none";
  document.getElementById("btn-begin-game").style.display = step === 1 ? "" : "none";

  // Animate count bumps
  [0, 1].forEach(i => {
    const countEl  = document.getElementById(`ts-count-${i}`);
    const newCount = counts[i];
    if (newCount !== lastTSCounts[i]) {
      lastTSCounts[i] = newCount;
      countEl.textContent = newCount;
      countEl.classList.remove("ts-count-bump");
      void countEl.offsetWidth;
      countEl.classList.add("ts-count-bump");
    }
  });

  // ── Team 1 card ───────────────────────────────────────────
  const card0  = document.getElementById("ts-card-0");
  const label0 = document.getElementById("ts-card-label-0");

  if (step > 0) {
    // Phase moved on — Team 1 is done
    card0.className     = "ts-card ts-locked";
    label0.textContent  = t("tsLocked");
  } else if (t0.locked) {
    // Quota reached — Team 1 full
    card0.className     = "ts-card ts-full";
    label0.textContent  = t("tsFull");
  } else {
    // Actively accepting
    card0.className     = "ts-card ts-active";
    label0.textContent  = t0.quota
      ? `${counts[0]} / ${t0.quota} ${t("tsJoined")}`
      : t("tsShakingIn");
  }

  // ── Team 2 card ───────────────────────────────────────────
  const card1  = document.getElementById("ts-card-1");
  const label1 = document.getElementById("ts-card-label-1");

  if (step === 1) {
    card1.className    = "ts-card ts-active";
    label1.textContent = t("tsShakingIn");
  } else {
    card1.className    = "ts-card ts-waiting";
    label1.textContent = t("tsWaiting");
  }
}

// ── Score display (single mode) ──────────────────────────────
/**
 * Update the score label in single-team mode.
 * Displays "Score: X pts" (or Chinese equivalent).
 * Caches the progress value so applyLang() can re-render with the
 * correct number when switching languages mid-game.
 */
function updateProgress(score, progress) {
  lastProgress = progress;
  document.getElementById("progress-label").textContent = t("score", score ?? 0);
}

// ── Countdown timer ───────────────────────────────────────────
/**
 * Update the countdown timer display.
 *
 * Behavior:
 *   - Hidden during non-playing phases (waiting, won, team_select)
 *   - Shows MM:SS format during gameplay, e.g. "2:05"
 *   - Adds "timer-urgent" CSS class when <= 10 seconds remain,
 *     which turns the timer red and makes it blink (CSS animation)
 *
 * @param {number} timeRemaining — Seconds left (from server), can be fractional
 * @param {string} phase — Current game phase
 */
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
/**
 * Synchronize the flower garden with the server's plant list.
 *
 * For each plant in the server state:
 *   - If the plant doesn't exist in the garden yet: spawn a new flower
 *     element and trigger its growth animation.
 *   - If it already exists: just update its "bloomed" state (growth >= 0.98).
 *
 * Growth animation uses a double-requestAnimationFrame trick:
 *   1. First rAF: browser has painted the clip at height=0
 *   2. Second rAF: we set the target height, triggering the CSS transition
 *   Without this, the browser batches the height change and the flower
 *   "pops" to full size instantly instead of growing smoothly.
 *
 * The "bloomed" CSS class unlocks petal overflow (so petals aren't clipped
 * at the edge) and adds a gentle swaying animation.
 *
 * @param {Array} plants — Array of {id, growth} from the server
 * @param {object} g — Garden object with {el, els[], scale}
 */
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
/**
 * Update the pod count display in the header.
 * Shows "No pods connected" when n=0, or "X pod(s) connected" otherwise.
 * Caches the count for re-rendering when the language changes.
 */
function updatePodCount(n) {
  lastPodCount = n;
  document.getElementById("pod-count").textContent =
    n === 0 ? t("noPods") : t("pods", n);
}

// ── Competitive team update ───────────────────────────────────
/**
 * Update a single team's display in competitive mode.
 * Sets the team's score label and updates its flower garden.
 *
 * @param {object} team — Team state object: {id, score, plants}
 *   team.id is 0 or 1 (maps to left/right panel).
 */
function updateTeam(team) {
  const i = team.id;
  document.getElementById(`team-score-label-${i}`).textContent = t("teamScore", team.score ?? 0);
  updatePlants(team.plants, TEAM_GARDENS[i]);
}

// ── Badge ─────────────────────────────────────────────────────
/**
 * Update the status badge in the header to reflect the current game phase.
 * The badge changes both text and CSS class for different colors:
 *   "waiting" -> white badge, "Ready" text
 *   "playing" -> yellow badge, "Growing!" text
 *   "won"     -> pink badge, "Time's Up!" text
 */
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
/**
 * Manage overlay visibility and content based on the current game phase.
 *
 * Phase transitions:
 *   "waiting": Show the waiting overlay, hide win overlay, clear gardens.
 *              Reset team-select state and confetti tracking.
 *
 *   "playing": Hide waiting overlay, hide win overlay. Gardens are
 *              being updated by updatePlants() in the main update loop.
 *
 *   "won": Hide waiting overlay, show win overlay with final results.
 *          Content depends on mode:
 *            - Competitive + winner: "Team X Wins!" with both scores
 *            - Competitive + tie: "It's a Tie!" with both scores
 *            - Single: "Time's Up!" with final score
 *          Confetti is launched once (tracked by dataset.confettiDone).
 *
 * The phaseChanged flag prevents redundant DOM updates when the phase
 * hasn't actually changed between update ticks.
 */
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
/**
 * Attach click event listeners to all interactive buttons on the page.
 *
 * Facilitator actions (sent to server via WebSocket):
 *   - #btn-start: Start a new session with the selected mode and duration
 *   - #btn-reset: Reset the game back to the waiting phase
 *   - #btn-next-team: Advance team selection from Team 1 to Team 2
 *   - #btn-begin-game: Finalize teams and start competitive play
 *   - #facilitator-start: Alternative start button (bottom-left shortcut)
 *
 * Configuration controls (local state only, not sent to server):
 *   - .mode-btn: Toggle between "single" and "competitive" mode
 *   - .dur-btn: Select game duration (30s, 60s, 120s, 300s)
 *   - #lang-toggle: Switch between English and Chinese
 */
function attachButtons() {
  document.getElementById("btn-start").addEventListener("click", () =>
    sendAction("start", { mode: selectedMode, duration: selectedDuration })
  );
  document.getElementById("btn-reset").addEventListener("click", () =>
    sendAction("reset")
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

/**
 * Update the selected game mode and toggle the active state on mode buttons.
 * This only changes the local UI state — the mode is sent to the server
 * when the facilitator clicks "Start Session".
 */
function selectMode(mode) {
  selectedMode = mode;
  document.getElementById("btn-mode-single").classList.toggle("active", mode === "single");
  document.getElementById("btn-mode-competitive").classList.toggle("active", mode === "competitive");
}

// ── Confetti ─────────────────────────────────────────────────
/* Color palette for confetti particles — a festive mix of pink, gold,
   green, purple, orange, and sky blue. */
const CONFETTI_COLORS = ["#ff69b4","#ffd700","#78e060","#cc66dd","#ff7030","#87ceeb"];

/**
 * Launch a confetti celebration animation.
 *
 * Creates 100 small colored div elements scattered across the viewport.
 * Each particle:
 *   - Starts above the screen (top: -14px)
 *   - Falls to 108vh while rotating 540 degrees
 *   - Has a random horizontal position (0-100vw)
 *   - Has randomized duration (2-4.5s) and delay (0-2s) via CSS custom
 *     properties --dur and --delay
 *   - Is either circular (border-radius: 50%) or square (3px radius)
 *   - Self-removes from the DOM when its animation ends
 *
 * The CSS @keyframes "fall" animation in style.css handles the actual
 * movement. This function only creates the elements and sets their
 * random properties.
 */
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
/**
 * Fullscreen toggle — self-executing IIFE that sets up the fullscreen button.
 *
 * Uses the browser's Fullscreen API (document.documentElement.requestFullscreen).
 * The button icon switches between expand (normal) and close (fullscreen).
 * Listens for both button clicks and Escape key to keep the icon in sync.
 * The fullscreenchange event ensures the icon always matches the actual state.
 */
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
/**
 * Update the WebSocket connection indicator dot (bottom-right corner).
 * Sets the CSS class to "connected" (green with glow) or "disconnected"
 * (red with blink animation). Used by the WebSocket lifecycle handlers.
 */
function setConnDot(connected) {
  document.getElementById("conn-dot").className = connected ? "connected" : "disconnected";
}
