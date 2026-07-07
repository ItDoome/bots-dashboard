/* ============================================================
 * assets.js — арт-слоты прототипа.
 *
 * Каждая картинка в интерфейсе рендерится через art(slotId).
 * Если у слота в манифесте ART указан src (файл в assets/),
 * рендерится <img>. Пока src нет — рисуется SVG-заглушка.
 * Полный список слотов и размеров — в ASSETS.md.
 * ============================================================ */

/* ---------- палитры и утилиты ---------- */

const SVGH = (w, h, inner, cls = '') =>
  `<svg class="ph ${cls}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;

let __gid = 0;
const gid = (p) => `${p}${++__gid}`;

function lgrad(id, from, to, deg = 90) {
  const rad = (deg - 90) * Math.PI / 180;
  const x2 = 50 + Math.cos(rad) * 50, y2 = 50 + Math.sin(rad) * 50;
  const x1 = 100 - x2, y1 = 100 - y2;
  return `<linearGradient id="${id}" x1="${x1}%" y1="${y1}%" x2="${x2}%" y2="${y2}%">
    <stop offset="0%" stop-color="${from}"/><stop offset="100%" stop-color="${to}"/></linearGradient>`;
}

function stars(n, w, h, color = '#fff', op = 0.8) {
  let s = '';
  for (let i = 0; i < n; i++) {
    const x = (Math.sin(i * 127.3) * 0.5 + 0.5) * w;
    const y = (Math.sin(i * 311.7) * 0.5 + 0.5) * h * 0.6;
    const r = 0.6 + (i % 3) * 0.5;
    s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${color}" opacity="${(op * (0.4 + (i % 5) / 6)).toFixed(2)}"/>`;
  }
  return s;
}

function snow(n, w, h) {
  let s = '';
  for (let i = 0; i < n; i++) {
    const x = (Math.sin(i * 91.7) * 0.5 + 0.5) * w;
    const y = (Math.sin(i * 47.3) * 0.5 + 0.5) * h;
    s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${1 + (i % 3)}" fill="#fff" opacity="${(0.15 + (i % 4) * 0.08).toFixed(2)}"/>`;
  }
  return s;
}

/* Силуэт пары (для кат-сцен) */
function coupleSil(x, y, s, color = '#12101c', mode = 'close') {
  const gap = mode === 'apart' ? 46 * s : mode === 'dance' ? 20 * s : 12 * s;
  const her = `<g>
    <circle cx="${x - gap}" cy="${y - 78 * s}" r="${13 * s}" fill="${color}"/>
    <path d="M ${x - gap - 16 * s} ${y} C ${x - gap - 20 * s} ${y - 50 * s}, ${x - gap - 12 * s} ${y - 66 * s}, ${x - gap} ${y - 64 * s} C ${x - gap + 10 * s} ${y - 66 * s}, ${x - gap + 16 * s} ${y - 46 * s}, ${x - gap + 13 * s} ${y} Z" fill="${color}"/>
    <path d="M ${x - gap - 12 * s} ${y - 86 * s} q ${-10 * s} ${26 * s} ${-4 * s} ${44 * s} L ${x - gap + 14 * s} ${y - 44 * s} q ${8 * s} ${-24 * s} ${-2 * s} ${-42 * s} Z" fill="${color}" opacity="0.92"/>
  </g>`;
  const him = `<g>
    <circle cx="${x + gap}" cy="${y - 84 * s}" r="${13.5 * s}" fill="${color}"/>
    <path d="M ${x + gap - 15 * s} ${y} L ${x + gap - 14 * s} ${y - 68 * s} Q ${x + gap} ${y - 76 * s} ${x + gap + 14 * s} ${y - 68 * s} L ${x + gap + 15 * s} ${y} Z" fill="${color}"/>
  </g>`;
  return him + her;
}

/* Одиночный женский силуэт */
function heroSil(x, y, s, color = '#12101c') {
  return `<g>
    <circle cx="${x}" cy="${y - 80 * s}" r="${13 * s}" fill="${color}"/>
    <path d="M ${x - 17 * s} ${y} C ${x - 21 * s} ${y - 52 * s}, ${x - 12 * s} ${y - 68 * s}, ${x} ${y - 66 * s} C ${x + 11 * s} ${y - 68 * s}, ${x + 18 * s} ${y - 48 * s}, ${x + 14 * s} ${y} Z" fill="${color}"/>
    <path d="M ${x - 13 * s} ${y - 88 * s} q ${-11 * s} ${28 * s} ${-4 * s} ${46 * s} L ${x + 15 * s} ${y - 46 * s} q ${9 * s} ${-25 * s} ${-2 * s} ${-44 * s} Z" fill="${color}" opacity="0.92"/>
  </g>`;
}

/* ============================================================
 * ФОНЫ СЦЕН (16:9)
 * ============================================================ */

const BG_DEFS = {
  gates:        { sky: ['#2c2350', '#6f5aa8'], motif: 'castle',  ground: '#241d3e', label: 'Ворота дворца' },
  room:         { sky: ['#3a2c4e', '#7c5f8e'], motif: 'room',    ground: '#2b2140', label: 'Комната героини' },
  corridor:     { sky: ['#241f38', '#4d3f6e'], motif: 'arches',  ground: '#1c1830', label: 'Коридор дворца' },
  hall:         { sky: ['#2a2248', '#5a4488'], motif: 'throne',  ground: '#211a38', label: 'Тронный зал' },
  ballroom:     { sky: ['#3c2a58', '#8a62b0'], motif: 'ball',    ground: '#2d2148', label: 'Бальный зал' },
  garden:       { sky: ['#365a7c', '#8fb6c9'], motif: 'garden',  ground: '#2c4a3c', label: 'Сад, день' },
  garden_night: { sky: ['#141230', '#3b2f66'], motif: 'gardenN', ground: '#161428', label: 'Ночной сад' },
  balcony:      { sky: ['#402f66', '#c76d8e'], motif: 'balcony', ground: '#2b2148', label: 'Балкон, вечер' },
  study:        { sky: ['#33241f', '#6e4a38'], motif: 'study',   ground: '#241a16', label: 'Кабинет' },
  cafe:         { sky: ['#26203c', '#5c4a80'], motif: 'cafe',    ground: '#1e1830', label: 'Кофейня между мирами' },
};

function bgMotif(kind, w, h) {
  const cx = w / 2;
  switch (kind) {
    case 'castle':
      return `<path d="M ${cx - 210} ${h} L ${cx - 210} ${h - 150} L ${cx - 180} ${h - 195} L ${cx - 150} ${h - 150} L ${cx - 150} ${h - 120}
        L ${cx - 60} ${h - 120} L ${cx - 60} ${h - 230} L ${cx - 20} ${h - 285} L ${cx + 20} ${h - 230} L ${cx + 60} ${h - 230} L ${cx + 60} ${h - 120}
        L ${cx + 150} ${h - 120} L ${cx + 150} ${h - 150} L ${cx + 180} ${h - 195} L ${cx + 210} ${h - 150} L ${cx + 210} ${h} Z" fill="#171230" opacity="0.9"/>
        <rect x="${cx - 16}" y="${h - 190}" width="32" height="70" rx="14" fill="#f5c86e" opacity="0.55"/>${stars(40, w, h)}`;
    case 'room':
      return `<rect x="${w * 0.12}" y="${h * 0.18}" width="${w * 0.22}" height="${h * 0.5}" rx="10" fill="#f0d9a8" opacity="0.35"/>
        <rect x="${w * 0.12}" y="${h * 0.18}" width="${w * 0.22}" height="${h * 0.5}" rx="10" fill="none" stroke="#1f1834" stroke-width="10" opacity="0.8"/>
        <line x1="${w * 0.23}" y1="${h * 0.18}" x2="${w * 0.23}" y2="${h * 0.68}" stroke="#1f1834" stroke-width="6" opacity="0.8"/>
        <rect x="${w * 0.62}" y="${h * 0.55}" width="${w * 0.3}" height="${h * 0.16}" rx="12" fill="#241b3e"/>
        <rect x="${w * 0.66}" y="${h * 0.42}" width="${w * 0.22}" height="${h * 0.14}" rx="10" fill="#2e2350"/>`;
    case 'arches': {
      let a = '';
      for (let i = 0; i < 5; i++) {
        const x = w * 0.08 + i * w * 0.19;
        a += `<path d="M ${x} ${h} L ${x} ${h * 0.34} Q ${x + w * 0.07} ${h * 0.16} ${x + w * 0.14} ${h * 0.34} L ${x + w * 0.14} ${h} Z" fill="#16122a" opacity="${0.55 + i * 0.08}"/>`;
      }
      return a + `<rect x="0" y="${h * 0.88}" width="${w}" height="${h * 0.12}" fill="#120e22" opacity="0.9"/>`;
    }
    case 'throne':
      return `<path d="M ${cx - 70} ${h} L ${cx - 70} ${h * 0.42} Q ${cx} ${h * 0.22} ${cx + 70} ${h * 0.42} L ${cx + 70} ${h} Z" fill="#191333" opacity="0.95"/>
        <path d="M ${cx} ${h * 0.26} l 12 24 l 26 4 l -19 18 l 5 26 l -24 -13 l -24 13 l 5 -26 l -19 -18 l 26 -4 Z" fill="#c9a24f" opacity="0.6"/>
        <rect x="${cx - 180}" y="${h * 0.86}" width="360" height="${h * 0.14}" fill="#140f28" opacity="0.9"/>${stars(16, w, h * 0.5)}`;
    case 'ball': {
      let c = '';
      for (let i = 0; i < 3; i++) {
        const x = w * (0.25 + i * 0.25);
        c += `<path d="M ${x} 0 L ${x} ${h * 0.12}" stroke="#c9a24f" stroke-width="3" opacity="0.6"/>
          <circle cx="${x}" cy="${h * 0.16}" r="20" fill="#f2d488" opacity="0.5"/>
          <circle cx="${x}" cy="${h * 0.16}" r="34" fill="#f2d488" opacity="0.14"/>`;
      }
      return c + stars(30, w, h * 0.7, '#ffe9b0', 0.7) + `<rect x="0" y="${h * 0.87}" width="${w}" height="${h * 0.13}" fill="#1d1636" opacity="0.85"/>`;
    }
    case 'garden':
      return `<circle cx="${w * 0.8}" cy="${h * 0.2}" r="46" fill="#fff3c9" opacity="0.75"/>
        <ellipse cx="${w * 0.18}" cy="${h * 0.75}" rx="130" ry="90" fill="#1f3d2e" opacity="0.85"/>
        <ellipse cx="${w * 0.34}" cy="${h * 0.82}" rx="100" ry="70" fill="#274a36" opacity="0.85"/>
        <ellipse cx="${w * 0.85}" cy="${h * 0.8}" rx="150" ry="85" fill="#20402f" opacity="0.85"/>
        <path d="M ${w * 0.45} ${h} Q ${cx} ${h * 0.7} ${w * 0.58} ${h}" fill="#c9b98a" opacity="0.4"/>`;
    case 'gardenN':
      return `<circle cx="${w * 0.78}" cy="${h * 0.18}" r="40" fill="#f4ecd0" opacity="0.9"/>
        <circle cx="${w * 0.78}" cy="${h * 0.18}" r="58" fill="#f4ecd0" opacity="0.12"/>
        ${stars(50, w, h)}
        <ellipse cx="${w * 0.15}" cy="${h * 0.78}" rx="140" ry="95" fill="#0e0c1e" opacity="0.9"/>
        <ellipse cx="${w * 0.88}" cy="${h * 0.82}" rx="150" ry="90" fill="#0e0c1e" opacity="0.9"/>
        <circle cx="${w * 0.4}" cy="${h * 0.62}" r="7" fill="#ffd98a" opacity="0.9"/>
        <path d="M ${w * 0.4 - 2} ${h * 0.62 + 7} L ${w * 0.4 - 2} ${h * 0.85}" stroke="#0e0c1e" stroke-width="4"/>`;
    case 'balcony':
      return `<circle cx="${w * 0.72}" cy="${h * 0.3}" r="60" fill="#ffd9a0" opacity="0.85"/>
        <circle cx="${w * 0.72}" cy="${h * 0.3}" r="90" fill="#ffd9a0" opacity="0.15"/>
        <rect x="0" y="${h * 0.72}" width="${w}" height="12" fill="#191333"/>
        ${[...Array(12)].map((_, i) => `<rect x="${w * 0.04 + i * w * 0.08}" y="${h * 0.74}" width="10" height="${h * 0.2}" rx="5" fill="#191333"/>`).join('')}
        <rect x="0" y="${h * 0.93}" width="${w}" height="${h * 0.07}" fill="#191333"/>${stars(14, w, h * 0.5)}`;
    case 'study':
      return `${[...Array(4)].map((_, i) => `<rect x="${w * 0.08 + i * w * 0.09}" y="${h * 0.2}" width="${w * 0.07}" height="${h * 0.5}" rx="4" fill="#20150f" opacity="0.9"/>
        ${[...Array(5)].map((__, j) => `<rect x="${w * 0.085 + i * w * 0.09}" y="${h * (0.23 + j * 0.09)}" width="${w * 0.06}" height="${h * 0.05}" rx="2" fill="${['#7a4a3a', '#8a6a3a', '#5a3a4a', '#4a5a3a'][(i + j) % 4]}" opacity="0.7"/>`).join('')}`).join('')}
        <rect x="${w * 0.6}" y="${h * 0.6}" width="${w * 0.3}" height="${h * 0.12}" rx="8" fill="#241610"/>
        <circle cx="${w * 0.68}" cy="${h * 0.52}" r="14" fill="#ffd98a" opacity="0.8"/>`;
    case 'cafe':
      return `${stars(36, w, h)}
        <rect x="${w * 0.1}" y="${h * 0.5}" width="${w * 0.8}" height="${h * 0.1}" rx="14" fill="#241c3e"/>
        <path d="M ${w * 0.3} ${h * 0.5} l 0 -30 q 0 -14 14 -14 l 30 0 q 14 0 14 14 l 0 30 Z" fill="#c98a5a" opacity="0.85"/>
        <path d="M ${w * 0.395} ${h * 0.5 - 36} q 18 4 2 22" stroke="#c98a5a" stroke-width="5" fill="none" opacity="0.85"/>
        <path d="M ${w * 0.34} ${h * 0.5 - 52} q 4 -10 -2 -16 M ${w * 0.36} ${h * 0.5 - 52} q 4 -10 -2 -16" stroke="#fff" stroke-width="3" fill="none" opacity="0.5"/>
        <circle cx="${w * 0.72}" cy="${h * 0.28}" r="26" fill="#8ad4f0" opacity="0.35"/>
        <circle cx="${w * 0.2}" cy="${h * 0.22}" r="18" fill="#f0a8d4" opacity="0.35"/>`;
    default:
      return '';
  }
}

function phBg(kind) {
  const d = BG_DEFS[kind] || BG_DEFS.corridor;
  const id = gid('bg');
  const W = 1280, H = 720;
  return SVGH(W, H, `
    <defs>${lgrad(id, d.sky[0], d.sky[1], 180)}</defs>
    <rect width="${W}" height="${H}" fill="url(#${id})"/>
    ${bgMotif(d.motif, W, H)}
    <rect width="${W}" height="${H}" fill="#0b0912" opacity="0.12"/>
  `, 'ph-bg');
}

/* ============================================================
 * ПЕРСОНАЖИ — простые «аниме»-лица для портретов и героини
 * ============================================================ */

function face(emo, skin, opts = {}) {
  const iris = opts.iris || '#6b4fbb';
  const cy = 0;
  let brows = '', eyes = '', mouth = '', extra = '';
  const eyeL = -13, eyeR = 13;
  const openEye = (x, dx = 0) => `
    <ellipse cx="${x}" cy="${cy}" rx="6.2" ry="${emo === 'surprised' ? 7.6 : 6.4}" fill="#fff"/>
    <circle cx="${x + dx}" cy="${cy + 0.6}" r="${emo === 'surprised' ? 4.4 : 3.9}" fill="${iris}"/>
    <circle cx="${x + dx - 1.4}" cy="${cy - 1.2}" r="1.4" fill="#fff"/>`;
  const happyEye = (x) => `<path d="M ${x - 6} ${cy + 1} Q ${x} ${cy - 6} ${x + 6} ${cy + 1}" stroke="#241d33" stroke-width="2.4" fill="none" stroke-linecap="round"/>`;

  switch (emo) {
    case 'joy':
      eyes = happyEye(eyeL) + happyEye(eyeR);
      brows = `<path d="M -19 -10 Q -13 -14 -7 -11" class="brow"/><path d="M 7 -11 Q 13 -14 19 -10" class="brow"/>`;
      mouth = `<path d="M -7 13 Q 0 21 7 13 Z" fill="#b0475a"/>`;
      break;
    case 'smile':
      eyes = openEye(eyeL) + openEye(eyeR);
      brows = `<path d="M -19 -10 Q -13 -13 -7 -10" class="brow"/><path d="M 7 -10 Q 13 -13 19 -10" class="brow"/>`;
      mouth = `<path d="M -6 14 Q 0 19 6 14" stroke="#b0475a" stroke-width="2.2" fill="none" stroke-linecap="round"/>`;
      break;
    case 'sad':
      eyes = openEye(eyeL) + openEye(eyeR);
      brows = `<path d="M -18 -8 Q -12 -13 -6 -9" class="brow" transform="rotate(8)"/><path d="M 6 -9 Q 12 -13 18 -8" class="brow" transform="rotate(-8)"/>`;
      mouth = `<path d="M -5 16 Q 0 12.5 5 16" stroke="#b0475a" stroke-width="2.2" fill="none" stroke-linecap="round"/>`;
      extra = `<path d="M ${eyeL - 4} 7 q -1.5 4 0 6" stroke="#8ac4e8" stroke-width="2" fill="none" opacity="0.9"/>`;
      break;
    case 'angry':
      eyes = openEye(eyeL) + openEye(eyeR);
      brows = `<path d="M -19 -13 L -6 -8" class="brow"/><path d="M 6 -8 L 19 -13" class="brow"/>`;
      mouth = `<path d="M -5 15 Q 0 13 5 15" stroke="#b0475a" stroke-width="2.4" fill="none" stroke-linecap="round"/>`;
      break;
    case 'shy':
      eyes = openEye(eyeL, 1.6) + openEye(eyeR, 1.6);
      brows = `<path d="M -18 -10 Q -12 -12 -6 -10" class="brow"/><path d="M 6 -10 Q 12 -12 18 -10" class="brow"/>`;
      mouth = `<path d="M -4 14.5 Q 0 17 4 14.5" stroke="#b0475a" stroke-width="2" fill="none" stroke-linecap="round"/>`;
      extra = `<ellipse cx="-16" cy="8" rx="5" ry="3" fill="#e88" opacity="0.5"/><ellipse cx="16" cy="8" rx="5" ry="3" fill="#e88" opacity="0.5"/>`;
      break;
    case 'surprised':
      eyes = openEye(eyeL) + openEye(eyeR);
      brows = `<path d="M -18 -13 Q -12 -16 -6 -13" class="brow"/><path d="M 6 -13 Q 12 -16 18 -13" class="brow"/>`;
      mouth = `<ellipse cx="0" cy="15" rx="3.4" ry="4.4" fill="#b0475a"/>`;
      break;
    case 'cold':
      eyes = `<path d="M ${eyeL - 6} ${cy - 2} l 12 0" stroke="#241d33" stroke-width="2.6" stroke-linecap="round"/>
              <path d="M ${eyeR - 6} ${cy - 2} l 12 0" stroke="#241d33" stroke-width="2.6" stroke-linecap="round"/>
              ${openEye(eyeL)}${openEye(eyeR)}
              <rect x="${eyeL - 7}" y="${cy - 8}" width="14" height="5" fill="${skin}"/>
              <rect x="${eyeR - 7}" y="${cy - 8}" width="14" height="5" fill="${skin}"/>`;
      brows = `<path d="M -18 -11 L -6 -10" class="brow"/><path d="M 6 -10 L 18 -11" class="brow"/>`;
      mouth = `<path d="M -5 15 L 5 15" stroke="#b0475a" stroke-width="2.2" stroke-linecap="round"/>`;
      break;
    default: /* calm */
      eyes = openEye(eyeL) + openEye(eyeR);
      brows = `<path d="M -18 -10 Q -12 -12.5 -6 -10" class="brow"/><path d="M 6 -10 Q 12 -12.5 18 -10" class="brow"/>`;
      mouth = `<path d="M -4.5 15 Q 0 16.5 4.5 15" stroke="#b0475a" stroke-width="2" fill="none" stroke-linecap="round"/>`;
  }
  return `<g class="face" style="--brow:#241d33">${brows.replaceAll('class="brow"', 'stroke="#241d33" stroke-width="2.6" fill="none" stroke-linecap="round"')}${eyes}${mouth}${extra}</g>`;
}

/* ---------- героиня: параметрический спрайт ---------- */

const HERO_SKIN = { eu: '#f3d3bc', asia: '#f6debe', afro: '#a5714f' };
const HERO_HAIR = { black: '#2a2733', blond: '#e6c574', red: '#c25b36' };

const HERO_OUTFITS = {
  base:    { name: 'Простое платье',     dress: '#5c5470', trim: '#7a7290', glow: null },
  festive: { name: 'Праздничное платье', dress: '#a83a5c', trim: '#e8b04a', glow: null },
  advent:  { name: 'Лунное платье',      dress: '#4b3a8f', trim: '#b9a4ff', glow: '#b9a4ff' },
};

function heroineSVG(cfg, emo = 'calm') {
  const skin = HERO_SKIN[cfg.type] || HERO_SKIN.eu;
  const hair = HERO_HAIR[cfg.hair] || HERO_HAIR.black;
  const outfit = HERO_OUTFITS[cfg.outfit] || HERO_OUTFITS.base;
  const W = 260, H = 470;
  const cx = W / 2;
  const headY = 92;

  /* задние волосы — зависят от причёски */
  let backHair = '', frontExtra = '';
  if (cfg.style === 'loose') {
    backHair = `<path d="M ${cx - 46} ${headY + 10} C ${cx - 58} ${headY + 120}, ${cx - 44} ${headY + 190}, ${cx - 30} ${headY + 210}
      L ${cx + 30} ${headY + 210} C ${cx + 46} ${headY + 180}, ${cx + 58} ${headY + 110}, ${cx + 46} ${headY + 10} Z" fill="${hair}"/>`;
  } else if (cfg.style === 'ponytail') {
    backHair = `<path d="M ${cx + 34} ${headY - 24} C ${cx + 78} ${headY + 10}, ${cx + 70} ${headY + 130}, ${cx + 44} ${headY + 185}
      C ${cx + 56} ${headY + 110}, ${cx + 52} ${headY + 40}, ${cx + 30} ${headY - 6} Z" fill="${hair}"/>
      <circle cx="${cx + 33}" cy="${headY - 22}" r="7" fill="${outfit.trim}"/>`;
  } else { /* festive updo */
    backHair = `<ellipse cx="${cx}" cy="${headY - 44}" rx="22" ry="16" fill="${hair}"/>
      <circle cx="${cx - 18}" cy="${headY - 50}" r="4" fill="${outfit.trim}"/>
      <circle cx="${cx + 16}" cy="${headY - 52}" r="4" fill="${outfit.trim}"/>
      <path d="M ${cx - 42} ${headY + 6} q -6 44 4 66 M ${cx + 42} ${headY + 6} q 6 44 -4 66" stroke="${hair}" stroke-width="9" fill="none" stroke-linecap="round"/>`;
  }

  const glow = outfit.glow
    ? `<ellipse cx="${cx}" cy="${H - 60}" rx="86" ry="20" fill="${outfit.glow}" opacity="0.25"/>
       ${stars(10, W, H * 0.9, outfit.glow, 0.9)}`
    : '';

  return SVGH(W, H, `
    ${glow}
    ${backHair}
    <!-- шея и тело -->
    <rect x="${cx - 9}" y="${headY + 26}" width="18" height="26" fill="${skin}"/>
    <path d="M ${cx - 30} ${headY + 66} Q ${cx} ${headY + 44} ${cx + 30} ${headY + 66} L ${cx + 26} ${headY + 96} L ${cx - 26} ${headY + 96} Z" fill="${skin}"/>
    <!-- платье -->
    <path d="M ${cx - 27} ${headY + 78} C ${cx - 30} ${headY + 120}, ${cx - 62} ${headY + 240}, ${cx - 74} ${H - 24}
      L ${cx + 74} ${H - 24} C ${cx + 62} ${headY + 240}, ${cx + 30} ${headY + 120}, ${cx + 27} ${headY + 78}
      Q ${cx} ${headY + 64} ${cx - 27} ${headY + 78} Z" fill="${outfit.dress}"/>
    <path d="M ${cx - 27} ${headY + 80} Q ${cx} ${headY + 66} ${cx + 27} ${headY + 80} L ${cx + 24} ${headY + 96} Q ${cx} ${headY + 84} ${cx - 24} ${headY + 96} Z" fill="${outfit.trim}" opacity="0.9"/>
    <path d="M ${cx - 60} ${H - 60} Q ${cx} ${H - 84} ${cx + 60} ${H - 60}" stroke="${outfit.trim}" stroke-width="4" fill="none" opacity="0.7"/>
    <!-- руки -->
    <path d="M ${cx - 28} ${headY + 84} C ${cx - 46} ${headY + 120}, ${cx - 44} ${headY + 168}, ${cx - 34} ${headY + 196}" stroke="${skin}" stroke-width="13" fill="none" stroke-linecap="round"/>
    <path d="M ${cx + 28} ${headY + 84} C ${cx + 46} ${headY + 120}, ${cx + 40} ${headY + 160}, ${cx + 22} ${headY + 178}" stroke="${skin}" stroke-width="13" fill="none" stroke-linecap="round"/>
    <!-- голова -->
    <circle cx="${cx}" cy="${headY}" r="34" fill="${skin}"/>
    <!-- чёлка -->
    <path d="M ${cx - 36} ${headY + 4} C ${cx - 40} ${headY - 36}, ${cx - 18} ${headY - 46}, ${cx} ${headY - 45}
      C ${cx + 18} ${headY - 46}, ${cx + 40} ${headY - 36}, ${cx + 36} ${headY + 4}
      C ${cx + 28} ${headY - 10}, ${cx + 22} ${headY - 20}, ${cx + 12} ${headY - 22}
      Q ${cx} ${headY - 12} ${cx - 12} ${headY - 22} C ${cx - 22} ${headY - 20}, ${cx - 28} ${headY - 10}, ${cx - 36} ${headY + 4} Z" fill="${hair}"/>
    ${frontExtra}
    <g transform="translate(${cx}, ${headY + 4})">${face(emo, skin)}</g>
  `, 'ph-heroine');
}

/* ---------- портреты остальных персонажей ---------- */

const CHARS = {
  darian: { name: 'Дариан', skin: '#e8c8ae', hair: '#241f30', coat: '#2c2450', trim: '#8f76e8', iris: '#8f76e8', hairShape: 'long' },
  rein:   { name: 'Рейн',   skin: '#e8cbb0', hair: '#b9c2cc', coat: '#274448', trim: '#6fc4c9', iris: '#4f9ba8', hairShape: 'short' },
  lia:    { name: 'Лия',    skin: '#f3d3bc', hair: '#7a4f33', coat: '#7c5a3c', trim: '#e2b878', iris: '#8a6a3a', hairShape: 'bob' },
  vivian: { name: 'Вивиан', skin: '#f0d4c4', hair: '#e9dbc4', coat: '#701f38', trim: '#d4a04a', iris: '#a83a5c', hairShape: 'waves' },
  noa:    { name: 'Ноа',    skin: '#e0c0a4', hair: '#3f7d78', coat: '#33305c', trim: '#8ad4f0', iris: '#4f9ba8', hairShape: 'messy' },
};

function charHair(shape, color, cx, headY) {
  switch (shape) {
    case 'long':
      return `<path d="M ${cx - 34} ${headY + 40} C ${cx - 42} ${headY - 10}, ${cx - 36} ${headY - 40}, ${cx} ${headY - 42}
        C ${cx + 36} ${headY - 40}, ${cx + 42} ${headY - 8}, ${cx + 36} ${headY + 44} L ${cx + 26} ${headY + 30}
        C ${cx + 30} ${headY - 8}, ${cx + 22} ${headY - 24}, ${cx + 10} ${headY - 24} Q ${cx} ${headY - 14} ${cx - 14} ${headY - 24}
        C ${cx - 26} ${headY - 22}, ${cx - 30} ${headY - 4}, ${cx - 26} ${headY + 28} Z" fill="${color}"/>`;
    case 'short':
      return `<path d="M ${cx - 32} ${headY + 2} C ${cx - 36} ${headY - 34}, ${cx - 14} ${headY - 44}, ${cx} ${headY - 43}
        C ${cx + 16} ${headY - 44}, ${cx + 36} ${headY - 32}, ${cx + 32} ${headY + 2}
        C ${cx + 24} ${headY - 14}, ${cx + 14} ${headY - 24}, ${cx - 2} ${headY - 22}
        C ${cx - 16} ${headY - 22}, ${cx - 26} ${headY - 12}, ${cx - 32} ${headY + 2} Z" fill="${color}"/>`;
    case 'bob':
      return `<path d="M ${cx - 34} ${headY + 26} C ${cx - 42} ${headY - 20}, ${cx - 24} ${headY - 44}, ${cx} ${headY - 43}
        C ${cx + 24} ${headY - 44}, ${cx + 42} ${headY - 20}, ${cx + 34} ${headY + 26}
        L ${cx + 24} ${headY + 22} C ${cx + 28} ${headY - 10}, ${cx + 18} ${headY - 24}, ${cx + 8} ${headY - 24}
        Q ${cx} ${headY - 14} ${cx - 12} ${headY - 24} C ${cx - 22} ${headY - 22}, ${cx - 28} ${headY - 8}, ${cx - 24} ${headY + 22} Z" fill="${color}"/>`;
    case 'waves':
      return `<path d="M ${cx - 36} ${headY + 46} C ${cx - 50} ${headY + 10}, ${cx - 38} ${headY - 40}, ${cx} ${headY - 42}
        C ${cx + 38} ${headY - 40}, ${cx + 50} ${headY + 12}, ${cx + 36} ${headY + 46}
        C ${cx + 44} ${headY + 20}, ${cx + 34} ${headY + 30}, ${cx + 30} ${headY + 12}
        C ${cx + 32} ${headY - 16}, ${cx + 20} ${headY - 26}, ${cx + 8} ${headY - 25}
        Q ${cx} ${headY - 15} ${cx - 12} ${headY - 25} C ${cx - 24} ${headY - 24}, ${cx - 32} ${headY - 12}, ${cx - 30} ${headY + 14}
        C ${cx - 34} ${headY + 32}, ${cx - 44} ${headY + 22}, ${cx - 36} ${headY + 46} Z" fill="${color}"/>`;
    default: /* messy */
      return `<path d="M ${cx - 33} ${headY + 4} L ${cx - 38} ${headY - 18} L ${cx - 24} ${headY - 26} L ${cx - 20} ${headY - 42}
        L ${cx - 2} ${headY - 34} L ${cx + 12} ${headY - 44} L ${cx + 20} ${headY - 28} L ${cx + 37} ${headY - 20} L ${cx + 33} ${headY + 4}
        C ${cx + 22} ${headY - 16}, ${cx + 10} ${headY - 24}, ${cx - 4} ${headY - 21}
        C ${cx - 18} ${headY - 21}, ${cx - 26} ${headY - 12}, ${cx - 33} ${headY + 4} Z" fill="${color}"/>`;
  }
}

function phPortrait(charId, emo = 'calm') {
  const c = CHARS[charId];
  if (!c) return '';
  const W = 160, H = 160, cx = W / 2, headY = 74;
  const id = gid('pt');
  return SVGH(W, H, `
    <defs>${lgrad(id, '#241d3e', '#171225', 180)}</defs>
    <rect width="${W}" height="${H}" fill="url(#${id})"/>
    <circle cx="${cx}" cy="${headY - 30}" r="70" fill="${c.trim}" opacity="0.08"/>
    <!-- плечи -->
    <path d="M ${cx - 52} ${H} C ${cx - 46} ${H - 40}, ${cx - 26} ${H - 52}, ${cx} ${H - 52}
      C ${cx + 26} ${H - 52}, ${cx + 46} ${H - 40}, ${cx + 52} ${H} Z" fill="${c.coat}"/>
    <path d="M ${cx - 8} ${H - 52} L ${cx} ${H - 34} L ${cx + 8} ${H - 52} Z" fill="${c.trim}" opacity="0.8"/>
    <rect x="${cx - 8}" y="${headY + 22}" width="16" height="18" fill="${c.skin}"/>
    <circle cx="${cx}" cy="${headY}" r="30" fill="${c.skin}"/>
    ${charHair(c.hairShape, c.hair, cx, headY)}
    <g transform="translate(${cx}, ${headY + 4}) scale(0.88)">${face(emo, c.skin, { iris: c.iris })}</g>
  `, 'ph-portrait');
}

/* ============================================================
 * ОБЛОЖКИ, БАННЕР, КАТ-СЦЕНЫ
 * ============================================================ */

function phCover(storyId) {
  const id = gid('cv');
  const W = 480, H = 660;
  const P = {
    s1: { g: ['#3a2560', '#7c4a8e'], motif: 'castle', accent: '#c9a24f' },
    s2: { g: ['#20304e', '#5c4a80'], motif: 'cafe', accent: '#8ad4f0' },
    s3: { g: ['#1c2a3c', '#3c5a7c'], motif: 'storm', accent: '#7cb8e8' },
  }[storyId] || { g: ['#2a2a3a', '#4a4a6a'], motif: 'castle', accent: '#aaa' };

  let motif = '';
  if (P.motif === 'castle') motif = bgMotif('castle', W, H) + heroSil(W * 0.5, H * 0.97, 1.8, '#150f28');
  if (P.motif === 'cafe') motif = bgMotif('cafe', W, H) + heroSil(W * 0.62, H * 0.99, 1.6, '#141026');
  if (P.motif === 'storm') motif = `${stars(30, W, H)}
    <path d="M ${W * 0.5} ${H * 0.1} L ${W * 0.4} ${H * 0.34} L ${W * 0.52} ${H * 0.34} L ${W * 0.42} ${H * 0.58}" stroke="${P.accent}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    ${heroSil(W * 0.5, H * 0.99, 1.8, '#101828')}`;

  return SVGH(W, H, `
    <defs>${lgrad(id, P.g[0], P.g[1], 180)}</defs>
    <rect width="${W}" height="${H}" fill="url(#${id})"/>
    ${motif}
    <rect x="10" y="10" width="${W - 20}" height="${H - 20}" rx="14" fill="none" stroke="${P.accent}" stroke-width="2" opacity="0.5"/>
  `, 'ph-cover');
}

function phBanner() {
  const id = gid('bn');
  const W = 1280, H = 360;
  return SVGH(W, H, `
    <defs>${lgrad(id, '#241a4e', '#6b3a8e', 120)}</defs>
    <rect width="${W}" height="${H}" fill="url(#${id})"/>
    ${bgMotif('castle', W, H)}
    ${snow(40, W, H)}
    ${coupleSil(W * 0.78, H * 0.99, 1.7, '#150f2a', 'close')}
    <circle cx="${W * 0.12}" cy="${H * 0.3}" r="44" fill="#f4ecd0" opacity="0.85"/>
    <circle cx="${W * 0.12}" cy="${H * 0.3}" r="66" fill="#f4ecd0" opacity="0.12"/>
  `, 'ph-banner');
}

const CS_DEFS = {
  'cs.s1.arrival':    { g: ['#2c2350', '#7c5aa8'], scene: (W, H) => bgMotif('castle', W, H) + heroSil(W * 0.32, H * 0.98, 1.5, '#140f28') + snow(30, W, H) },
  'cs.s1.dance':      { g: ['#3c2a58', '#9a6ab8'], scene: (W, H) => bgMotif('ball', W, H) + coupleSil(W * 0.5, H * 0.98, 1.6, '#1d1435', 'dance') },
  'cs.s1.balcony':    { g: ['#402f66', '#c76d8e'], scene: (W, H) => bgMotif('balcony', W, H) + coupleSil(W * 0.42, H * 0.94, 1.5, '#1b1233', 'apart') },
  'cs.s1.trust':      { g: ['#2a2248', '#6a4a98'], scene: (W, H) => `${stars(30, W, H)}<circle cx="${W / 2}" cy="${H * 0.46}" r="70" fill="#b9a4ff" opacity="0.2"/>
      <path d="M ${W / 2 - 60} ${H * 0.5} C ${W / 2 - 20} ${H * 0.36}, ${W / 2 + 20} ${H * 0.62}, ${W / 2 + 60} ${H * 0.46}" stroke="#e8ddff" stroke-width="14" fill="none" stroke-linecap="round"/>` + coupleSil(W * 0.5, H * 0.99, 1.55, '#171030', 'close') },
  'cs.s1.storm':      { g: ['#141428', '#3a3a5c'], scene: (W, H) => `${[...Array(24)].map((_, i) => `<line x1="${i * W / 24}" y1="0" x2="${i * W / 24 - 40}" y2="${H}" stroke="#8ab" stroke-width="2" opacity="0.25"/>`).join('')}
      <path d="M ${W * 0.5} ${H * 0.06} L ${W * 0.44} ${H * 0.26} L ${W * 0.52} ${H * 0.26} L ${W * 0.45} ${H * 0.46}" stroke="#cfe4ff" stroke-width="6" fill="none" stroke-linecap="round"/>` + coupleSil(W * 0.5, H * 0.99, 1.55, '#0e0c1c', 'apart') },
  'cs.s1.nightgarden':{ g: ['#141230', '#3b2f66'], scene: (W, H) => bgMotif('gardenN', W, H) + coupleSil(W * 0.46, H * 0.98, 1.5, '#0e0c1e', 'close') },
  'cs.s1.confession': { g: ['#4a2450', '#a84a72'], scene: (W, H) => `${stars(36, W, H)}<path d="M ${W / 2} ${H * 0.3} c -22 -26 -62 -6 -50 26 c 8 22 34 34 50 46 c 16 -12 42 -24 50 -46 c 12 -32 -28 -52 -50 -26 Z" fill="#ff9ab8" opacity="0.35"/>` + coupleSil(W * 0.5, H * 0.99, 1.62, '#241028', 'close') },
  'cs.s1.dawn':       { g: ['#2c3a66', '#e89a6e'], scene: (W, H) => `<circle cx="${W * 0.5}" cy="${H * 0.62}" r="80" fill="#ffd9a0" opacity="0.9"/><circle cx="${W * 0.5}" cy="${H * 0.62}" r="130" fill="#ffd9a0" opacity="0.2"/>
      <rect x="0" y="${H * 0.72}" width="${W}" height="${H * 0.28}" fill="#1c1c30" opacity="0.9"/>` + coupleSil(W * 0.24, H * 0.99, 1.5, '#161226', 'close') },
  'cs.s2.door':       { g: ['#26203c', '#5c4a80'], scene: (W, H) => bgMotif('cafe', W, H) + heroSil(W * 0.24, H * 0.98, 1.5, '#141026') },
};

function phCutscene(slot, locked = false) {
  const d = CS_DEFS[slot] || CS_DEFS['cs.s1.arrival'];
  const id = gid('cs');
  const W = 1280, H = 720;
  if (locked) {
    return SVGH(W, H, `
      <rect width="${W}" height="${H}" fill="#17141f"/>
      ${heroSil(W * 0.5, H * 0.92, 2.4, '#221d30')}
      <rect width="${W}" height="${H}" fill="#0d0b14" opacity="0.55"/>
    `, 'ph-cs locked');
  }
  return SVGH(W, H, `
    <defs>${lgrad(id, d.g[0], d.g[1], 160)}
      <radialGradient id="${id}v"><stop offset="60%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.5"/></radialGradient>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#${id})"/>
    ${d.scene(W, H)}
    <rect width="${W}" height="${H}" fill="url(#${id}v)"/>
  `, 'ph-cs');
}

/* ============================================================
 * ИКОНКИ (валюты, ключи, интерфейс)
 * ============================================================ */

const ICONS = {
  key: `<path d="M14.5 3a6.5 6.5 0 0 0-6.2 8.4L2 17.7V22h4.3l1.4-1.4v-2.2h2.2l1.6-1.6a6.5 6.5 0 1 0 3-13.8zm2 6.5a2 2 0 1 1 0-4 2 2 0 0 1 0 4z" fill="#f2c94c"/>`,
  crystal: `<path d="M12 2 5 9l7 13 7-13-7-7zm0 3.2L16.4 9 12 17.6 7.6 9 12 5.2z" fill="#6fc4f0"/><path d="M12 5.2 16.4 9 12 17.6z" fill="#a8dcf7"/>`,
  heart: `<path d="M12 21s-7.5-4.7-9.7-9C.6 8.6 2.6 5 6 5c2.2 0 3.6 1.2 6 3.6C14.4 6.2 15.8 5 18 5c3.4 0 5.4 3.6 3.7 7-2.2 4.3-9.7 9-9.7 9z" fill="#e86a9a"/>`,
  gift: `<path d="M20 7h-2.2A3.5 3.5 0 0 0 12 3.7 3.5 3.5 0 0 0 6.2 7H4a1 1 0 0 0-1 1v3h8V7.5h2V11h8V8a1 1 0 0 0-1-1zM8.5 7A1.5 1.5 0 1 1 10 5.5c.8 0 1 .7 1 1.5H8.5zm7 0H13c0-.8.2-1.5 1-1.5A1.5 1.5 0 1 1 15.5 7zM4 13v7a1 1 0 0 0 1 1h6v-8H4zm9 8h6a1 1 0 0 0 1-1v-7h-7v8z" fill="#c9a4f7"/>`,
  lock: `<path d="M17 9V7a5 5 0 0 0-10 0v2H5v13h14V9h-2zm-8-2a3 3 0 0 1 6 0v2H9V7zm4 9.7V19h-2v-2.3a2 2 0 1 1 2 0z" fill="currentColor"/>`,
  gallery: `<path d="M21 4H3a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1zm-1 12.4-4.2-5-3.3 4-2.3-2.7L6 17.8V6h14v10.4z" fill="currentColor"/><circle cx="9" cy="9.5" r="1.6" fill="currentColor"/>`,
  clock: `<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 10.4 4 2.4-.8 1.4L11 13V6h2v6.4z" fill="currentColor"/>`,
  check: `<path d="M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6 12-12L20.1 5.6z" fill="currentColor"/>`,
  play: `<path d="M8 5v14l11-7z" fill="currentColor"/>`,
  replay: `<path d="M12 5V1L7 6l5 5V7a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z" fill="currentColor"/>`,
  sparkle: `<path d="M12 2l2 6 6 2-6 2-2 6-2-6-6-2 6-2 2-6z" fill="#e8c877"/>`,
  dress: `<path d="M9 3h2c0 1 .4 1.6 1 1.6S13 4 13 3h2l1 4-2 2 3 11H7L10 9 8 7l1-4z" fill="#c9a4f7"/>`,
  book: `<path d="M20 2H8a3 3 0 0 0-3 3v14a3 3 0 0 0 3 3h13v-2H8a1 1 0 0 1 0-2h13V3a1 1 0 0 0-1-1zm-1 12H8c-.4 0-.7 0-1 .1V5a1 1 0 0 1 1-1h11v10z" fill="currentColor"/>`,
  badge: `<path d="M12 2 4 6v6c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10V6l-8-4zm0 4.4 2 4 4.4.4-3.3 2.9 1 4.3L12 15.7 7.9 18l1-4.3-3.3-2.9 4.4-.4 2-4z" fill="#e8c877"/>`,
};

function ic(name, size = 18, cls = '') {
  return `<svg class="ic ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}

/* ============================================================
 * МАНИФЕСТ СЛОТОВ
 * src: null → SVG-заглушка; укажите имя файла из assets/, чтобы
 * подменить заглушку реальным изображением, например:
 *   'cover.s1': { src: 'cover_s1.webp', ... }
 * ============================================================ */

const ART = {
  'banner.event':   { src: null, size: '1280×360', desc: 'Баннер ивента на хабе', ph: () => phBanner() },
  'cover.s1':       { src: null, size: '480×660', desc: 'Обложка «Невеста тёмного принца»', ph: () => phCover('s1') },
  'cover.s2':       { src: null, size: '480×660', desc: 'Обложка «Кофейня на краю миров»', ph: () => phCover('s2') },
  'cover.s3':       { src: null, size: '480×660', desc: 'Обложка «Сердце бури»', ph: () => phCover('s3') },

  'bg.gates':        { src: null, size: '1280×720', desc: 'Фон: ворота дворца, вечер', ph: () => phBg('gates') },
  'bg.room':         { src: null, size: '1280×720', desc: 'Фон: комната героини', ph: () => phBg('room') },
  'bg.corridor':     { src: null, size: '1280×720', desc: 'Фон: коридор дворца', ph: () => phBg('corridor') },
  'bg.hall':         { src: null, size: '1280×720', desc: 'Фон: тронный зал', ph: () => phBg('hall') },
  'bg.ballroom':     { src: null, size: '1280×720', desc: 'Фон: бальный зал', ph: () => phBg('ballroom') },
  'bg.garden':       { src: null, size: '1280×720', desc: 'Фон: сад днём', ph: () => phBg('garden') },
  'bg.garden_night': { src: null, size: '1280×720', desc: 'Фон: ночной сад', ph: () => phBg('garden_night') },
  'bg.balcony':      { src: null, size: '1280×720', desc: 'Фон: балкон на закате', ph: () => phBg('balcony') },
  'bg.study':        { src: null, size: '1280×720', desc: 'Фон: кабинет', ph: () => phBg('study') },
  'bg.cafe':         { src: null, size: '1280×720', desc: 'Фон: кофейня между мирами', ph: () => phBg('cafe') },

  'cs.s1.arrival':     { src: null, size: '1280×720', desc: 'Кат-сцена: прибытие во дворец', ph: (l) => phCutscene('cs.s1.arrival', l) },
  'cs.s1.dance':       { src: null, size: '1280×720', desc: 'Кат-сцена: первый танец', ph: (l) => phCutscene('cs.s1.dance', l) },
  'cs.s1.balcony':     { src: null, size: '1280×720', desc: 'Кат-сцена: разговор на балконе', ph: (l) => phCutscene('cs.s1.balcony', l) },
  'cs.s1.trust':       { src: null, size: '1280×720', desc: 'Кат-сцена: путь доверия', ph: (l) => phCutscene('cs.s1.trust', l) },
  'cs.s1.storm':       { src: null, size: '1280×720', desc: 'Кат-сцена: гроза', ph: (l) => phCutscene('cs.s1.storm', l) },
  'cs.s1.nightgarden': { src: null, size: '1280×720', desc: 'Кат-сцена: ночной сад', ph: (l) => phCutscene('cs.s1.nightgarden', l) },
  'cs.s1.confession':  { src: null, size: '1280×720', desc: 'Кат-сцена: признание', ph: (l) => phCutscene('cs.s1.confession', l) },
  'cs.s1.dawn':        { src: null, size: '1280×720', desc: 'Кат-сцена: рассвет', ph: (l) => phCutscene('cs.s1.dawn', l) },
  'cs.s2.door':        { src: null, size: '1280×720', desc: 'Кат-сцена: дверь между мирами', ph: (l) => phCutscene('cs.s2.door', l) },
};

/* Универсальный рендер арта: <img> если задан src, иначе SVG-заглушка */
function art(slotId, opts = {}) {
  const a = ART[slotId];
  if (!a) return `<div class="ph ph-missing">${slotId}</div>`;
  if (a.src) {
    return `<img class="art ${opts.cls || ''}" src="assets/${a.src}" alt="${a.desc}">`;
  }
  return a.ph(opts.locked || false);
}
