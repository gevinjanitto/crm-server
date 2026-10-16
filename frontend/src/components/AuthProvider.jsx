import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, getToken, setToken } from "../lib/api";
import { LOGOUT_KEY, IDLE_TIMEOUT_MS, readActivity, writeActivity } from "../lib/session";
import { useIdleSession } from "../hooks/useIdleSession";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authAnimation, setAuthAnimation] = useState(0);
  const [logoutReason, setLogoutReason] = useState(() => localStorage.getItem(LOGOUT_KEY) || "");
  const loggingOut = useRef(false);
  const logout = useCallback(async (reason = "manual", remote = false) => {
    if (loggingOut.current) return;
    loggingOut.current = true;
    const token = getToken();
    const why = typeof reason === "string" ? reason : "manual";
    localStorage.setItem(LOGOUT_KEY, why);
    setLogoutReason(why);
    setToken(null);
    setUser(null);
    setAuthAnimation((value) => value + 1);
    // Clear private UI immediately, even offline; marker prevents cookie restore.
    if (!remote) {
      try {
        await api.post("/auth/logout", {}, { headers: token ? { Authorization: `Bearer ${token}` } : {}, timeout: 10000 });
      } catch { /* Server idle expiry also prevents reuse of an abandoned session. */ }
    }
  }, []);
  const completeLogin = useCallback(({ token, user: account }) => {
    loggingOut.current = false;
    localStorage.removeItem(LOGOUT_KEY);
    setLogoutReason("");
    setToken(token);
    writeActivity(token, Date.now());
    setUser(account);
    setAuthAnimation((value) => value + 1);
  }, []);
  useEffect(() => {
    let cancelled = false;
    if (localStorage.getItem(LOGOUT_KEY)) { setLoading(false); return; }
    api.get("/auth/me").then(({ data }) => {
      if (cancelled) return;
      // A reload is not activity. Prefer the persisted event time for this exact
      // session; server time is only a fallback when no browser record exists.
      const last = readActivity(getToken()) || data.session_last_activity || 0;
      if (last && Date.now() - last >= IDLE_TIMEOUT_MS) logout("idle");
      else setUser(data);
    }).catch((error) => {
      if (!cancelled && error.response?.data?.detail?.includes("15 menit")) logout("idle");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [logout]);
  useIdleSession(user, logout);
  return <AuthContext.Provider value={{ user, setUser, loading, logout, completeLogin, authAnimation, logoutReason }}>{children}</AuthContext.Provider>;
};