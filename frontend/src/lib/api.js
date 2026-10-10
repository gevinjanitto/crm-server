import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { mutate } from 'swr';
const TOKEN_KEY = "maiharta_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);
export const api = axios.create({
  baseURL: `${process.env.REACT_APP_BACKEND_URL}/api`,
  withCredentials: true,
});
api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});
// Only refresh after a successful save, never on an optimistic drag preview.
api.interceptors.response.use((response) => {
  const { method, url } = response.config;
  const match = url?.match(/^\/projects\/([^/]+)\/(tasks|statuses)(?:\/|$)/);
  if (match && ['patch', 'post', 'delete'].includes(method)) {
    mutate(`/projects/${match[1]}/tickets/summary`).catch(() => {});
  }
  return response;
});
export const errorText = (e) => {
  const detail = e.response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : Array.isArray(detail)
      ? detail.map((x) => `${x.loc?.slice(-1)[0]}: ${x.msg}`).join(", ")
      : "Terjadi kesalahan. Silakan coba kembali.";
};
export function useData(path) {
  const [data, setData] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const reload = useCallback(async () => {
    try {
      const r = await api.get(path);
      setData(r.data);
      setError("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    setLoading(true);
    reload();
  }, [reload]);
  return { data, loading, error, reload, setData };
}
export const money = (n) =>
  new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(n || 0);
export const compact = (n) =>
  n >= 1e9
    ? `${+(n / 1e9).toFixed(2)} M`
    : n >= 1e6
      ? `${+(n / 1e6).toFixed(1)} jt`
      : new Intl.NumberFormat("id-ID").format(n || 0);
export const dateLabel = (d) =>
  d
    ? new Date(d).toLocaleDateString("id-ID", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "—";
export const initials = (s) =>
  (s || "")
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
export async function download(path, name) {
  try {
    const r = await api.get(path, { responseType: "blob" });
    const u = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = u;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(u), 1000);
  } catch (e) {
    toast.error("Dokumen tidak dapat diunduh.");
  }
}
export const statuses = [
  "Project Masuk",
  "Follow Up",
  "Dokumen Disiapkan",
  "Scope Dirinci",
  "UI/UX",
  "Disetujui",
  "Development",
  "Uploaded to Dev Server",
  "Testing",
  "Revisi",
  "Uploaded to Production",
  "Selesai",
];
export const taskStatuses = [
  "Belum Mulai",
  "Dikerjakan",
  "Testing",
  "Revisi",
  "Selesai",
];
export const serverStages = ["Belum Naik", "Dev Server", "Production"];
export const slug = (s) => String(s).toLowerCase().replace(/\s+/g, "-");
export const ticketStatuses = [
  "Baru",
  "Ditinjau",
  "Menunggu Klarifikasi",
  "Diterima",
  "Ditolak",
  "Menunggu Estimasi Biaya",
  "Menunggu Persetujuan",
  "Dikerjakan",
  "Selesai",
  "Ditutup",
];
