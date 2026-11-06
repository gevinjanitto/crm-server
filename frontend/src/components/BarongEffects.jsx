import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';

const spring = { type: 'spring', stiffness: 260, damping: 16 };
const off = { duration: 0 };

export const BarongGlasses = ({ show, enabled }) => <AnimatePresence>
  {show && <motion.svg key="glasses" className="barong-glasses" data-testid="barong-glasses" viewBox="0 0 410 120" aria-hidden="true"
    initial={enabled ? { opacity: 0, y: '-120%', rotate: -10, scale: 1.2 } : false} animate={{ opacity: 1, y: 0, rotate: 0, scale: 1 }}
    exit={enabled ? { opacity: 0, y: '-90%', rotate: 8 } : { opacity: 0 }} transition={enabled ? spring : off}>
    <path d="M20 44 L2 30 M390 44 L408 30" stroke="#1d2333" strokeWidth="11" strokeLinecap="round" fill="none" />
    <path d="M180 54 Q205 34 230 54" stroke="#1d2333" strokeWidth="11" strokeLinecap="round" fill="none" />
    {[18, 228].map((x) => <g key={x}>
      <rect x={x} y="10" width="164" height="100" rx="44" fill="#a9ddff4d" stroke="#1d2333" strokeWidth="12" />
      <rect x={x + 5} y="15" width="154" height="90" rx="40" fill="none" stroke="#f3c76b" strokeWidth="3" />
      <path className="bfx-glint" d={`M${x + 34} 82 L${x + 82} 24 M${x + 62} 88 L${x + 104} 36`} stroke="#fff" strokeWidth="8" strokeLinecap="round" opacity=".7" />
    </g>)}
  </motion.svg>}
</AnimatePresence>;

const Cloud = () => <svg viewBox="0 0 220 175" aria-hidden="true">
  <defs><linearGradient id="bfx-cloud" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#cfe5ff" /></linearGradient></defs>
  <path d="M60 110 C30 110 14 92 14 72 C14 52 30 38 50 38 C56 18 76 6 100 6 C128 6 148 24 152 48 C176 48 204 62 204 82 C204 98 190 110 170 110 Z"
    fill="url(#bfx-cloud)" stroke="#173768" strokeWidth="5" strokeLinejoin="round" />
  <path className="bfx-pulse" d="M110 42 V82 M94 68 L110 84 L126 68" stroke="#173768" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  {[66, 110, 154].map((x, i) => <g key={x} transform={`translate(${x} 122)`}>
    <g className="bfx-drop" style={{ animationDelay: `${i * 0.28}s` }}>
      <path d="M0 0 V22 M-9 13 L0 22 L9 13" stroke="#f3c76b" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </g>
  </g>)}
</svg>;

const Win = () => <svg viewBox="0 0 220 170" aria-hidden="true">
  <rect x="5" y="5" width="210" height="160" rx="16" fill="#fff" stroke="#173768" strokeWidth="5" />
  <path d="M5 21 Q5 5 21 5 H199 Q215 5 215 21 V38 H5 Z" fill="#173768" />
  {[['#ff8a7a', 26], ['#f3c76b', 44], ['#7fe0a8', 62]].map(([c, x]) => <circle key={x} cx={x} cy="21" r="6" fill={c} />)}
  <rect x="84" y="15" width="112" height="12" rx="6" fill="#ffffff33" />
  {[[24, 56, 150], [24, 78, 120], [24, 100, 140], [24, 122, 86]].map(([x, y, w], i) =>
    <rect key={y} className="bfx-line" style={{ animationDelay: `${i * 0.15}s` }} x={x} y={y} width={w} height="10" rx="5" fill="#cfdcf0" />)}
  <g className="bfx-pulse" transform="translate(178 132)">
    <circle r="22" fill="#f3c76b" stroke="#173768" strokeWidth="4" />
    <path d="M-8 8 L8 -8 M-4 -8 H8 V4" stroke="#173768" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </g>
</svg>;

const FX = {
  cloud: { C: Cloud, cls: 'bfx-cloud', init: { opacity: 0, y: -40, scale: .5 }, out: { opacity: 0, y: -30, scale: .7 } },
  window: { C: Win, cls: 'bfx-window', init: { opacity: 0, scale: .2, rotate: -18, x: 30, y: 30 }, out: { opacity: 0, scale: .4, rotate: 10 } },
};

export const BarongEffects = ({ effect, enabled }) => <AnimatePresence>
  {FX[effect] && (() => {
    const { C, cls, init, out } = FX[effect];
    return <motion.div key={effect} className={`barong-fx ${cls}`} data-testid={`barong-fx-${effect}`}
      initial={enabled ? init : false} animate={{ opacity: 1, scale: 1, rotate: 0, x: 0, y: 0 }}
      exit={enabled ? out : { opacity: 0 }} transition={enabled ? spring : off}><C /></motion.div>;
  })()}
</AnimatePresence>;
