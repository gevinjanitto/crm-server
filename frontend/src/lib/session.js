export const IDLE_TIMEOUT_MS = 15 * 60 * 1000;
export const ACTIVITY_KEY = "maiharta_session_activity";
export const LOGOUT_KEY = "maiharta_logout_reason";

const sessionId = (token) => token?.split(".")[2] || "cookie-session";
export function readActivity(token) {
  try {
    const saved = JSON.parse(localStorage.getItem(ACTIVITY_KEY));
    return saved?.session === sessionId(token) && Number.isFinite(saved.at) ? saved.at : 0;
  } catch { return 0; }
}
export function writeActivity(token, at) {
  localStorage.setItem(ACTIVITY_KEY, JSON.stringify({ session: sessionId(token), at }));
}
export const sessionMessage = (reason) => reason === "idle"
  ? "Anda otomatis keluar karena tidak ada aktivitas selama 15 menit. Silakan masuk kembali."
  : reason === "expired" ? "Sesi Anda telah berakhir. Silakan masuk kembali." : "";