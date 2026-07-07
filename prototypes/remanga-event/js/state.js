/* ============================================================
 * state.js — состояние прототипа, localStorage, экономика.
 * ============================================================ */

const STORAGE_KEY = 'remangaEventProto.v1';

function defaultState() {
  return {
    resources: { ...EVENT.start },
    day: 1, /* текущий день ивента (двигается dev-панелью) */
    advent: { claimed: 0 }, /* мягкий вариант: забрано наград по порядку */
    heroine: { name: 'Ария', type: 'eu', hair: 'black', style: 'loose', outfit: 'base' },
    outfitsOwned: ['base'],
    badges: [],
    milestonesClaimed: [],
    stories: {}, /* по id: см. ensureStory */
  };
}

let S = load();

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const st = JSON.parse(raw);
      /* дозаполняем новые поля при обновлении прототипа */
      return Object.assign(defaultState(), st, {
        resources: Object.assign({ ...EVENT.start }, st.resources),
      });
    }
  } catch (e) { console.warn('state load failed', e); }
  return defaultState();
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(S));
}

function resetState() {
  S = defaultState();
  save();
}

/* ---------- истории ---------- */

function storyById(id) { return STORIES.find(s => s.id === id); }

function ensureStory(id) {
  if (!S.stories[id]) {
    S.stories[id] = {
      unlocked: storyById(id).cost === 0,
      episodes: {},   /* id: { started, completed, pos, rewardClaimed } */
      paidBought: [], /* 'choiceId:optIndex' */
      cutscenes: [],  /* открытые кат-сцены (id слотов) */
      flags: {},
      rel: {},
      completed: false,
    };
  }
  return S.stories[id];
}

function ensureEp(storyId, epId) {
  const st = ensureStory(storyId);
  if (!st.episodes[epId]) st.episodes[epId] = { started: false, completed: false, pos: 0, rewardClaimed: false };
  return st.episodes[epId];
}

/* ---------- ресурсы ---------- */

function canAfford(cost) {
  return Object.entries(cost).every(([k, v]) => (S.resources[k] || 0) >= v);
}

function spend(cost) {
  if (!canAfford(cost)) return false;
  for (const [k, v] of Object.entries(cost)) S.resources[k] -= v;
  save();
  return true;
}

/* Начисление награды; возвращает список строк для поп-апа */
function grant(reward) {
  const lines = [];
  for (const [k, v] of Object.entries(reward)) {
    if (k === 'outfit') {
      if (!S.outfitsOwned.includes(v)) S.outfitsOwned.push(v);
      lines.push({ icon: 'dress', text: `Облик «${EVENT.outfits[v].name}»` });
    } else if (k === 'badge') {
      if (!S.badges.includes(v)) S.badges.push(v);
      lines.push({ icon: 'badge', text: `Бейдж «${v}»` });
    } else {
      S.resources[k] = (S.resources[k] || 0) + v;
      lines.push({ icon: EVENT.currencies[k].icon, text: `${EVENT.currencies[k].name}: +${v}` });
    }
  }
  save();
  return lines;
}

/* ---------- адвент ---------- */

/* Мягкий вариант: награды забираются строго по порядку,
 * доступно наград = min(день ивента, всего дней). */
function adventClaimable() {
  return S.advent.claimed < Math.min(S.day, EVENT.advent.length);
}

function claimAdvent() {
  if (!adventClaimable()) return null;
  const cell = EVENT.advent[S.advent.claimed];
  S.advent.claimed++;
  const lines = grant(cell.reward);
  save();
  return { cell, lines };
}

/* ---------- статусы историй и эпизодов ---------- */

/* Статусы истории из ТЗ: закрыта / доступна для открытия / открыта,
 * но не начата / в процессе / пройдена / ожидает продолжения */
function storyStatus(story) {
  if (story.comingSoon) return 'soon';
  const st = ensureStory(story.id);
  if (!st.unlocked) return 'locked';
  const eps = story.episodes.filter(e => !e.bonus);
  const done = eps.filter(e => st.episodes[e.id]?.completed).length;
  const started = eps.some(e => st.episodes[e.id]?.started);
  if (done === eps.length && eps.length > 0) return 'done';
  if (started) return 'progress';
  return 'open';
}

function episodeStatus(story, ep) {
  const st = ensureStory(story.id);
  const es = st.episodes[ep.id];
  if (es?.completed) return 'done';
  if (es?.started) return 'progress';
  if (ep.bonus) {
    return bonusUnlocked(story) ? 'available' : 'locked';
  }
  /* последовательная разблокировка */
  const idx = story.episodes.filter(e => !e.bonus).findIndex(e => e.id === ep.id);
  if (idx === 0) return 'available';
  const prev = story.episodes.filter(e => !e.bonus)[idx - 1];
  return st.episodes[prev.id]?.completed ? 'available' : 'locked';
}

function bonusUnlocked(story) {
  const st = ensureStory(story.id);
  const mainDone = story.episodes.filter(e => !e.bonus).every(e => st.episodes[e.id]?.completed);
  const need = story.bonusEpisode?.minCutscenes || 0;
  return mainDone && st.cutscenes.length >= need;
}

function storyProgress(story) {
  const st = ensureStory(story.id);
  const eps = story.episodes.filter(e => !e.bonus);
  const done = eps.filter(e => st.episodes[e.id]?.completed).length;
  return { done, total: eps.length };
}

/* ---------- кат-сцены ---------- */

function totalCutscenesOpen() {
  return STORIES.reduce((n, s) => n + (S.stories[s.id]?.cutscenes.length || 0), 0);
}

function totalCutscenes() {
  return STORIES.reduce((n, s) => n + s.cutscenes.length, 0);
}

/* Открыть кат-сцену; награда — только при первом открытии */
function openCutscene(storyId, csId) {
  const st = ensureStory(storyId);
  if (st.cutscenes.includes(csId)) return { first: false, lines: [] };
  st.cutscenes.push(csId);
  const meta = storyById(storyId).cutscenes.find(c => c.id === csId);
  const lines = meta?.reward ? grant(meta.reward) : [];
  save();
  return { first: true, lines };
}

/* ---------- отношения ---------- */

function applyRel(storyId, rel) {
  const st = ensureStory(storyId);
  const msgs = [];
  for (const [ch, d] of Object.entries(rel)) {
    if (!d) continue;
    st.rel[ch] = (st.rel[ch] || 0) + d;
    const name = REL_LABELS[ch] || ch;
    msgs.push(d > 0 ? `${name}: отношения улучшились (+${d})` : `${name}: отношения испортились (${d})`);
  }
  save();
  return msgs;
}
