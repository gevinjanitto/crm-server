import React, { useEffect, useState } from "react";
import { Mail, MessageCircle, KeyRound, LoaderCircle, BellOff } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "../lib/api";
import { Switch } from "./ui/switch";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "./ui/alert-dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "./ui/dropdown-menu";

const CHANNELS = [["email", "Email", Mail], ["whatsapp", "WhatsApp", MessageCircle]];
const DURATIONS = [[1, "1 jam"], [3, "3 jam"], [8, "8 jam"], [24, "24 jam"], [0, "Sampai diaktifkan lagi"]];
const clock = (iso) => new Date(iso).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
// Jeda berakhir otomatis setelah waktu `<channel>_until` lewat.
const isMuted = (state, key) => !!state?.[key] && (!state[`${key}_until`] || new Date(state[`${key}_until`]) > new Date());
const useNow = (ms = 30000) => {
  const [, set] = useState(0);
  useEffect(() => { const i = setInterval(() => set((n) => n + 1), ms); return () => clearInterval(i); }, [ms]);
};

export const NotificationPausePanel = () => {
  const [pause, setPause] = useState(null), [hours, setHours] = useState(1);
  useNow();
  useEffect(() => { api.get("/admin/notification-pause").then((r) => setPause(r.data)).catch(() => {}); }, []);
  const change = async (key, value) => {
    const next = { email: isMuted(pause, "email"), whatsapp: isMuted(pause, "whatsapp"), [key]: value, hours };
    try {
      const r = await api.put("/admin/notification-pause", next);
      setPause(r.data);
      const label = DURATIONS.find(([h]) => h === hours)?.[1];
      toast.success(`Notifikasi ${key === "email" ? "email" : "WhatsApp"} semua akun ${value ? `dijeda ${hours ? `selama ${label}` : "sampai diaktifkan lagi"}` : "diaktifkan kembali"}`);
    } catch (e) { toast.error(errorText(e)); }
  };
  if (!pause) return null;
  const any = isMuted(pause, "email") || isMuted(pause, "whatsapp");
  return (
    <div className={`panel notif-pause-panel ${any ? "paused" : ""}`} data-testid="notification-pause-panel">
      <div className="notif-pause-text">
        <BellOff size={18} />
        <div>
          <b>Jeda notifikasi semua akun</b>
          <small>Saat dijeda, email/WhatsApp tidak dikirim ke akun mana pun dan otomatis aktif lagi setelah durasi jeda habis. Notifikasi reset password tetap dikirim.</small>
        </div>
      </div>
      <div className="notif-pause-switches">
        <label className="notif-pause-switch notif-pause-duration">
          Durasi jeda
          <select data-testid="pause-duration-select" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            {DURATIONS.map(([h, label]) => <option key={h} value={h}>{label}</option>)}
          </select>
        </label>
        {CHANNELS.map(([key, label, Icon]) => {
          const muted = isMuted(pause, key), until = pause[`${key}_until`];
          return (
            <label key={key} className="notif-pause-switch">
              <Icon size={15} /> {label} {muted ? "dijeda" : "aktif"}
              {muted && until && <small className="notif-pause-until" data-testid={`pause-all-${key}-until`}>s/d {clock(until)}</small>}
              <Switch checked={muted} onCheckedChange={(v) => change(key, v)} data-testid={`pause-all-${key}`} />
            </label>
          );
        })}
      </div>
    </div>
  );
};

export const UserMuteToggles = ({ user, onChanged }) => {
  const mute = user.notification_mute || {};
  useNow();
  const save = async (key, value, hours = 1) => {
    const next = { email: isMuted(mute, "email"), whatsapp: isMuted(mute, "whatsapp"), [key]: value, hours };
    try {
      await api.put(`/users/${user.id}/notification-mute`, next);
      const label = DURATIONS.find(([h]) => h === hours)?.[1];
      toast.success(`${key === "email" ? "Email" : "WhatsApp"} ${user.name} ${value ? `dijeda ${hours ? `selama ${label}` : "sampai diaktifkan lagi"}` : "diaktifkan"}`);
      onChanged();
    } catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div className="user-mute-toggles">
      {CHANNELS.map(([key, label, Icon]) => {
        const muted = isMuted(mute, key), until = mute[`${key}_until`];
        const title = muted ? `${label}: dijeda${until ? ` s/d ${clock(until)}` : ""} (klik untuk aktifkan)` : `${label}: aktif (klik untuk jeda)`;
        if (muted) return (
          <button key={key} type="button" className="user-mute muted" data-testid={`user-mute-${key}-${user.id}`} title={title} onClick={() => save(key, false)}>
            <Icon size={13} />
          </button>
        );
        return (
          <DropdownMenu key={key}>
            <DropdownMenuTrigger asChild>
              <button type="button" className="user-mute" data-testid={`user-mute-${key}-${user.id}`} title={title}><Icon size={13} /></button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" data-testid={`user-mute-menu-${key}-${user.id}`}>
              <DropdownMenuLabel>Jeda {label} selama</DropdownMenuLabel>
              {DURATIONS.map(([h, text]) => (
                <DropdownMenuItem key={h} data-testid={`user-mute-${key}-${user.id}-${h}`} onSelect={() => save(key, true, h)}>{text}</DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </div>
  );
};

export const ResetPasswordButton = ({ user }) => {
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/users/${user.id}/reset-password`);
      const via = data.channels.length ? data.channels.map((c) => (c === "email" ? "email" : "WhatsApp")).join(" & ") : null;
      toast.success(`${data.message} Password: ${data.default_password}.`, { description: via ? `Notifikasi terkirim via ${via}.` : "Email/WhatsApp belum terkirim, periksa kontak akun atau konfigurasi notifikasi." });
      setOpen(false);
    } catch (e) { toast.error(errorText(e)); }
    setBusy(false);
  };
  return (
    <>
      <button data-testid={`reset-password-${user.id}`} className="icon-button" title="Reset password ke default" aria-label={`Reset password ${user.name}`} onClick={() => setOpen(true)}>
        <KeyRound size={14} />
      </button>
      <AlertDialog open={open} onOpenChange={(v) => !v && !busy && setOpen(false)}>
        <AlertDialogContent data-testid="reset-password-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Reset password ke default?</AlertDialogTitle>
            <AlertDialogDescription>
              Password <b>{user.name}</b> ({user.username}) akan dikembalikan ke <b>12345678</b> dan semua sesi login akan keluar.
              Username & password dikirim ke email dan WhatsApp akun ini. Pengguna wajib membuat password baru saat login.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="reset-password-cancel" disabled={busy}>Batal</AlertDialogCancel>
            <AlertDialogAction data-testid="reset-password-confirm" disabled={busy} onClick={(e) => { e.preventDefault(); reset(); }}>
              {busy && <LoaderCircle className="spin" size={15} />}
              {busy ? "Mereset..." : "Reset password"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
