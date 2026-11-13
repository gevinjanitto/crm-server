import { useSyncExternalStore } from "react";

const queryText = "(prefers-reduced-motion: reduce)";
const read = () => window.matchMedia(queryText).matches;
const subscribe = (onChange) => {
  const query = window.matchMedia(queryText);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
};
export const useReducedMotionPreference = () => useSyncExternalStore(subscribe, read, () => true);