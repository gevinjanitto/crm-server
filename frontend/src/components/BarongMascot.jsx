import React, { useEffect, useRef } from 'react';
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { useReducedMotionPreference } from '../hooks/useReducedMotionPreference';
import { DeveloperAssets } from './DeveloperAssets';

export const BarongMascot = ({ eyesClosed = false, approved = false, showId = false }) => {
  const rig = useRef(null);
  const enabled = !useReducedMotionPreference();
  const mx = useMotionValue(0), my = useMotionValue(0);
  const headX = useSpring(mx, { stiffness: 72, damping: 15, mass: 1.2 });
  const headY = useSpring(my, { stiffness: 68, damping: 16, mass: 1.2 });
  const eyeX = useSpring(mx, { stiffness: 260, damping: 22 });
  const eyeY = useSpring(my, { stiffness: 260, damping: 22 });
  const rotateY = useTransform(headX, [-1, 1], [-9, 9]);
  const rotateX = useTransform(headY, [-1, 1], [5, -5]);
  const rotateZ = useTransform(headX, [-1, 1], [-1.8, 1.8]);
  const x = useTransform(headX, [-1, 1], ['-1.2%', '1.2%']);
  const gazeX = useTransform(eyeX, [-1, 1], ['-10%', '10%']);
  const gazeY = useTransform(eyeY, [-1, 1], ['-8%', '8%']);

  useEffect(() => {
    let resetTimer;
    const reset = () => { mx.set(0); my.set(0); };
    reset();
    if (!enabled) { headX.jump(0); headY.jump(0); eyeX.jump(0); eyeY.jump(0); return; }
    const follow = event => {
      if (!rig.current || document.hidden) return;
      clearTimeout(resetTimer);
      const rect = rig.current.getBoundingClientRect();
      const clamp = n => Math.max(-1, Math.min(1, n));
      mx.set(clamp((event.clientX - rect.left - rect.width / 2) / Math.max(rect.width, 200)));
      my.set(clamp((event.clientY - rect.top - rect.height * .53) / Math.max(rect.height * .6, 180)));
      if (event.pointerType === 'touch') resetTimer = setTimeout(reset, 1400);
    };
    window.addEventListener('pointermove', follow, { passive: true });
    window.addEventListener('pointerdown', follow, { passive: true });
    window.addEventListener('blur', reset);
    document.documentElement.addEventListener('pointerleave', reset);
    document.addEventListener('visibilitychange', reset);
    return () => {
      clearTimeout(resetTimer);
      window.removeEventListener('pointermove', follow);
      window.removeEventListener('pointerdown', follow);
      window.removeEventListener('blur', reset);
      document.documentElement.removeEventListener('pointerleave', reset);
      document.removeEventListener('visibilitychange', reset);
    };
  }, [enabled, mx, my, headX, headY, eyeX, eyeY]);

  return <div className="barong-mascot-stage" data-testid="barong-mascot-stage">
    <DeveloperAssets/>
    <div className="barong-backdrop" data-testid="barong-backdrop" aria-hidden="true" />
    <div className={`barong-breath ${enabled ? 'is-alive' : ''}`}>
      <motion.div ref={rig} className="barong-rig" data-testid="barong-rig"
        style={{ rotateY, rotateX, rotateZ, x }}>
        <img src="/assets/barong-gaze-base.webp" className="barong-restored" data-testid="barong-image"
          alt="Barong biru MaiHarta dengan mahkota utuh" draggable="false" fetchPriority="high" />
        {['left', 'right'].map(side => <div className={`barong-eye eye-${side}`} key={side} aria-hidden="true">
          <motion.img src={`/assets/barong-eye-${side}.webp`} alt="" draggable="false"
            data-testid={`barong-pupil-${side}`} style={{ x: gazeX, y: gazeY }} />
        </div>)}
        {['left', 'right'].map(side => <div className={`barong-lid-socket socket-${side}`} key={side} aria-hidden="true">
          <motion.span className="barong-lid" data-testid={`barong-lid-${side}`} data-closed={eyesClosed}
            initial={false} animate={{ y: eyesClosed ? '0%' : '-104%' }}
            transition={enabled ? { type: 'spring', stiffness: 320, damping: 28 } : { duration: 0 }} />
        </div>)}
      </motion.div>
      <AnimatePresence>
        {approved && <motion.img key="thumb" src="/assets/barong-thumb.webp" alt="Barong memberi jempol" draggable="false"
          className="barong-thumb" data-testid="barong-thumb-up"
          initial={enabled ? { opacity: 0, y: 60, rotate: -25, scale: .6 } : false}
          animate={{ opacity: 1, y: 0, rotate: 0, scale: 1 }}
          exit={enabled ? { opacity: 0, y: 40, scale: .7 } : { opacity: 0 }}
          transition={enabled ? { type: 'spring', stiffness: 260, damping: 14 } : { duration: 0 }} />}
        {showId && !approved && <motion.img key="id-card" src="/assets/barong-id.webp" alt="Barong memegang kartu ID" draggable="false"
          className="barong-thumb barong-id" data-testid="barong-id-card"
          initial={enabled ? { opacity: 0, x: 50, rotate: 18, scale: .7 } : false}
          animate={{ opacity: 1, x: 0, rotate: -4, scale: 1 }}
          exit={enabled ? { opacity: 0, x: 40, scale: .75 } : { opacity: 0 }}
          transition={enabled ? { type: 'spring', stiffness: 240, damping: 16 } : { duration: 0 }} />}
      </AnimatePresence>
    </div>
  </div>;
};