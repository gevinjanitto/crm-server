import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useAuth } from "../App";
import { OrbitBackdrop } from "./OrbitBackdrop";
import { useReducedMotionPreference } from "../hooks/useReducedMotionPreference";

// Full page load and explicit auth transitions only; navigation never replays it.
export const BrandIntro = ({ children }) => {
  const { authAnimation } = useAuth();
  const previousAnimation = useRef(authAnimation);
  // Read synchronously and subscribe to changes; never queue a decorative intro
  // for users who have requested reduced motion, even during an active animation.
  const reduced = useReducedMotionPreference();
  const [visible, setVisible] = useState(!reduced);
  const [blocking, setBlocking] = useState(!reduced);
  useEffect(() => {
    if (!reduced && authAnimation !== previousAnimation.current) {
      setVisible(true);
      setBlocking(true);
    }
    previousAnimation.current = authAnimation;
  }, [authAnimation, reduced]);
  useEffect(() => {
    if (reduced) {
      setVisible(false);
      setBlocking(false);
      return;
    }
    if (!visible) return;
    const timer = window.setTimeout(() => setVisible(false), 1150);
    return () => window.clearTimeout(timer);
  }, [visible, reduced, authAnimation]);
  const ease = [.22, 1, .36, 1];
  return <>
    <div inert={blocking && !reduced ? true : undefined}>{children}</div>
    {!reduced && <AnimatePresence onExitComplete={() => setBlocking(false)}>
      {visible && <motion.div className="brand-intro" key="brand-intro" role="status" aria-live="polite" data-testid="brand-intro"
        initial={{ opacity: 1 }} exit={reduced ? { opacity: 0 } : { y: "-100%" }}
        transition={{ duration: reduced ? .1 : .65, ease: [.76, 0, .24, 1] }}>
        <OrbitBackdrop variant="intro" />
        <div className="brand-intro-content">
          <motion.img src="/assets/logo-mark.webp" alt="Logo MaiHarta" data-testid="brand-intro-logo"
            initial={reduced ? false : { scale: .65, opacity: 0, rotate: -16 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }} transition={{ duration: .65, ease }} />
          <div className="brand-intro-name-mask">
            <motion.h1 data-testid="brand-intro-name" initial={reduced ? false : { y: "110%" }} animate={{ y: 0 }} transition={{ duration: .6, delay: .15, ease }}>CRM <b>MaiHarta</b></motion.h1>
          </div>
          <motion.p data-testid="brand-intro-tagline" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: .35 }}>CONNECT. CREATE. GROW.</motion.p>
          <div className="brand-intro-progress" aria-hidden="true"><motion.span initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: reduced ? 0 : 1.05, ease: "easeInOut" }} /></div>
          <span className="sr-only">Menyiapkan ruang kerja MaiHarta.</span>
        </div>
        <span className="brand-intro-footer" data-testid="brand-intro-footer">Satu ruang. Tanpa batas.</span>
      </motion.div>}
    </AnimatePresence>}
  </>;
};