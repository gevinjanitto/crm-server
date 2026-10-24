import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";

export const AI_STATUS_EVENT = "maiharta-ai-status";
export const notifyAiStatus = () => window.dispatchEvent(new Event(AI_STATUS_EVENT));

export function useAiStatus() {
  const [status, setStatus] = useState(null);
  const load = useCallback(() => api.get("/ai/status").then((r) => setStatus(r.data)).catch(() => setStatus(null)), []);
  useEffect(() => {
    load();
    window.addEventListener(AI_STATUS_EVENT, load);
    return () => window.removeEventListener(AI_STATUS_EVENT, load);
  }, [load]);
  return status;
}
