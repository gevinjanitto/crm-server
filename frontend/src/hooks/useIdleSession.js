import { useEffect } from "react";
import { api, getToken } from "../lib/api";
import { ACTIVITY_KEY, IDLE_TIMEOUT_MS, LOGOUT_KEY, readActivity, writeActivity } from "../lib/session";

// Wall-clock deadlines survive refresh, sleeping devices and throttled background tabs.
export function useIdleSession(user, logout) {
  useEffect(() => {
    if (!user) return;
    const token = getToken();
    let ended = false, deadlineTimer, syncTimer, lastSync = 0;
    const initial = readActivity(token) || user.session_last_activity || Date.now();
    writeActivity(token, initial);
    const expire = (reason = "idle", remote = false) => {
      if (ended) return;
      ended = true;
      logout(reason, remote);
    };
    const check = () => {
      if (ended) return false;
      const remaining = IDLE_TIMEOUT_MS - (Date.now() - readActivity(token));
      if (remaining <= 0) { expire(); return false; }
      window.clearTimeout(deadlineTimer);
      deadlineTimer = window.setTimeout(check, remaining);
      return true;
    };
    const syncActivity = () => {
      syncTimer = undefined;
      if (!check()) return;
      lastSync = Date.now();
      api.post("/auth/activity", { idle_for_ms: Math.max(0, Date.now() - readActivity(token)) }, { timeout: 10000 })
        .catch((error) => {
          if (error.response?.status === 401) expire(error.response.data?.detail?.includes("15 menit") ? "idle" : "expired");
        });
    };
    const interact = () => {
      // An event after the deadline must not resurrect an expired session.
      if (document.hidden || !check()) return;
      const now = Date.now();
      if (now - readActivity(token) < 1000) return;
      writeActivity(token, now);
      check();
      // Coalesce rapid input; a final trailing sync retains the real event time.
      if (now - lastSync >= 30000) {
        window.clearTimeout(syncTimer);
        syncActivity();
      } else if (!syncTimer) {
        syncTimer = window.setTimeout(syncActivity, 30000 - (now - lastSync));
      }
    };
    const storage = (event) => {
      if (event.key === LOGOUT_KEY && event.newValue) expire(event.newValue, true);
      else if (event.key === ACTIVITY_KEY) check();
    };
    const events = ["pointermove", "pointerdown", "keydown", "scroll", "wheel", "touchstart"];
    events.forEach((event) => window.addEventListener(event, interact, { passive: true, capture: true }));
    window.addEventListener("storage", storage);
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", check);
    const interceptor = api.interceptors.response.use((response) => response, (error) => {
      if (error.response?.status === 401 && !error.config?.url?.includes("/auth/logout")) {
        expire(error.response.data?.detail?.includes("15 menit") ? "idle" : "expired");
      }
      return Promise.reject(error);
    });
    check();
    return () => {
      ended = true;
      window.clearTimeout(deadlineTimer);
      window.clearTimeout(syncTimer);
      events.forEach((event) => window.removeEventListener(event, interact, true));
      window.removeEventListener("storage", storage);
      window.removeEventListener("focus", check);
      document.removeEventListener("visibilitychange", check);
      api.interceptors.response.eject(interceptor);
    };
  }, [user, logout]);
}