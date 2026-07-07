/* ============================================================
 * app.js — экраны, навигация, читалка, поп-апы.
 * ============================================================ */

const $app = document.getElementById('app');
const $modals = document.getElementById('modals');
const $toasts = document.getElementById('toasts');

/* Служебное UI-состояние (не персистится, кроме позиции читалки) */
const UI = {
  screen: 'hub',       /* hub | story | reader */
  storyId: null,
  reader: null,        /* { storyId, epId } */
  modals: [],          /* стек модалок: {type, ...} */
};

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const heroName = () => esc(S.heroine.name || 'Ария');
const fmtText = (t) => esc(t).replaceAll('{name}', heroName());

/* ============================ НАВИГАЦИЯ ============================ */

const App = {};

App.go = (screen, storyId = null) => {
  UI.screen = screen;
  UI.storyId = storyId;
  if (screen !== 'reader') UI.reader = null;
  render();
  window.scrollTo(0, 0);
};

/* ============================ ТОСТЫ ============================ */

function toast(text, icon = 'sparkle') {
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `${ic(icon, 16)}<span>${text}</span>`;
  $toasts.appendChild(el);
  setTimeout(() => el.classList.add('show'), 20);
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 350); }, 2800);
}

/* ============================ МОДАЛКИ ============================ */

function pushModal(m) { UI.modals.push(m); renderModals(); }
App.closeModal = () => { UI.modals.pop(); renderModals(); render(); };
App.closeAllModals = () => { UI.modals = []; renderModals(); render(); };

function popup({ title, text = '', lines = [], buttons = null, art = null, wide = false }) {
  pushModal({ type: 'popup', title, text, lines, buttons, art, wide });
}

function rewardLinesHtml(lines) {
  if (!lines.length) return '';
  return `<div class="reward-lines">${lines.map(l => `<div class="reward-line">${ic(l.icon, 20)}<span>${esc(l.text)}</span></div>`).join('')}</div>`;
}

function renderModals() {
  if (!UI.modals.length) { $modals.innerHTML = ''; $modals.classList.remove('on'); return; }
  $modals.classList.add('on');
  const m = UI.modals[UI.modals.length - 1];
  let inner = '';

  if (m.type === 'popup') {
    const btns = m.buttons || [{ text: 'Хорошо', cls: 'btn-primary', action: 'App.closeModal()' }];
    inner = `<div class="modal ${m.wide ? 'modal-wide' : ''}">
      ${m.art ? `<div class="modal-art">${m.art}</div>` : ''}
      <div class="modal-body">
        <div class="modal-title">${m.title}</div>
        ${m.text ? `<div class="modal-text">${m.text}</div>` : ''}
        ${rewardLinesHtml(m.lines || [])}
        <div class="modal-btns">${btns.map(b => `<button class="btn ${b.cls || 'btn-ghost'}" onclick="${b.action}">${b.text}</button>`).join('')}</div>
      </div>
    </div>`;
  } else if (m.type === 'cutscene') {
    const meta = storyById(m.storyId).cutscenes.find(c => c.id === m.csId);
    inner = `<div class="cs-view">
      <div class="cs-art">${art(m.csId)}</div>
      <div class="cs-caption">
        <div class="cs-name">${ic('gallery', 18)} Кат-сцена «${esc(meta.title)}» ${m.first ? 'открыта!' : ''}</div>
        ${m.first ? rewardLinesHtml(m.lines) : ''}
        <button class="btn btn-primary" onclick="App.afterCutscene()">Продолжить</button>
      </div>
    </div>`;
  } else if (m.type === 'advent') {
    inner = renderAdvent();
  } else if (m.type === 'gallery') {
    inner = renderGallery();
  } else if (m.type === 'constructor') {
    inner = renderConstructor();
  } else if (m.type === 'shop') {
    inner = renderShop(m.focus);
  }

  $modals.innerHTML = `<div class="modal-backdrop" onclick="if(event.target===this)App.closeModal()">${inner}</div>`;
}

/* ============================ РЕСУРСЫ ============================ */

function resBarHtml() {
  const r = S.resources;
  const cell = (key) => `<div class="res" title="${EVENT.currencies[key].hint}">
    ${ic(EVENT.currencies[key].icon, 20)}<b>${r[key]}</b></div>`;
  return `<div class="res-bar">
    ${cell('keys')}${cell('crystals')}${cell('hearts')}
    <button class="res-plus" onclick="App.openShop()" title="Магазин">+</button>
  </div>`;
}

App.openShop = (focus = null) => pushModal({ type: 'shop', focus });

function renderShop(focus) {
  const rows = EVENT.shop.map(p => `
    <div class="shop-row ${focus === p.res ? 'hl' : ''}">
      <div class="shop-icon">${ic(EVENT.currencies[p.res].icon, 26)}</div>
      <div class="shop-name">${EVENT.currencies[p.res].name} × ${p.amount}</div>
      <button class="btn btn-primary btn-sm" onclick="App.buyPack('${p.id}')">${p.price}</button>
    </div>`).join('');
  return `<div class="modal modal-wide">
    <div class="modal-body">
      <div class="modal-title">${ic('gift', 20)} Магазин ивента</div>
      <div class="modal-text muted">Прототип: покупка имитируется, деньги не списываются.</div>
      <div class="shop-list">${rows}</div>
      <div class="modal-btns"><button class="btn btn-ghost" onclick="App.closeModal()">Закрыть</button></div>
    </div>
  </div>`;
}

App.buyPack = (id) => {
  const p = EVENT.shop.find(x => x.id === id);
  const lines = grant({ [p.res]: p.amount });
  App.closeModal();
  popup({ title: 'Покупка совершена', text: 'Это мок-покупка для прототипа.', lines });
};

/* ============================ ХАБ ============================ */

function timerHtml() {
  const daysLeft = Math.max(0, EVENT.durationDays - S.day);
  return `<span id="evt-timer">${daysLeft} дн. <span class="t-hms"></span></span>`;
}

function tickTimer() {
  const el = document.querySelector('#evt-timer .t-hms');
  if (!el) return;
  const now = new Date();
  const hh = 23 - now.getHours(), mm = 59 - now.getMinutes(), ss = 59 - now.getSeconds();
  el.textContent = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}
setInterval(tickTimer, 1000);

const STATUS_META = {
  locked:   { label: 'Закрыта',            btn: 'Открыть',     cls: 'st-locked' },
  soon:     { label: 'Скоро',              btn: 'Скоро',       cls: 'st-soon' },
  open:     { label: 'Не начата',          btn: 'Начать',      cls: 'st-open' },
  progress: { label: 'В процессе',         btn: 'Продолжить',  cls: 'st-progress' },
  done:     { label: 'Пройдена',           btn: 'Перепройти',  cls: 'st-done' },
};

function storyCardHtml(story) {
  const status = storyStatus(story);
  const meta = STATUS_META[status];
  const st = ensureStory(story.id);
  const prog = storyProgress(story);
  const csOpen = st.cutscenes.length, csTotal = story.cutscenes.length;

  let actions = '';
  if (status === 'soon') actions = `<button class="btn btn-ghost" onclick="App.soonPopup()">Скоро</button>`;
  else if (status === 'locked') actions = `<button class="btn btn-primary" onclick="App.tryUnlockStory('${story.id}')">${ic('crystal', 16)} Открыть за ${story.cost}</button>`;
  else actions = `<button class="btn btn-primary" onclick="App.go('story','${story.id}')">${meta.btn}</button>`;

  return `<div class="story-card ${status === 'soon' || status === 'locked' ? 'dim' : ''}">
    <div class="story-cover" onclick="${status === 'soon' ? 'App.soonPopup()' : status === 'locked' ? `App.tryUnlockStory('${story.id}')` : `App.go('story','${story.id}')`}">
      ${art(story.cover)}
      <span class="chip status-chip ${meta.cls}">${meta.label}</span>
      ${status === 'locked' ? `<span class="cover-lock">${ic('lock', 34)}</span>` : ''}
    </div>
    <div class="story-info">
      <div class="story-title">${esc(story.title)}</div>
      <div class="story-genres">${story.genres.map(g => `<span class="chip">${g}</span>`).join('')}</div>
      ${!story.comingSoon ? `
        <div class="story-meta">
          <div class="pbar"><div class="pbar-fill" style="width:${prog.total ? prog.done / prog.total * 100 : 0}%"></div></div>
          <span class="muted">Эпизоды: ${prog.done}/${prog.total}</span>
          <span class="muted">${ic('gallery', 14)} ${csOpen}/${csTotal}</span>
        </div>` : `<div class="story-meta"><span class="muted">Продолжение ивента</span></div>`}
      <div class="story-actions">${actions}</div>
    </div>
  </div>`;
}

App.soonPopup = () => popup({
  title: 'Продолжение скоро',
  text: 'Эта история откроется в следующем обновлении ивента. Загляните позже!',
});

App.tryUnlockStory = (id) => {
  const story = storyById(id);
  if (canAfford({ crystals: story.cost })) {
    popup({
      title: `Открыть историю?`,
      text: `«${esc(story.title)}» — открытие навсегда, повторно платить не нужно.`,
      buttons: [
        { text: `${ic('crystal', 16)} Открыть за ${story.cost}`, cls: 'btn-primary', action: `App.unlockStory('${id}')` },
        { text: 'Назад', cls: 'btn-ghost', action: 'App.closeModal()' },
      ],
    });
  } else {
    popup({
      title: 'Недостаточно кристаллов',
      text: `Для открытия истории нужно ${story.cost} ${ic('crystal', 16)}. Кристаллы можно получить в адвент-календаре или купить.`,
      buttons: [
        { text: 'Адвент-календарь', cls: 'btn-primary', action: 'App.closeModal();App.openAdvent()' },
        { text: 'Магазин', cls: 'btn-ghost', action: 'App.closeModal();App.openShop("crystals")' },
        { text: 'Назад', cls: 'btn-ghost', action: 'App.closeModal()' },
      ],
    });
  }
};

App.unlockStory = (id) => {
  const story = storyById(id);
  if (!spend({ crystals: story.cost })) return;
  ensureStory(id).unlocked = true;
  save();
  App.closeModal();
  popup({ title: 'История открыта!', text: `«${esc(story.title)}» теперь доступна навсегда.`, buttons: [
    { text: 'К истории', cls: 'btn-primary', action: `App.closeModal();App.go('story','${id}')` },
    { text: 'Позже', cls: 'btn-ghost', action: 'App.closeModal()' },
  ]});
  render();
};

function milestonesHtml() {
  const open = totalCutscenesOpen();
  return `<div class="panel">
    <div class="panel-title">${ic('gallery', 20)} Награды за кат-сцены <span class="muted">(открыто: ${open}/${totalCutscenes()})</span></div>
    <div class="ms-row">
      ${EVENT.milestones.map((m, i) => {
        const claimed = S.milestonesClaimed.includes(i);
        const ready = open >= m.count && !claimed;
        return `<div class="ms-cell ${claimed ? 'claimed' : ready ? 'ready' : ''}">
          <div class="ms-count">${m.count} сцен${m.count === 1 ? 'а' : ''}</div>
          <div class="ms-reward">${esc(m.label)}</div>
          ${claimed ? `<div class="ms-state">${ic('check', 16)} Получено</div>`
            : ready ? `<button class="btn btn-primary btn-sm" onclick="App.claimMilestone(${i})">Забрать</button>`
            : `<div class="ms-state muted">${ic('lock', 14)}</div>`}
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

App.claimMilestone = (i) => {
  const m = EVENT.milestones[i];
  if (S.milestonesClaimed.includes(i) || totalCutscenesOpen() < m.count) return;
  S.milestonesClaimed.push(i);
  const lines = grant(m.reward);
  popup({ title: 'Награда получена!', lines });
  render();
};

function renderHub() {
  const adventReady = adventClaimable();
  const heroCfg = S.heroine;
  return `
  <div class="hub">
    <div class="banner">
      ${art('banner.event')}
      <div class="banner-overlay">
        <div class="banner-kicker">Ивент ReМанга</div>
        <h1 class="banner-title">${EVENT.title}</h1>
        <div class="banner-sub">${EVENT.subtitle}</div>
        <div class="banner-timer chip">${ic('clock', 14)} До конца: ${timerHtml()}</div>
      </div>
    </div>

    <div class="hub-topline">
      ${resBarHtml()}
      <div class="hub-tiles">
        <button class="tile ${adventReady ? 'tile-glow' : ''}" onclick="App.openAdvent()">
          ${ic('gift', 26)}<span>Адвент</span>
          ${adventReady ? '<span class="dot"></span>' : ''}
          <span class="tile-sub">${S.advent.claimed}/${EVENT.advent.length}</span>
        </button>
        <button class="tile" onclick="App.openGallery()">
          ${ic('gallery', 26)}<span>Галерея</span>
          <span class="tile-sub">${totalCutscenesOpen()}/${totalCutscenes()}</span>
        </button>
        <button class="tile" onclick="App.openConstructor()">
          <span class="tile-hero">${heroineSVG(heroCfg, 'smile')}</span><span>Героиня</span>
          <span class="tile-sub">${esc(EVENT.outfits[heroCfg.outfit].name)}</span>
        </button>
      </div>
    </div>

    <h2 class="section-title">Истории</h2>
    <div class="stories-grid">
      ${STORIES.map(storyCardHtml).join('')}
    </div>

    ${milestonesHtml()}

    ${S.badges.length ? `<div class="panel"><div class="panel-title">${ic('badge', 20)} Ваши бейджи</div>
      <div class="badges">${S.badges.map(b => `<span class="chip chip-badge">${ic('badge', 14)} ${esc(b)}</span>`).join('')}</div></div>` : ''}

    <div class="hub-note muted">Прототип механик ивента. Все арты — временные SVG-заглушки, каждая будет заменена сгенерированным изображением (см. ASSETS.md).</div>
  </div>`;
}

/* ============================ АДВЕНТ ============================ */

App.openAdvent = () => pushModal({ type: 'advent' });

function renderAdvent() {
  const claimedN = S.advent.claimed;
  const availableN = Math.min(S.day, EVENT.advent.length);
  const cells = EVENT.advent.map((c, i) => {
    const claimed = i < claimedN;
    const isNext = i === claimedN && i < availableN;
    const locked = !claimed && !isNext;
    return `<div class="adv-cell ${c.final ? 'adv-final' : ''} ${claimed ? 'claimed' : isNext ? 'ready' : 'locked'}">
      <div class="adv-day">День ${c.day}</div>
      <div class="adv-icon">${c.final ? heroineSVG({ ...S.heroine, outfit: 'advent' }, 'joy') : ic(c.reward.keys ? 'key' : c.reward.crystals ? 'crystal' : 'heart', 30)}</div>
      <div class="adv-label">${esc(c.label)}</div>
      ${claimed ? `<div class="adv-state">${ic('check', 16)} Получено</div>`
        : isNext ? `<button class="btn btn-primary btn-sm" onclick="App.claimAdvent()">Забрать</button>`
        : `<div class="adv-state muted">${ic('lock', 14)} ${i >= availableN ? `Откроется в день ${c.day}` : 'По порядку'}</div>`}
    </div>`;
  }).join('');
  return `<div class="modal modal-advent">
    <div class="modal-body">
      <div class="modal-title">${ic('gift', 22)} Адвент-календарь</div>
      <div class="modal-text muted">Каждый день — одна награда. Пропущенные дни не сгорают: награды забираются по порядку. Сегодня ${S.day}-й день ивента.</div>
      <div class="adv-grid">${cells}</div>
      <div class="modal-btns"><button class="btn btn-ghost" onclick="App.closeModal()">Закрыть</button></div>
    </div>
  </div>`;
}

App.claimAdvent = () => {
  const res = claimAdvent();
  if (!res) return;
  renderModals();
  popup({
    title: `День ${res.cell.day}: награда получена!`,
    lines: res.lines,
    text: res.cell.final ? 'Финальная награда адвента! Облик уже доступен в конструкторе героини — он пригодится и в продолжении истории.' : '',
  });
  render();
};

/* ============================ ГАЛЕРЕЯ ============================ */

App.openGallery = () => pushModal({ type: 'gallery' });

function renderGallery() {
  const blocks = STORIES.filter(s => s.cutscenes.length).map(story => {
    const st = ensureStory(story.id);
    const cells = story.cutscenes.map(cs => {
      const open = st.cutscenes.includes(cs.id);
      return `<div class="gal-cell ${open ? '' : 'locked'}" ${open ? `onclick="App.viewCutscene('${story.id}','${cs.id}')"` : ''}>
        <div class="gal-thumb">${art(cs.id, { locked: !open })}</div>
        <div class="gal-name">${open ? esc(cs.title) : '???'}</div>
        <div class="gal-hint muted">${open ? 'Открыта' : esc(cs.hint)}</div>
      </div>`;
    }).join('');
    return `<div class="gal-story">
      <div class="gal-story-title">${esc(story.title)} <span class="muted">${st.cutscenes.length}/${story.cutscenes.length}</span></div>
      <div class="gal-grid">${cells}</div>
    </div>`;
  }).join('');
  return `<div class="modal modal-advent">
    <div class="modal-body">
      <div class="modal-title">${ic('gallery', 22)} Галерея кат-сцен</div>
      <div class="modal-text muted">Закрытые сцены показаны силуэтами. Награда за открытие каждой сцены выдаётся один раз.</div>
      ${blocks}
      <div class="modal-btns"><button class="btn btn-ghost" onclick="App.closeModal()">Закрыть</button></div>
    </div>
  </div>`;
}

App.viewCutscene = (storyId, csId) => {
  pushModal({ type: 'cutscene', storyId, csId, first: false, lines: [], viewOnly: true });
};

/* ============================ КОНСТРУКТОР ============================ */

App.openConstructor = () => pushModal({ type: 'constructor' });

const H_TYPES = { eu: 'Европейский', asia: 'Азиатский', afro: 'Афро' };
const H_HAIRS = { black: 'Чёрные', blond: 'Блонд', red: 'Рыжие' };
const H_STYLES = { loose: 'Распущенные', ponytail: 'Хвост', festive: 'Укладка' };

function chipRow(map, cur, setter) {
  return Object.entries(map).map(([k, label]) =>
    `<button class="chip chip-btn ${cur === k ? 'on' : ''}" onclick="${setter}('${k}')">${label}</button>`).join('');
}

function renderConstructor() {
  const h = S.heroine;
  const outfitCards = Object.entries(EVENT.outfits).map(([id, o]) => {
    const owned = S.outfitsOwned.includes(id);
    const cur = h.outfit === id;
    let action;
    if (cur) action = `<div class="ms-state">${ic('check', 16)} Выбран</div>`;
    else if (owned) action = `<button class="btn btn-ghost btn-sm" onclick="App.setHero('outfit','${id}')">Надеть</button>`;
    else if (o.cost) action = `<button class="btn btn-primary btn-sm" onclick="App.buyOutfit('${id}')">${ic('heart', 14)} ${o.cost}</button>`;
    else action = `<div class="ms-state muted">${ic('lock', 14)} Адвент, день 7</div>`;
    return `<div class="outfit-card ${cur ? 'on' : ''} ${!owned && !o.cost ? 'dim' : ''}">
      <div class="outfit-prev">${heroineSVG({ ...h, outfit: id }, 'calm')}</div>
      <div class="outfit-name">${esc(o.name)}</div>
      <div class="outfit-how muted">${esc(o.how)}</div>
      ${action}
    </div>`;
  }).join('');

  return `<div class="modal modal-advent">
    <div class="modal-body constructor">
      <div class="modal-title">${ic('dress', 22)} Конструктор героини</div>
      <div class="modal-text muted">Собери образ по шагам — он будет использоваться в сценах всех историй. Особый облик добавляет реплики персонажей.</div>
      <div class="ctor-grid">
        <div class="ctor-preview">${heroineSVG(h, 'smile')}
          <input class="ctor-name" value="${heroName()}" maxlength="16" onchange="App.setHeroName(this.value)" title="Имя героини">
        </div>
        <div class="ctor-controls">
          <div class="ctor-row"><label>Типаж</label><div>${chipRow(H_TYPES, h.type, "App.setHeroT")}</div></div>
          <div class="ctor-row"><label>Волосы</label><div>${chipRow(H_HAIRS, h.hair, "App.setHeroH")}</div></div>
          <div class="ctor-row"><label>Причёска</label><div>${chipRow(H_STYLES, h.style, "App.setHeroS")}</div></div>
          <div class="ctor-row"><label>Облик</label></div>
          <div class="outfit-row">${outfitCards}</div>
        </div>
      </div>
      <div class="modal-btns"><button class="btn btn-primary" onclick="App.closeModal()">Готово</button></div>
    </div>
  </div>`;
}

App.setHero = (k, v) => { S.heroine[k] = v; save(); renderModals(); render(); };
App.setHeroT = (v) => App.setHero('type', v);
App.setHeroH = (v) => App.setHero('hair', v);
App.setHeroS = (v) => App.setHero('style', v);
App.setHeroName = (v) => { S.heroine.name = v.trim() || 'Ария'; save(); render(); };

App.buyOutfit = (id) => {
  const o = EVENT.outfits[id];
  if (!spend({ hearts: o.cost })) {
    popup({ title: 'Недостаточно сердец', text: `Нужно ${o.cost} ${ic('heart', 16)}. Сердца дают адвент, кат-сцены и награды эпизодов.`, buttons: [
      { text: 'Магазин', cls: 'btn-primary', action: 'App.closeModal();App.openShop("hearts")' },
      { text: 'Назад', cls: 'btn-ghost', action: 'App.closeModal()' },
    ]});
    return;
  }
  S.outfitsOwned.push(id);
  S.heroine.outfit = id;
  save();
  toast(`Облик «${o.name}» получен!`, 'dress');
  renderModals(); render();
};

/* ============================ ЭКРАН ИСТОРИИ ============================ */

function relBarsHtml(story) {
  const st = ensureStory(story.id);
  if (!story.characters.length) return '';
  return `<div class="rel-block">
    ${story.characters.map(ch => {
      const v = st.rel[ch] || 0;
      const pct = Math.max(4, Math.min(100, (v + 2) / 12 * 100));
      return `<div class="rel-row">
        <span class="rel-ava">${phPortrait(ch, v >= 3 ? 'smile' : v < 0 ? 'cold' : 'calm')}</span>
        <span class="rel-name">${REL_LABELS[ch]}</span>
        <div class="rel-bar"><div class="rel-fill ${v < 0 ? 'neg' : ''}" style="width:${pct}%"></div></div>
        <span class="rel-val muted">${v > 0 ? '+' + v : v}</span>
      </div>`;
    }).join('')}
  </div>`;
}

function episodeRowHtml(story, ep) {
  const st = ensureStory(story.id);
  const es = st.episodes[ep.id];
  const status = episodeStatus(story, ep);
  const stChip = {
    locked: `<span class="chip st-locked">${ic('lock', 12)} Закрыт</span>`,
    available: `<span class="chip st-open">Доступен</span>`,
    progress: `<span class="chip st-progress">В процессе</span>`,
    done: `<span class="chip st-done">${ic('check', 12)} Пройден</span>`,
  }[status];

  let btn = '';
  if (status === 'available') btn = `<button class="btn btn-primary btn-sm" onclick="App.startEpisode('${story.id}','${ep.id}')">${ic('key', 14)} ${ep.keyCost} · Начать</button>`;
  if (status === 'progress') btn = `<button class="btn btn-primary btn-sm" onclick="App.startEpisode('${story.id}','${ep.id}')">Продолжить</button>`;
  if (status === 'done') btn = `<button class="btn btn-ghost btn-sm" onclick="App.startEpisode('${story.id}','${ep.id}')">${ic('replay', 14)} ${ic('key', 14)} ${ep.keyCost}</button>`;
  if (status === 'locked' && ep.bonus) {
    const need = story.bonusEpisode.minCutscenes;
    btn = `<span class="muted small">Пройдите историю и откройте ${need} кат-сцен (${st.cutscenes.length}/${need})</span>`;
  }

  return `<div class="ep-row ${status === 'locked' ? 'dim' : ''} ${ep.bonus ? 'ep-bonus' : ''}">
    <div class="ep-num">${ep.bonus ? ic('sparkle', 20) : ep.num}</div>
    <div class="ep-main">
      <div class="ep-title">${esc(ep.title)} ${ep.bonus ? '<span class="chip chip-badge">Бонус</span>' : ''} ${stChip}</div>
      <div class="ep-prev muted">${esc(ep.preview)}</div>
      ${!es?.rewardClaimed && ep.reward ? `<div class="ep-reward muted small">Награда за первое прохождение: +${ep.reward.hearts} ${ic('heart', 12)}</div>` : ''}
    </div>
    <div class="ep-action">${btn}</div>
  </div>`;
}

function renderStory() {
  const story = storyById(UI.storyId);
  const st = ensureStory(story.id);
  const prog = storyProgress(story);
  const status = storyStatus(story);
  return `<div class="story-page">
    <button class="btn btn-ghost btn-back" onclick="App.go('hub')">← К ивенту</button>
    <div class="story-head">
      <div class="story-head-cover">${art(story.cover)}</div>
      <div class="story-head-info">
        ${resBarHtml()}
        <h1>${esc(story.title)}</h1>
        <div class="story-genres">${story.genres.map(g => `<span class="chip">${g}</span>`).join('')}
          <span class="chip status-chip ${STATUS_META[status].cls}">${STATUS_META[status].label}</span></div>
        <p class="story-desc">${esc(story.desc)}</p>
        <div class="story-meta">
          <div class="pbar"><div class="pbar-fill" style="width:${prog.total ? prog.done / prog.total * 100 : 0}%"></div></div>
          <span class="muted">Эпизоды: ${prog.done}/${prog.total} · Кат-сцены: ${st.cutscenes.length}/${story.cutscenes.length}</span>
        </div>
        <div class="panel-title small-title">Отношения</div>
        ${relBarsHtml(story)}
      </div>
    </div>

    <h2 class="section-title">Эпизоды</h2>
    <div class="ep-list">${story.episodes.map(ep => episodeRowHtml(story, ep)).join('')}</div>

    <h2 class="section-title">Кат-сцены истории</h2>
    <div class="gal-grid">
      ${story.cutscenes.map(cs => {
        const open = st.cutscenes.includes(cs.id);
        return `<div class="gal-cell ${open ? '' : 'locked'}" ${open ? `onclick="App.viewCutscene('${story.id}','${cs.id}')"` : ''}>
          <div class="gal-thumb">${art(cs.id, { locked: !open })}</div>
          <div class="gal-name">${open ? esc(cs.title) : '???'}</div>
          <div class="gal-hint muted">${open ? 'Открыта' : esc(cs.hint)}</div>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

/* ============================ ЗАПУСК ЭПИЗОДА ============================ */

App.startEpisode = (storyId, epId) => {
  const story = storyById(storyId);
  const ep = story.episodes.find(e => e.id === epId);
  const es = ensureEp(storyId, epId);
  const status = episodeStatus(story, ep);
  if (status === 'locked') return;

  /* возврат в начатый эпизод — без ключа */
  if (status === 'progress') { openReader(storyId, epId); return; }

  /* перепрохождение — подтверждение */
  if (status === 'done') {
    popup({
      title: 'Перепройти эпизод?',
      text: `Стоимость: 1 ${ic('key', 16)}. Награды за прохождение и открытые кат-сцены повторно не выдаются, купленные особые выборы останутся открытыми.`,
      buttons: [
        { text: 'Перепройти', cls: 'btn-primary', action: `App.payAndStart('${storyId}','${epId}')` },
        { text: 'Назад', cls: 'btn-ghost', action: 'App.closeModal()' },
      ],
    });
    return;
  }
  App.payAndStart(storyId, epId, false);
};

App.payAndStart = (storyId, epId, fromModal = true) => {
  if (fromModal) App.closeModal();
  const story = storyById(storyId);
  const ep = story.episodes.find(e => e.id === epId);
  if (!spend({ keys: ep.keyCost })) {
    const adventHint = adventClaimable();
    popup({
      title: 'Для прохождения эпизода нужен ключ',
      text: `Ключи можно получить в адвент-календаре, за награды ивента или купить.${adventHint ? '<br><b>В адвенте вас ждёт награда!</b>' : ''}`,
      buttons: [
        { text: 'Адвент-календарь', cls: 'btn-primary', action: 'App.closeModal();App.openAdvent()' },
        { text: 'Купить ключ', cls: 'btn-ghost', action: 'App.closeModal();App.openShop("keys")' },
        { text: 'Назад', cls: 'btn-ghost', action: 'App.closeModal()' },
      ],
    });
    return;
  }
  toast(`−${ep.keyCost} ключ`, 'key');
  const es = ensureEp(storyId, epId);
  es.started = true;
  es.pos = 0;
  save();
  openReader(storyId, epId);
};

/* ============================ ЧИТАЛКА ============================ */

function openReader(storyId, epId) {
  UI.reader = { storyId, epId };
  UI.screen = 'reader';
  render();
}

function readerCtx() {
  const { storyId, epId } = UI.reader;
  const story = storyById(storyId);
  return { story, ep: story.episodes.find(e => e.id === epId), st: ensureStory(storyId), es: ensureEp(storyId, epId) };
}

function checkCond(cond, st) {
  if (cond.flag !== undefined) return st.flags[cond.flag] === cond.eq;
  if (cond.rel !== undefined) return (st.rel[cond.rel] || 0) >= cond.gte;
  if (cond.outfit !== undefined) return S.heroine.outfit === cond.outfit;
  return true;
}

function labelIndex(ep, label) {
  return ep.scenes.findIndex(s => s.label === label);
}

/* Возвращает индекс первой «отображаемой» сцены начиная с pos,
 * обрабатывая label/if/goto; -1 = конец эпизода */
function resolvePos(ep, st, pos) {
  let guard = 0;
  while (pos < ep.scenes.length && guard++ < 500) {
    const s = ep.scenes[pos];
    if (s.if && !checkCond(s.if, st)) { pos++; continue; }
    if (s.goto) { pos = labelIndex(ep, s.goto); continue; }
    if (s.label && !s.text && !s.choice && !s.cutscene) { pos++; continue; }
    return pos;
  }
  return -1;
}

function renderReader() {
  const { story, ep, st, es } = readerCtx();
  const pos = resolvePos(ep, st, es.pos); /* конец эпизода перехвачен в render() */
  es.pos = pos;
  save();
  const s = ep.scenes[pos];

  /* сцена-кат-сцена обрабатывается на клике Next — сюда не попадает */
  if (s.cutscene) {
    triggerCutscene(story.id, s.cutscene, () => { es.pos = pos + 1; save(); render(); });
    return `<div class="reader"></div>`;
  }

  const isChoice = !!s.choice;
  const speakerId = s.who;
  const speakerName = speakerId === 'hero' ? heroName() : speakerId ? REL_LABELS[speakerId] : '';
  const heroEmo = speakerId === 'hero' ? (s.emo || 'calm') : (s.heroEmo || 'calm');
  const bg = s.bg || 'bg.corridor';

  let dialog;
  if (isChoice) {
    const bought = (i) => st.paidBought.includes(`${s.choice.id}:${i}`);
    dialog = `<div class="vn-choice">
      <div class="vn-choice-prompt">${fmtText(s.choice.prompt)}</div>
      ${s.choice.options.map((o, i) => {
        const isPaid = o.cost && !bought(i);
        return `<button class="vn-opt ${o.cost ? 'vn-opt-paid' : ''}" onclick="App.pickOption(${pos},${i})">
          ${o.cost ? `<span class="vn-price">${bought(i) ? ic('check', 14) + ' куплено' : ic('heart', 14) + ' ' + o.cost}</span>` : ''}
          <span>${fmtText(o.text)}</span>
        </button>`;
      }).join('')}
    </div>`;
  } else {
    dialog = `<div class="vn-dialog" onclick="App.nextScene()">
      ${speakerName ? `<div class="vn-name ${speakerId === 'hero' ? 'vn-name-hero' : ''}">${speakerName}</div>` : ''}
      <div class="vn-text ${!speakerName ? 'vn-narrator' : ''}">${fmtText(s.text)}</div>
      <div class="vn-next">▸ дальше</div>
    </div>`;
  }

  const portrait = speakerId && speakerId !== 'hero'
    ? `<div class="vn-portrait">${phPortrait(speakerId, s.emo || 'calm')}</div>` : '';

  return `<div class="reader">
    <div class="vn-bg">${art(bg)}</div>
    <div class="vn-top">
      <button class="btn btn-ghost btn-sm" onclick="App.exitReader()">✕ Выйти</button>
      <span class="vn-ep-title">${esc(story.title)} — Эпизод ${ep.num}: ${esc(ep.title)}</span>
      <span class="vn-hearts">${ic('heart', 16)} ${S.resources.hearts}</span>
    </div>
    <div class="vn-stage">
      <div class="vn-heroine">${heroineSVG(S.heroine, heroEmo)}</div>
      ${portrait}
    </div>
    <div class="vn-bottom">${dialog}</div>
  </div>`;
}

App.nextScene = () => {
  const { ep, st, es } = readerCtx();
  es.pos = es.pos + 1;
  save();
  render();
};

App.exitReader = () => {
  /* прогресс уже сохранён в es.pos */
  App.go('story', UI.reader.storyId);
};

App.pickOption = (pos, i) => {
  const { story, ep, st, es } = readerCtx();
  const s = ep.scenes[pos];
  const o = s.choice.options[i];
  const key = `${s.choice.id}:${i}`;

  if (o.cost && !st.paidBought.includes(key)) {
    if (!canAfford({ hearts: o.cost })) {
      popup({
        title: 'Недостаточно сердец для особого выбора',
        text: `Нужно ${o.cost} ${ic('heart', 16)}. Сердца дают адвент-календарь, кат-сцены и награды за эпизоды.`,
        buttons: [
          { text: 'Магазин', cls: 'btn-primary', action: 'App.closeModal();App.openShop("hearts")' },
          { text: 'Назад', cls: 'btn-ghost', action: 'App.closeModal()' },
        ],
      });
      return;
    }
    spend({ hearts: o.cost });
    st.paidBought.push(key);
    toast(`−${o.cost} сердец: особый выбор`, 'heart');
  }

  if (o.rel) applyRel(story.id, o.rel).forEach(m => toast(m, 'sparkle'));
  if (o.flag) { Object.assign(st.flags, o.flag); save(); }

  const proceed = () => {
    es.pos = o.goto ? labelIndex(ep, o.goto) : pos + 1;
    save();
    render();
  };

  if (o.cutscene) triggerCutscene(story.id, o.cutscene, proceed);
  else proceed();
};

/* показ кат-сцены с наградой; onDone — продолжение читалки */
let csCallback = null;
function triggerCutscene(storyId, csId, onDone) {
  const res = openCutscene(storyId, csId);
  csCallback = onDone;
  pushModal({ type: 'cutscene', storyId, csId, first: res.first, lines: res.lines });
}

App.afterCutscene = () => {
  const m = UI.modals[UI.modals.length - 1];
  UI.modals.pop();
  renderModals();
  if (m.viewOnly) { render(); return; }
  const cb = csCallback; csCallback = null;
  if (cb) cb(); else render();
};

/* ---------- завершение эпизода ---------- */

function finishEpisode() {
  const { story, ep, st, es } = readerCtx();
  const firstTime = !es.completed;
  es.completed = true;
  es.started = false;
  es.pos = 0;

  let lines = [];
  if (firstTime && ep.reward && !es.rewardClaimed) {
    es.rewardClaimed = true;
    lines = grant(ep.reward);
  }
  save();

  const storyId = story.id;
  UI.reader = null;
  UI.screen = 'story';
  UI.storyId = storyId;

  /* завершена ли вся история */
  const mainDone = story.episodes.filter(e => !e.bonus).every(e => st.episodes[e.id]?.completed);
  if (mainDone && !st.completed) {
    st.completed = true;
    save();
    const compLines = story.completionReward ? grant(story.completionReward) : [];
    popup({
      title: 'История завершена!',
      text: `Вы прошли «${esc(story.title)}». ${story.bonusEpisode ? 'Откройте все кат-сцены, чтобы получить доступ к бонусному эпизоду.' : ''}`,
      lines: compLines,
    });
  }

  popup({
    title: `Эпизод «${esc(ep.title)}» завершён!`,
    text: firstTime ? '' : 'Награды за повторное прохождение не выдаются.',
    lines,
  });
  render();
}

/* ============================ DEV-ПАНЕЛЬ ============================ */

App.toggleDev = () => document.getElementById('dev-panel').classList.toggle('hidden');
App.devNextDay = () => { S.day = Math.min(S.day + 1, EVENT.durationDays); save(); toast(`День ивента: ${S.day}`, 'clock'); render(); };
App.devGrant = () => { grant({ keys: 5, hearts: 100, crystals: 100 }); toast('Ресурсы начислены', 'gift'); render(); };
App.devReset = () => {
  resetState();
  UI.screen = 'hub'; UI.storyId = null; UI.reader = null; UI.modals = [];
  renderModals(); render();
  toast('Прогресс сброшен', 'replay');
};

/* ============================ РЕНДЕР ============================ */

function render() {
  /* эпизод дочитан до конца — завершаем до отрисовки читалки */
  if (UI.screen === 'reader' && UI.reader) {
    const { ep, st, es } = readerCtx();
    if (resolvePos(ep, st, es.pos) === -1) { finishEpisode(); return; }
  }
  let html = '';
  if (UI.screen === 'hub') html = renderHub();
  else if (UI.screen === 'story') html = renderStory();
  else if (UI.screen === 'reader') html = renderReader();
  $app.innerHTML = html;
  $app.className = UI.screen === 'reader' ? 'is-reader' : '';
  tickTimer();
}

render();
